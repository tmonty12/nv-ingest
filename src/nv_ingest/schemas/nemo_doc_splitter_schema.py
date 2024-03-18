# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from typing import Literal
from typing import Optional

from pydantic import BaseModel
from pydantic import conint
from pydantic import validator


class DocumentSplitterSchema(BaseModel):
    split_by: Literal["word", "sentence", "passage"] = "word"
    split_length: conint(gt=0) = 60
    split_overlap: conint(ge=0) = 10
    max_character_length: Optional[conint(gt=0)] = 450
    sentence_window_size: Optional[conint(ge=0)] = 0

    @validator("sentence_window_size")
    def check_sentence_window_size(cls, v, values, **kwargs):
        if v is not None and v > 0 and values["split_by"] != "sentence":
            raise ValueError(
                "When using sentence_window_size, split_by must be 'sentence'."
            )
        return v
