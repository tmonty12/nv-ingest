# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import logging

from pydantic import BaseModel

from nv_ingest.schemas.metadata_schema import ContentMetadataSchema
from nv_ingest.schemas.metadata_schema import ErrorMetadataSchema
from nv_ingest.schemas.metadata_schema import ImageMetadataSchema
from nv_ingest.schemas.metadata_schema import SourceMetadataSchema
from nv_ingest.schemas.metadata_schema import TextMetadataSchema

logger = logging.getLogger(__name__)


class PDFExtractorSchema(BaseModel):
    n_workers: int = 16
    max_queue_size: int = 1
    raise_on_failure: bool = False

    class Config:
        extra = "forbid"
