#!/usr/bin/python3

import os
import time
import sys
import shutil
from datetime import datetime

import uuid
import argparse
import pathlib
import yaml
import logging
from typing import List, Dict, Union

# Configuration data class
from Config import Config

# UE subprocess manager
from Ue import Ue


logger = logging.getLogger(__name__)


def configure() -> None:
    """
    Reads in CLI arguments
    Parses YAML config
    Configures logging
    """
    script_dir = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Run an srsRAN gNB and Open5GS, then send metrics to the ue_controller")
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        required=True,
        help="Path of YAML config for the controller")
    parser.add_argument("--log-level",
                    default="DEBUG",
                    help="Set the logging level. Options: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    parser.add_argument("--docker",
                    type=bool,
                    default=False,
                    help="Start all processes as docker containers")
    args = parser.parse_args()
    Config.log_level = getattr(logging, args.log_level.upper(), 1)

    if not isinstance(Config.log_level, int):
        raise ValueError(f"Invalid log level: {args.log_level}")

    logging.basicConfig(level=Config.log_level,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("selectors").setLevel(logging.WARNING)

    Config.filename = args.config
    Config.enable_docker = args.docker
    with open(str(args.config), 'r') as file:
        Config.options = yaml.safe_load(file)


def kill_existing(process_names : List[str]) -> None:
    """
    Finds and kills any stray processes that might interfere with the system
    """
    for name in process_names:
        os.system("kill -9 $(ps aux | awk '/{" + name + "}/{print $2}')")

def start_processes() -> List[Dict[str, Union[str, Ue, int]]]:
    """
    Starts any necessary processes using Config
    Starts ping and iperf if specified
    """
    process_list: List[Dict[str, Union[str, Ue, int]]] = []

    ue_index = 1

    if Config.options is None:
        raise ValueError("Config.options is None. Please check the configuration.")


    for process_config in Config.options.get("processes", []):
        if process_config["type"] == "srsue":
            new_ue = Ue(Config.enable_docker, ue_index)
            if "args" in process_config.keys():
                new_ue.start([process_config["config_file"]] + process_config["args"].split(" "))
            else:
                new_ue.start([process_config["config_file"]])
            process_list.append({
                'id': str(uuid.uuid4()),
                'type': process_config['type'],
                'config': process_config['config_file'],
                'handle': new_ue,
                'index': ue_index
            })
            ue_index += 1
            logger.debug(f"STARTED: {new_ue}")

    return process_list

def await_children(export_params) -> None:
    """
    Wait for all child processes to stop
    """
    export_data = False
    export_path = None

    # Handle export parameters
    if export_params:
        export_dir = pathlib.Path(export_params["output_directory"])
        if not export_dir.exists():
            raise ValueError(f"Directory does not exist: {export_dir}")
        export_data = True
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Format: YYYYMMDD_HHMMSS
        export_path = export_dir / f"test_run_{timestamp}"
        export_path.mkdir(parents=True, exist_ok=True)

    process_running = True
    while process_running:
        process_running = False
        for process in process_list:
            if process["handle"].isRunning:
                process_running = True

            if export_data:
                for filename, output in process["handle"].get_unwritten_output().items():
                    file_path = export_path / f"{filename}.csv"
                    with file_path.open("a") as f:
                        f.write("\n" + '\n'.join(output))

                # Export main output
                output_filename = export_path / process["handle"].get_output_filename()
                with output_filename.open("a") as f:
                    f.write("\n" + '\n'.join(process["handle"].output))
                process["handle"].output = []
                for pcap_key, pcap_file in process["handle"].pcap_data.items():
                    if pcap_file:
                        pcap_path = pathlib.Path(pcap_file)
                        if pcap_path.is_file():
                            target_file = export_path / pcap_path.name
                            shutil.copy(pcap_path, target_file)


                if process["handle"].metrics_client.file_path:
                    target_file = export_path / f"metrics_ue{process['handle'].ue_index}.csv" 
                    try:
                        shutil.copy(process["handle"].metrics_client.file_path, target_file)
                    except FileNotFoundError as e:
                        logging.error(f"UE metrics file {process['handle'].metrics_client.file_path} not found")
        time.sleep(1)


if __name__ == '__main__':
    if os.geteuid() != 0:
        logger.error("The Soft-T-UE controller must be run as root. Exiting.")
        sys.exit(1)

    kill_existing(["srsue", "gnb", "iperf3"])
    configure()

    process_list = start_processes()

    export_params = Config.options.get("data_export", False)

    await_children(export_params)



