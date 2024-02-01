# Copyright (c) 2023-2024, NVIDIA CORPORATION.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import time
import typing

from morpheus.config import Config
from morpheus.messages import ControlMessage
from morpheus.pipeline.pipeline import Pipeline
from morpheus.stages.general.linear_modules_source import LinearModuleSourceStage
from morpheus.stages.general.linear_modules_stage import LinearModulesStage

from morpheus_pdf_ingest.modules.file_source_pipe import FileSourcePipeLoaderFactory
from morpheus_pdf_ingest.modules.nemo_doc_splitter import NemoDocSplitterLoaderFactory
from morpheus_pdf_ingest.modules.redis_subscriber_source import RedisSubscriberSourceLoaderFactory
from morpheus_pdf_ingest.modules.redis_task_sink import RedisTaskSinkLoaderFactory

logger = logging.getLogger(__name__)

CONNECTION_TRACKER = {}

file_sources = [
    './data/pdf_ingest_testing/*.pdf',
]

_source_config = [{
    'type': 'filesystem',
    'name': 'filesystem-test',
    'config': {
        "batch_size": 1,
        "enable_monitor": True,
        "extractor_config": {
            "chunk_size": 512,
            "num_threads": 1,
        },
        "filenames": file_sources,
        "vdb_resource_name": "pdf_ingest_testing"
    }
}]


def validate_source_config(source_info: typing.Dict[str, any]) -> None:
    """
    Validates the configuration of a source.

    This function checks whether the given source configuration dictionary
    contains all required keys: 'type', 'name', and 'config'.

    Parameters
    ----------
    source_info : typing.Dict[str, any]
        The source configuration dictionary to validate.

    Raises
    ------
    ValueError
        If any of the required keys ('type', 'name', 'config') are missing
        in the source configuration.
    """
    if ('type' not in source_info or 'name' not in source_info or 'config' not in source_info):
        raise ValueError(f"Each source must have 'type', 'name', and 'config':\n {source_info}")


def setup_filesystem_source(pipe: Pipeline, config: Config, source_name: str, fs_config: typing.Dict[str, typing.Any]):
    """
    Set up the filesystem source stage in the pipeline.

    Parameters
    ----------
    pipe : Pipeline
        The pipeline to which the filesystem source stage will be added.
    config : Config
        Configuration object for the pipeline.
    source_name : str
        The name of the filesystem source stage.
    fs_config : typing.Dict[str, Any]
        Configuration parameters for the filesystem source stage.

    Returns
    -------
    SubPipeline
        The sub-pipeline stage created for the filesystem source.
    """

    module_loader = FileSourcePipeLoaderFactory.get_instance(module_name=f"file_source_pipe__{source_name}",
                                                             module_config={"file_source_config": fs_config})
    file_pipe = pipe.add_stage(
        LinearModuleSourceStage(config, module_loader, output_type=ControlMessage, output_port_name="output"))

    return file_pipe


# TODO: Should have multiple input channels (aka multiple redis sources for different pipelines)
def setup_redis_source(pipe: Pipeline, config: Config):
    source_module_loader = RedisSubscriberSourceLoaderFactory.get_instance(module_name="redis_listener",
                                                                           module_config={
                                                                               "redis_listener": {
                                                                                   "redis_host": "redis",
                                                                               }
                                                                           })

    source_stage = pipe.add_stage(
        LinearModuleSourceStage(config, source_module_loader, output_type=ControlMessage, output_port_name="output"))

    nemo_splitter_loader = NemoDocSplitterLoaderFactory.get_instance(module_name="nemo_doc_splitter",
                                                                     module_config={
                                                                         "split_by": "word",
                                                                         "split_length": 250,
                                                                         "split_overlap": 30,
                                                                         "max_character_length": 1900,
                                                                     })

    nemo_splitter_stage = pipe.add_stage(
        LinearModulesStage(config, nemo_splitter_loader,
                           input_type=ControlMessage,
                           output_type=ControlMessage,
                           input_port_name="input",
                           output_port_name="output"))

    sink_module_loader = RedisTaskSinkLoaderFactory.get_instance(module_name="redis_task_sink",
                                                                 module_config={
                                                                     "redis_host": "redis",
                                                                 })
    sink_stage = pipe.add_stage(
        LinearModulesStage(config, sink_module_loader,
                           input_type=ControlMessage,
                           output_type=ControlMessage,
                           input_port_name="input",
                           output_port_name="output"))

    pipe.add_edge(source_stage, nemo_splitter_stage)
    pipe.add_edge(nemo_splitter_stage, sink_stage)

    return sink_stage


def process_vdb_sources(pipe: Pipeline, config: Config, vdb_source_config: typing.List[typing.Dict]) -> typing.List:
    """
    Processes and sets up sources defined in a vdb_source_config.

    This function reads the source configurations provided in vdb_source_config and
    sets up each source based on its type ('rss', 'filesystem', or 'custom').
    It validates each source configuration and then calls the appropriate setup
    function to add the source to the pipeline.

    Parameters
    ----------
    pipe : Pipeline
        The pipeline to which the sources will be added.
    config : Config
        Configuration object for the pipeline.
    vdb_source_config : List[Dict]
        A list of dictionaries, each containing the configuration for a source.

    Returns
    -------
    list
        A list of the sub-pipeline stages created for each defined source.

    Raises
    ------
    ValueError
        If an unsupported source type is encountered in the configuration.
    """
    vdb_sources = []
    for source_info in vdb_source_config:
        validate_source_config(source_info)
        source_type = source_info['type']
        source_name = source_info['name']
        source_config = source_info['config']

        if (source_type == 'filesystem'):
            vdb_sources.append(setup_filesystem_source(pipe, config, source_name, source_config))
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    return vdb_sources


def pipeline(pipeline_config: Config) -> float:
    logging.info("Starting pipeline setup")

    pipe = Pipeline(pipeline_config)
    start_abs = time.clock_gettime_ns(time.CLOCK_MONOTONIC)

    # vdb_sources = process_vdb_sources(pipe, pipeline_config, _source_config)
    # cm_sink = pipe.add_stage(InMemorySinkStage(pipeline_config))

    # Create HTTP source
    setup_redis_source(pipe, pipeline_config)

    # Connect HTTP source

    # for source_output in vdb_sources:
    #    pipe.add_edge(source_output, cm_sink)

    end_setup = start_run = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    setup_elapsed = (end_setup - start_abs) / 1e9
    logging.info(f"Pipeline setup completed in {setup_elapsed:.2f} seconds")

    logging.info("Running pipeline")
    pipe.run()

    end_run = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    run_elapsed = (end_run - start_run) / 1e9
    total_elapsed = (end_run - start_abs) / 1e9

    logging.info(f"Pipeline run completed in {run_elapsed:.2f} seconds")
    logging.info(f"Total time elapsed: {total_elapsed:.2f} seconds")

    return total_elapsed


if (__name__ == "__main__"):
    logging.basicConfig(level=logging.INFO)

    config = Config()
    config.pipeline_batch_size = 1
    config.num_threads = 1
    config.enable_monitor = True

    pipeline(config)
