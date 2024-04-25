# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments

import logging
from typing import Dict
from typing import Literal

from pydantic import BaseModel
from pydantic import root_validator
from pydantic import validator

from .task_base import Task

logger = logging.getLogger(__name__)

_DEFAULT_EXTRACTOR_MAP = {
    "pdf": "pymupdf",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "html": "beautifulsoup",
    "xml": "lxml",
    "excel": "openpyxl",
    "csv": "pandas",
    "parquet": "pandas",
}


class ExtractTaskSchema(BaseModel):
    document_type: str
    extract_method: str = None  # Initially allow None to set a smart default
    extract_text: bool = (True,)
    extract_images: bool = (True,)
    extract_tables: bool = False

    @root_validator(pre=True)
    def set_default_extract_method(cls, values):
        document_type = values.get("document_type", "").lower()  # Ensure case-insensitive comparison
        extract_method = values.get("extract_method")

        if document_type not in _DEFAULT_EXTRACTOR_MAP:
            raise ValueError(
                f"Unsupported document type: {document_type}. Supported types are: {list(_DEFAULT_EXTRACTOR_MAP.keys())}"
            )

        if extract_method is None:
            values["extract_method"] = _DEFAULT_EXTRACTOR_MAP[document_type]
        return values

    @validator("extract_method")
    def extract_method_must_be_valid(cls, v, values, **kwargs):
        valid_methods = set(_DEFAULT_EXTRACTOR_MAP.values())
        if v not in valid_methods:
            raise ValueError(f"extract_method must be one of {valid_methods}")
        return v

    @validator("document_type")
    def document_type_must_be_supported(cls, v):
        if v.lower() not in _DEFAULT_EXTRACTOR_MAP:
            raise ValueError(
                f"Unsupported document type '{v}'. Supported types are: {', '.join(_DEFAULT_EXTRACTOR_MAP.keys())}"
            )
        return v.lower()

    class Config:
        extra = "forbid"


class ExtractTask(Task):
    """
    Object for document extraction task
    """

    _Type_Extract_Method_PDF = Literal[
        "pymupdf",
        "haystack",
        "tika",
        "unstructured_local",
        "unstructured_service",
        "llama_parse",
    ]

    _Type_Extract_Method_DOCX = Literal["python-docx", "haystack", "unstructured_local", "unstructured_service"]

    def __init__(
        self,
        document_type,
        extract_method: _Type_Extract_Method_PDF = "pymupdf",
        extract_text: bool = False,
        extract_images: bool = False,
        extract_tables: bool = False,
        text_depth: str = "document",
    ) -> None:
        """
        Setup Extract Task Config
        """
        super().__init__()

        self._document_type = document_type
        self._extract_images = extract_images
        self._extract_method = extract_method
        self._extract_tables = extract_tables
        self._extract_text = extract_text
        self._text_depth = "document"

    def __str__(self) -> str:
        """
        Returns a string with the object's config and run time state
        """
        info = ""
        info += "Extract Task:\n"
        info += f"  document type: {self._document_type}\n"
        info += f"  extract method: {self._extract_method}\n"
        info += f"  extract text: {self._extract_text}\n"
        info += f"  extract images: {self._extract_images}\n"
        info += f"  extract tables: {self._extract_tables}\n"
        info += f"  text depth: {self._text_depth}\n"
        return info

    def to_dict(self) -> Dict:
        """
        Convert to a dict for submission to redis (fixme)
        """
        extract_params = {
            "extract_text": self._extract_text,
            "extract_images": self._extract_images,
            "extract_tables": self._extract_tables,
            "text_depth": self._text_depth,
        }

        task_properties = {
            "method": self._extract_method,
            "document_type": self._document_type,
            "params": extract_params,
        }

        # TODO(Devin): I like the idea of Derived classes augmenting the to_dict method, but its not logically
        #  consistent with how we define tasks, we don't have multiple extract tasks, we have extraction paths based on
        #  the method and the document type.
        if self._extract_method == "unstructured_local":
            unstructured_properties = {
                "api_key": "",  # TODO(Devin): Should be an environment variable or configurable parameter
                "unstructured_url": "",  # TODO(Devin): Should be an environment variable
            }
            task_properties["params"].update(unstructured_properties)

        return {"type": "extract", "task_properties": task_properties}