# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# pylint: skip-file

import base64
from io import BytesIO
import logging
import time
import traceback
from typing import Annotated
import uuid

from nv_ingest_client.primitives.jobs.job_spec import JobSpec
from fastapi import File, UploadFile, Form
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from nv_ingest_client.primitives.tasks.extract import ExtractTask

from nv_ingest.service.impl.ingest.redis_ingest_service import RedisIngestService
from nv_ingest.service.meta.ingest.ingest_service_meta import IngestServiceMeta

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_ingest_service() -> IngestServiceMeta:
    """
    Gather the appropriate Ingestion Service to use for the nv-ingest endpoint.
    """
    logger.debug("Creating RedisIngestService singleton for dependency injection")
    return RedisIngestService.getInstance()


INGEST_SERVICE_T = Annotated[IngestServiceMeta, Depends(_get_ingest_service)]


# POST /submit
@router.post(
    "/submit",
    responses={
        200: {"description": "Submission was successful"},
        500: {"description": "Error encountered during submission"},
    },
    tags=["Ingestion"],
    summary="submit document to the core nv ingestion service for processing",
    operation_id="submit",
)
async def submit_job_curl_friendly(
    ingest_service: INGEST_SERVICE_T,
    file: UploadFile = File(...)
):
    """
    A multipart/form-data friendly Job submission endpoint that makes interacting with
    the nv-ingest service through tools like Curl easier.
    """
    try:
        print(f"Creating JobSpec from multipart/form-data file: {file}")
        print(f"File size: {file.size}")
        file_stream = BytesIO(file.file.read())
        pdf_content = base64.b64encode(file_stream.read()).decode("utf-8")
        # Construct the JobSpec from the HTTP supplied form-data
        job_spec = JobSpec(
            job_id=str(uuid.uuid4()),
            # document_type=file.content_type,
            document_type="pdf",
            payload=pdf_content,
            source_id=file.filename,
            source_name=file.filename,
            # TODO: Update this to accept user defined options
            extended_options={"tracing_options": {"trace": True, "ts_send": time.time_ns()}}
        )

        extract_task = ExtractTask(
            document_type="pdf",
            extract_text=True,
            extract_images=True,
            extract_tables=True
        )

        job_spec.add_task(extract_task)

        print(f"Created JobSpec instance: {job_spec}")
        submitted_job_id = await ingest_service.submit_job(job_spec)
        return submitted_job_id
    except Exception as ex:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Nv-Ingest Internal Server Error: {str(ex)}")


# POST /submit_job
@router.post(
    "/submit_job",
    responses={
        200: {"description": "Jobs were successfully submitted"},
        500: {"description": "Error encountered while submitting jobs."},
        503: {"description": "Service unavailable."},
    },
    tags=["Ingestion"],
    summary="submit jobs to the core nv ingestion service for processing",
    operation_id="submit_job",
)
async def submit_job(job_spec: JobSpec, ingest_service: INGEST_SERVICE_T):
    try:
        submitted_job_id = await ingest_service.submit_job(job_spec)
        return submitted_job_id
    except Exception as ex:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Nv-Ingest Internal Server Error: {str(ex)}")


# GET /fetch_job
@router.get(
    "/fetch_job/{job_id}",
    responses={
        200: {"description": "Job was succesfully retrieved."},
        500: {"description": "Error encountered while fetching job."},
        503: {"description": "Service unavailable."},
    },
    tags=["Ingestion"],
    summary="Fetch a previously submitted job from the ingestion service by providing its job_id",
    operation_id="fetch_job",
)
async def fetch_job(job_id: str, ingest_service: INGEST_SERVICE_T):
    try:
        job_response = await ingest_service.fetch_job(job_id)
        return job_response
    except Exception as ex:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Nv-Ingest Internal Server Error: {str(ex)}")
