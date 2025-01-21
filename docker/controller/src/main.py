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
    docker_client = None

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

    Config.docker_client = docker.from_env()

    process_metadata: List[Dict[str, Any]] = []

    for process_config in Config.options.get("processes", []):
        process_class = None
        try:
            process_class = globals()[process_config["type"]]
        except KeyError:
            logging.error(f"Invalid process type: {process_type}")
            continue

        process_handle = process_class(influxdb_client, Config.docker_client)

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

def backup_metrics() -> None:
    """
    Wait for all child processes to stop
    """

    backup_config = Config.options.get("data_backup", {})

    if not backup_config:
        while True:
            logging.debug("No backup configured")
            time.sleep(100)

    backup_every = int(backup_config["backup_every"]) if "backup_every" in backup_config.keys() else 1000
    backup_dir = backup_config["backup_dir"] if "backup_dir" in backup_config.keys() else "test"
    backup_since = backup_config["backup_since"] if "backup_since" in backup_config.keys() else "-1d"

    influxdb_backup_dir = f"/tmp/host/{backup_dir}/"

    containers = Config.docker_client.containers.list(all=True, filters={"name": "influxdb"})
    logging.debug(str(containers))
    influxdb_container = containers[0]
    if not influxdb_container:
        logging.error("Failed to get influxDB container")
        sys.exit(1)

    influxdb_container.exec_run(f"mkdir -p {influxdb_backup_dir}")
    query = f'from(bucket: "srsran") |> range(start: {backup_since})'

    while True:
        csv_file = f"{influxdb_backup_dir}/backup.csv"
        csv_command = f'influx query "{query}" --raw > {csv_file}'
        exit_code, output = influxdb_container.exec_run(f"sh -c '{csv_command}'", demux=True)
        if exit_code == 0:
            print(f"CSV backup saved to {csv_file}")
        else:
            print(f"Failed to create CSV backup: {output[1].decode()}")
        time.sleep(backup_every)



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

    backup_metrics()
    sys.exit(0)



