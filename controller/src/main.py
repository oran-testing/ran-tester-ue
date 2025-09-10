#!/usr/bin/python3

import os
import http
import ssl
import time
import sys
import shutil
import docker
from datetime import datetime, timezone

import uuid
import argparse
import pathlib
import yaml
import logging
import signal

from rtue_worker_thread import rtue
from jammer_worker_thread import jammer
from sniffer_worker_thread import sniffer
from decoder_worker_thread import decoder
from llm_worker_thread import llm_worker
from rach_worker_thread import rach_agent
from ofh_worker_thread import ofh

from influxdb_client import InfluxDBClient, WriteApi

from control_handler import SystemControlHandler
from globals import Config, Globals


def handle_signal(signum, frame):
    for process_meta in Globals.process_metadata:
        process_meta["handle"].stop()
        logging.debug(f"Killed process {process['id']}")
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
        description="RAN tester UE process controller")
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
                    format='%(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

    Config.filename = args.config
    with open(str(args.config), 'r') as file:
        Config.options = yaml.safe_load(file)


def start_subprocess_threads():
    """
    Creates one central influxDB client
    Creates one central docker client
    Starts any necessary subprocess threads using Config
    Returns a list of metadata for each thread
    """
    if Config.options is None:
        logging.error("Config is None: parsing failed... Exiting")
        sys.exit(1)

    influxdb_host = os.getenv("DOCKER_INFLUXDB_INIT_HOST")
    influxdb_port = os.getenv("DOCKER_INFLUXDB_INIT_PORT")
    influxdb_org = os.getenv("DOCKER_INFLUXDB_INIT_ORG")
    influxdb_token = os.getenv("DOCKER_INFLUXDB_INIT_ADMIN_TOKEN")

    logging.debug(f"DOCKER_INFLUXDB_INIT_HOST: {influxdb_host}")
    logging.debug(f"DOCKER_INFLUXDB_INIT_PORT: {influxdb_port}")
    logging.debug(f"DOCKER_INFLUXDB_INIT_ORG: {influxdb_org}")

    if not influxdb_host or not influxdb_port or not influxdb_org or not influxdb_token:
        raise RuntimeError("Influxdb environment is not complete! Ensure .env is configured and passed properly")

    Config.influxdb_client = InfluxDBClient(
        f"http://{influxdb_host}:{influxdb_port}",
        org=influxdb_org,
        token=influxdb_token
    )

    Config.docker_client = docker.from_env()

    process_metadata = []
    process_ids = []
    for process_config in Config.options.get("processes", []):

        if "id" not in process_config.keys():
            raise RuntimeError("id field required for each process")

        if "type" not in process_config.keys():
            raise RuntimeError("type field required for each process")

        if "config_file" not in process_config.keys():
            raise RuntimeError("config_file field required for each process")

        process_config["config_file"] = os.path.join("/host",process_config["config_file"])
        if not os.path.exists(process_config["config_file"]):
            logging.warning(f"File {process_config['config_file']} not found searching root")
            config_basename = process_config["config_file"].split("/")[-1]
            found = False
            for root, _, files in os.walk("/host"):
                if config_basename in files:
                    process_config["config_file"] = os.path.join(root, config_basename)
                    logging.info(f"Found config file {process_config['config_file']}")
                    found = True
                    break
            if not found:
                raise RuntimeError(f"config file {process_config['config_file']} not found")
        process_config["config_file"] = process_config["config_file"].replace("/host", os.getenv("DOCKER_SYSTEM_DIRECTORY"))
        logging.debug(f"Filename on host {process_config['config_file']}")


        if "depends_on" in process_config.keys():
            depends_on_list = list(process_config["depends_on"])
            for dependency in depends_on_list:
                found_dep = False
                for process_data in process_metadata:
                    if process_data["id"] == dependency:
                        found_dep = True
                if not found_dep:
                    raise RuntimeError(f"Did not find dependent process '{dependency}' for '{process_config['id']}'")

        if "sleep_ms" in process_config.keys():
            logging.debug(f"Sleeping for {process_config['sleep_ms']}")
            sleep_time = float(process_config["sleep_ms"])/1000.0
            time.sleep(sleep_time)

        permissions = []
        if "permissions" in process_config.keys():
            permissions = process_config["permissions"]
        process_config["permissions"] = permissions

        process_class = None
        try:
            process_class = globals()[process_config["type"]]
        except KeyError:
            raise RuntimeError(f"Invalid process type {process_config['type']}")

        process_handle = process_class(Config.influxdb_client, Config.docker_client, process_config)
        process_token = None
        if hasattr(process_handle, "get_token"):
            process_token = process_handle.get_token()

        process_metadata.append({
            'id': process_config['id'],
            'type': process_config['type'],
            'config': process_config,
            'handle': process_handle,
            'token': {process_token: permissions}
        })

        process_handle.start()

    for obj in process_metadata:
        logging.debug(f"{obj['id']} {obj['token']}")
    return process_metadata



if __name__ == '__main__':
    Globals.controller_init_time = f"{datetime.now().astimezone(timezone.utc)
        .isoformat().replace("+00:00", "Z")}"

    if os.geteuid() != 0:
        logging.error("The RAN Tester UE controller must be run as root.")
        sys.exit(1)

    control_ip = os.getenv("DOCKER_CONTROLLER_API_IP", None)
    if not control_ip:
        raise RuntimeError("environment variable DOCKER_CONTROLLER_API_IP not set")
        sys.exit(1)

    control_port = os.getenv("DOCKER_CONTROLLER_API_PORT", None)
    if not control_port:
        raise RuntimeError("environment variable DOCKER_CONTROLLER_API_PORT not set")
        sys.exit(1)
    try:
        control_port = int(control_port)
    except RuntimeError:
        raise RuntimeError("DOCKER_CONTROLLER_API_PORT is not a valid integer")


    configure()
    Globals.process_metadata = start_subprocess_threads()

    server = http.server.HTTPServer((control_ip, control_port), SystemControlHandler)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile="/server.pem", keyfile="/server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)

    logging.debug(f"control API setup on https://{control_ip}:{control_port}")

    server.serve_forever()
