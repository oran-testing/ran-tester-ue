#!/usr/bin/python3

import os
import time
import sys
import shutil
import docker
from datetime import datetime

import uuid
import argparse
import pathlib
import yaml
import logging
import signal
from typing import List, Dict, Union, Optional, Any

from influxdb_client import InfluxDBClient, WriteApi

class Config:
    filename : str = ""
    options : Optional[Dict[str,Any]] = None
    log_level : int = logging.DEBUG

# srsue worker thread class
from srsue_worker_thread import srsue



def handle_signal(signum, frame):
    global process_list
    for process in process_list:
        process["handle"].stop()
        logging.debug(f"Killed process {process['id']}")
    process_list= []
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


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
    args = parser.parse_args()
    Config.log_level = getattr(logging, args.log_level.upper(), 1)

    if not isinstance(Config.log_level, int):
        raise ValueError(f"Invalid log level: {args.log_level}")

    logging.basicConfig(level=Config.log_level,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

    Config.filename = args.config
    with open(str(args.config), 'r') as file:
        Config.options = yaml.safe_load(file)


def kill_existing(process_names : List[str]) -> None:
    """
    Finds and kills any stray processes that might interfere with the system
    """
    for name in process_names:
        os.system("kill -9 $(ps aux | awk '/" + name + "/{print $2}')")

def start_subprocess_threads() -> List[Dict[str, Any]]:
    """
    Creates one central influxDB client
    Creates one central docker client
    Starts any necessary subprocess threads using Config
    Returns a list of metadata for each thread
    """

    if Config.options is None:
        logging.error("Config is None: parsing failed... Exiting")
        sys.exit(1)

    influxdb_config = Config.options.get("influxdb", {})


    influxdb_host, influxdb_port, influxdb_org, influxdb_token = "NO_HOST", 8086, "NO_ORG", "NO_TOKEN"
    try:
        influxdb_host = os.path.expandvars(influxdb_config["influxdb_host"])
        influxdb_port = os.path.expandvars(influxdb_config["influxdb_port"])
        influxdb_org = os.path.expandvars(influxdb_config["influxdb_org"])
        influxdb_token = os.path.expandvars(influxdb_config["influxdb_token"])

    except (KeyError, ValueError) as e:
        print(f"Influxdb Configuration Error: {e}")

    logging.debug(f"{influxdb_token} : {influxdb_org} : TEST {os.path.expandvars("${DOCKER_INFLUXDB_INIT_HOST}")}")

    influxdb_client = InfluxDBClient(
        f"http://{influxdb_host}:{influxdb_port}",
        org=influxdb_org,
        token=influxdb_token
    )

    docker_client = docker.from_env()

    process_metadata: List[Dict[str, Any]] = []

    for process_config in Config.options.get("processes", []):
        process_class = None
        try:
            process_class = globals()[process_config["type"]]
        except KeyError:
            logging.error(f"Invalid process type: {process_type}")
            continue

        process_handle = process_class(influxdb_client, docker_client)

        process_handle.start(
            config=process_config["config_file"] if "config_file" in process_config.keys() else "",
            args=process_config["args"].split(" ") if "args" in process_config.keys() else []
        )

        process_metadata.append({
            'id': str(uuid.uuid4()),
            'type': process_config['type'],
            'config': process_config,
            'handle': process_handle,
        })

    return process_metadata

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
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M,%S")
        export_path = export_dir / f"soft_t_ue_run_{timestamp}"
        export_path.mkdir(parents=True, exist_ok=True)

    process_running = True
    while process_running:
        process_running = False
        for process in process_list:
            if process["handle"].isRunning:
                process_running = True

        time.sleep(1)


if __name__ == '__main__':
    if os.geteuid() != 0:
        logging.error("The Soft-T-UE controller must be run as root. Exiting.")
        sys.exit(1)

    global process_list
    process_list = []

    kill_existing(["srsue", "gnb"])
    configure()

    global process_metadata
    process_metadata = start_subprocess_threads()

    export_params = Config.options.get("data_export", False)

    await_children(export_params)
    sys.exit(0)



