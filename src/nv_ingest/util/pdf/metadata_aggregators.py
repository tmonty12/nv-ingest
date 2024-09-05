# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

import pandas as pd
import pypdfium2 as pdfium

from nv_ingest.schemas.metadata_schema import ContentSubtypeEnum
from nv_ingest.schemas.metadata_schema import ContentTypeEnum
from nv_ingest.schemas.metadata_schema import ImageTypeEnum
from nv_ingest.schemas.metadata_schema import StdContentDescEnum
from nv_ingest.schemas.metadata_schema import TableFormatEnum
from nv_ingest.schemas.metadata_schema import validate_metadata
from nv_ingest.util.converters import datetools
from nv_ingest.util.detectors.language import detect_language
from nv_ingest.util.exception_handlers.pdf import pdfium_exception_handler


@dataclass
class DataFrameTable:
    df: pd.DataFrame
    bbox: Tuple[int, int, int, int]


@dataclass
class ImageTable:
    content: str
    image: str
    bbox: Tuple[int, int, int, int]


@dataclass
class ImageChart:
    content: str
    image: str
    bbox: Tuple[int, int, int, int]


@dataclass
class LatexTable:
    latex: pd.DataFrame
    bbox: Tuple[int, int, int, int]


@dataclass
class Base64Image:
    image: str
    bbox: Tuple[int, int, int, int]
    width: int
    height: int


@dataclass
class PDFMetadata:
    """
    A data object to store metadata information extracted from a PDF document.
    """

    page_count: int
    filename: str
    last_modified: str
    date_created: str
    keywords: List[str]
    source_type: str = "PDF"


def extract_pdf_metadata(doc: pdfium.PdfDocument, source_id: str) -> PDFMetadata:
    """
    Extracts metadata and relevant information from a PDF document.

    Parameters
    ----------
    pdf_stream : bytes
        The PDF document data as a byte stream.
    source_id : str
        The identifier for the source document, typically the filename.

    Returns
    -------
    PDFMetadata
        An object containing extracted metadata and information including:
        - `page_count`: The total number of pages in the PDF.
        - `filename`: The source filename or identifier.
        - `last_modified`: The last modified date of the PDF document.
        - `date_created`: The creation date of the PDF document.
        - `keywords`: Keywords associated with the PDF document.
        - `source_type`: The type/format of the source, e.g., "PDF".

    Raises
    ------
    PdfiumError
        If there is an issue processing the PDF document.
    """
    page_count: int = len(doc)
    filename: str = source_id

    # Extract document metadata
    doc_meta = doc.get_metadata_dict()

    # Extract and process the last modified date
    last_modified: str = doc_meta.get("ModDate")
    if last_modified in (None, ""):
        last_modified = datetools.remove_tz(datetime.now()).isoformat()
    else:
        last_modified = datetools.datetimefrompdfmeta(last_modified)

    # Extract and process the creation date
    date_created: str = doc_meta.get("CreationDate")
    if date_created in (None, ""):
        date_created = datetools.remove_tz(datetime.now()).isoformat()
    else:
        date_created = datetools.datetimefrompdfmeta(date_created)

    # Extract keywords, defaulting to an empty list if not found
    keywords: List[str] = doc_meta.get("Keywords", [])

    # Create the PDFMetadata object
    metadata = PDFMetadata(
        page_count=page_count,
        filename=filename,
        last_modified=last_modified,
        date_created=date_created,
        keywords=keywords,
    )

    return metadata


def construct_text_metadata(
    accumulated_text,
    keywords,
    page_idx,
    block_idx,
    line_idx,
    span_idx,
    page_count,
    text_depth,
    source_metadata,
    base_unified_metadata,
):
    if len(accumulated_text) < 1:
        return []

    extracted_text = " ".join(accumulated_text)

    content_metadata = {
        "type": ContentTypeEnum.TEXT,
        "description": StdContentDescEnum.PDF_TEXT,
        "page_number": page_idx,
        "hierarchy": {
            "page_count": page_count,
            "page": page_idx,
            "block": -1,
            "line": -1,
            "span": -1,
        },
    }

    language = detect_language(extracted_text)

    # TODO(Devin) - Implement bounding box logic for text
    bbox = (-1, -1, -1, -1)

    text_metadata = {
        "text_type": text_depth,
        "summary": "",
        "keywords": keywords,
        "language": language,
        "text_location": bbox,
    }

    ext_unified_metadata = base_unified_metadata.copy()

    ext_unified_metadata.update(
        {
            "content": extracted_text,
            "source_metadata": source_metadata,
            "content_metadata": content_metadata,
            "text_metadata": text_metadata,
        }
    )

    validated_unified_metadata = validate_metadata(ext_unified_metadata)

    return [ContentTypeEnum.TEXT, validated_unified_metadata.dict(), str(uuid.uuid4())]


def construct_image_metadata(
    image_base64: Base64Image,
    page_idx: int,
    page_count: int,
    source_metadata: Dict[str, Any],
    base_unified_metadata: Dict[str, Any],
) -> List[Any]:
    """
    Extracts image data from a PdfImage object, converts it to a base64-encoded string,
    and constructs metadata for the image.

    Parameters
    ----------
    image_obj : PdfImage
        The PdfImage object from which the image will be extracted.
    page_idx : int
        The index of the current page being processed.
    page_count : int
        The total number of pages in the PDF document.
    source_metadata : dict
        Metadata related to the source of the PDF document.
    base_unified_metadata : dict
        The base unified metadata structure to be updated with the extracted image information.

    Returns
    -------
    List[Any]
        A list containing the content type, validated metadata dictionary, and a UUID string.

    Raises
    ------
    PdfiumError
        If the image cannot be extracted due to an issue with the PdfImage object.
        :param image_base64:
    """
    # Define the assumed image type (e.g., PNG)
    image_type: str = "PNG"

    # Construct content metadata
    content_metadata: Dict[str, Any] = {
        "type": ContentTypeEnum.IMAGE,
        "description": StdContentDescEnum.PDF_IMAGE,
        "page_number": page_idx,
        "hierarchy": {
            "page_count": page_count,
            "page": page_idx,
            "block": -1,
            "line": -1,
            "span": -1,
            "nearby_objects": [],
        },
    }

    # Construct image metadata
    image_metadata: Dict[str, Any] = {
        "image_type": image_type,
        "structured_image_type": ImageTypeEnum.image_type_1,
        "caption": "",
        "text": "",
        "image_location": image_base64.bbox,
        "width": image_base64.width,
        "height": image_base64.height,
    }

    # Update the unified metadata with the extracted image information
    unified_metadata: Dict[str, Any] = base_unified_metadata.copy()
    unified_metadata.update(
        {
            "content": image_base64.image,
            "source_metadata": source_metadata,
            "content_metadata": content_metadata,
            "image_metadata": image_metadata,
        }
    )

    # Validate and return the unified metadata
    validated_unified_metadata = validate_metadata(unified_metadata)
    return [ContentTypeEnum.IMAGE, validated_unified_metadata.dict(), str(uuid.uuid4())]


# TODO(Devin): Disambiguate tables and charts, create two distinct processing methods
@pdfium_exception_handler(descriptor="pdfium")
def construct_table_and_chart_metadata(
    table: Union[DataFrameTable, ImageTable, ImageChart],
    page_idx: int,
    page_count: int,
    source_metadata: Dict,
    base_unified_metadata: Dict,
):
    """
    +--------------------------------+--------------------------+------------+---+
    | Table/Chart Metadata           |                          | Extracted  | Y |
    | (tables within documents)      |                          |            |   |
    +--------------------------------+--------------------------+------------+---+
    | Table format                   | Structured (dataframe /  | Extracted  |   |
    |                                | lists of rows and        |            |   |
    |                                | columns), or serialized  |            |   |
    |                                | as markdown, html,       |            |   |
    |                                | latex, simple (cells     |            |   |
    |                                | separated just as spaces)|            |   |
    +--------------------------------+--------------------------+------------+---+
    | Table content                  | Extracted text content   |            |   |
    |                                |                          |            |   |
    |                                | Important: Tables should |            |   |
    |                                | not be chunked           |            |   |
    +--------------------------------+--------------------------+------------+---+
    | Table location                 | Bounding box of the table|            |   |
    +--------------------------------+--------------------------+------------+---+
    | Caption                        | Detected captions for    |            |   |
    |                                | the table/chart          |            |   |
    +--------------------------------+--------------------------+------------+---+
    | uploaded_image_uri             | Mirrors                  |            |   |
    |                                | source_metadata.         |            |   |
    |                                | source_location          |            |   |
    +--------------------------------+--------------------------+------------+---+
    """

    if isinstance(table, DataFrameTable):
        content = table.df.to_markdown(index=False)
        structured_content_text = content
        table_format = TableFormatEnum.MARKDOWN
        subtype = ContentSubtypeEnum.TABLE
        description = StdContentDescEnum.PDF_TABLE

    elif isinstance(table, ImageTable):
        content = table.image
        structured_content_text = table.content
        table_format = TableFormatEnum.IMAGE
        subtype = ContentSubtypeEnum.TABLE
        description = StdContentDescEnum.PDF_TABLE

    elif isinstance(table, ImageChart):
        content = table.image
        structured_content_text = table.content
        table_format = TableFormatEnum.IMAGE
        subtype = ContentSubtypeEnum.CHART
        description = StdContentDescEnum.PDF_CHART

    else:
        raise ValueError("Unknown table/chart type.")

    content_metadata = {
        "type": ContentTypeEnum.STRUCTURED,
        "description": description,
        "page_number": page_idx,
        "hierarchy": {
            "page_count": page_count,
            "page": page_idx,
            "line": -1,
            "span": -1,
        },
        "subtype": subtype,
    }

    table_metadata = {
        "caption": "",
        "table_format": table_format,
        "table_content": structured_content_text,
        "table_location": table.bbox,
    }

    ext_unified_metadata = base_unified_metadata.copy()

    ext_unified_metadata.update(
        {
            "content": content,
            "source_metadata": source_metadata,
            "content_metadata": content_metadata,
            "table_metadata": table_metadata,
        }
    )

    validated_unified_metadata = validate_metadata(ext_unified_metadata)

    return [ContentTypeEnum.STRUCTURED, validated_unified_metadata.dict(), str(uuid.uuid4())]