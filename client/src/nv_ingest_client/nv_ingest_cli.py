# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import json
import logging
import time
from io import BytesIO
from typing import List

import click
from nv_ingest_client.cli.util.click import ClientType
from nv_ingest_client.cli.util.click import LogLevel
from nv_ingest_client.cli.util.click import click_match_and_validate_files
from nv_ingest_client.cli.util.click import click_validate_batch_size
from nv_ingest_client.cli.util.click import click_validate_file_exists
from nv_ingest_client.cli.util.click import click_validate_task
from nv_ingest_client.cli.util.dataset import get_dataset_files
from nv_ingest_client.cli.util.dataset import get_dataset_statistics
from nv_ingest_client.cli.util.processing import create_and_process_jobs
from nv_ingest_client.cli.util.processing import report_statistics
from nv_ingest_client.cli.util.system import configure_logging
from nv_ingest_client.cli.util.system import ensure_directory_with_permissions
from nv_ingest_client.client import NvIngestClient
from nv_ingest_client.message_clients.redis import RedisClient

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--batch_size",
    default=10,
    show_default=True,
    type=int,
    help="Batch size (must be >= 1).",
    callback=click_validate_batch_size,
)
@click.option(
    "--doc",
    multiple=True,
    default=[],
    type=click.Path(exists=False),
    help="Add a new document to be processed (supports multiple).",
    callback=click_match_and_validate_files,
)
@click.option(
    "--dataset",
    type=click.Path(exists=False),
    default=None,
    help="Path to a dataset definition file.",
    callback=click_validate_file_exists,
)
@click.option(
    "--client",
    type=click.Choice([client.value for client in ClientType], case_sensitive=False),
    default="REDIS",
    show_default=True,
    help="Client type.",
)
@click.option("--client_host", required=True, help="DNS name or URL for the endpoint.")
@click.option("--client_port", required=True, type=int, help="Port for the client endpoint.")
@click.option("--client_kwargs", help="Additional arguments to pass to the client.", default="{}")
@click.option(
    "--concurrency_n", default=10, show_default=True, type=int, help="Number of inflight jobs to maintain at one time."
)
@click.option("--dry_run", is_flag=True, help="Perform a dry run without executing actions.")
@click.option("--output_directory", type=click.Path(), default=None, help="Output directory for results.")
@click.option(
    "--log_level",
    type=click.Choice([level.value for level in LogLevel], case_sensitive=False),
    default="INFO",
    show_default=True,
    help="Log level.",
)
@click.option(
    "--shuffle_dataset", is_flag=True, default=True, show_default=True, help="Shuffle the dataset before processing."
)
@click.option(
    "--task",
    multiple=True,
    callback=click_validate_task,
    help="""
\b
Task definitions in JSON format, allowing multiple tasks to be configured by repeating this option.
Each task must be specified with its type and corresponding options in the '[task_id]:{json_options}' format.

\b
Example:
  --task 'split:{"split_by":"page", "split_length":10}'
  --task 'extract:{"document_type":"pdf", "extract_text":true}'
  --task 'extract:{"document_type":"docx", "extract_text":true, "extract_images":true}'

\b
Tasks and Options:
- split: Divides documents according to specified criteria.
    Options:
    - split_by (str): Criteria ('page', 'size', 'word', 'sentence'). No default.
    - split_length (int): Segment length. No default.
    - split_overlap (int): Segment overlap. No default.
    - max_character_length (int): Maximum segment character count. No default.
    - sentence_window_size (int): Sentence window size. No default.
\b
- extract: Extracts content from documents, customizable per document type.
    Can be specified multiple times for different 'document_type' values.
    Options:
    - document_type (str): Document format ('pdf', 'docx', 'pptx', 'html', 'xml', 'excel', 'csv', 'parquet'). Required.
    - extract_method (str): Extraction technique. Defaults are smartly chosen based on 'document_type'.
    - extract_text (bool): Enables text extraction. Default: False.
    - extract_images (bool): Enables image extraction. Default: False.
    - extract_tables (bool): Enables table extraction. Default: False.

\b
Note: The 'extract_method' automatically selects the optimal method based on 'document_type' if not explicitly stated.
""",
)
@click.pass_context
def main(
    ctx,
    batch_size: int,
    doc: List[str],
    dataset: str,
    client: str,
    client_host: str,
    client_port: int,
    client_kwargs: str,
    concurrency_n: int,
    dry_run: bool,
    output_directory: str,
    log_level: str,
    shuffle_dataset: bool,
    task: [str],
):
    try:
        configure_logging(logger, log_level)
        logging.debug(f"nv-ingest-cli:params:\n{json.dumps(ctx.params, indent=2, default=repr)}")

        docs = list(doc)
        if dataset:
            dataset = dataset[0]
            logger.info(f"Processing dataset: {dataset}")
            with open(dataset, "rb") as file:
                dataset_bytes = BytesIO(file.read())

            logger.debug(get_dataset_statistics(dataset_bytes))
            docs.extend(get_dataset_files(dataset_bytes, shuffle_dataset))

        logger.info(f"Processing {len(docs)} documents.")
        if output_directory:
            _msg = f"Output will be written to: {output_directory}"
            if dry_run:
                _msg = f"[Dry-Run] {_msg}"
            else:
                ensure_directory_with_permissions(output_directory)

            logger.info(_msg)

        # TODO(Devin): Process config params, have a failure case for unimplemented items.
        if not dry_run:
            logging.debug(
                f"Creating message client: {client} with host: {client_host} and port: {client_port} -> {client_kwargs}"
            )
            client_allocator = RedisClient

            ingest_client = NvIngestClient(
                message_client_allocator=client_allocator,
                message_client_hostname=client_host,
                message_client_port=client_port,
                message_client_kwargs=json.loads(client_kwargs),
                worker_pool_size=concurrency_n,
            )

            start_time_ns = time.time_ns()
            (total_files, trace_times, pages_processed, total_timeouts) = create_and_process_jobs(
                docs, ingest_client, task, output_directory, batch_size
            )

            report_statistics(start_time_ns, trace_times, pages_processed, total_files, total_timeouts)

    except Exception as err:
        logging.error(f"Error: {err}")
        raise


if __name__ == "__main__":
    main()