#!/usr/bin/python3

import os
import ssl
import time
import sys
import shutil
import docker
from datetime import datetime, timezone
import json
import http.server

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
    influxdb_client : InfluxDBClient = None


from rtue_worker_thread import rtue
from jammer_worker_thread import jammer
from sniffer_worker_thread import sniffer
from decoder_worker_thread import decoder
from llm_worker_thread import llm_worker
from rach_worker_thread import rach_agent
from ofh_worker_thread import ofh


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

    process_metadata: List[Dict[str, Any]] = []
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

        process_handle = process_class(Config.influxdb_client, Config.docker_client)
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

        process_handle.start(process_config)

    for obj in process_metadata:
        logging.debug(f"{obj['id']} {obj['token']}")
    return process_metadata

class SystemControlHandler(http.server.SimpleHTTPRequestHandler):
    def _get_permissions(self):
        global process_metadata
        is_valid_token = False
        permissions = []
        auth_header = self.headers.get("Authorization")
        if not auth_header.startswith("Bearer "):
            return False, []
        token = auth_header.removeprefix("Bearer").strip()
        for process_config in process_metadata:
            for existing_tok in process_config["token"].keys():
                is_valid_token = existing_tok == token
                if is_valid_token:
                    permissions = process_config["token"][token]
                    break
            if is_valid_token:
                break
        return is_valid_token, permissions

    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def _send_unauthorized(self):
        self._set_headers(401)
        self.wfile.write(json.dumps({"error":"Unauthorized"}).encode("utf-8"))

    def _send_nonexistent(self):
        self._set_headers(404)
        self.wfile.write(json.dumps({"error":"Endpoint not found"}).encode("utf-8"))

    def get_components(self):
        global process_metadata
        is_valid_token, perms = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        response_list = []
        for process_config in process_metadata:
            if process_config["type"] not in perms:
                continue
            response_list.append({
                "id": process_config["id"],
                "type": process_config["type"],
                "config_file": process_config["config"]["config_file"],
                "permissions": process_config["config"]["permissions"]
            })
        self._set_headers()
        self.wfile.write(json.dumps({"running": response_list}).encode("utf-8"))

    def get_component_logs(self):
        is_valid_token, perms = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        try:
            payload = json.loads(post_data)
        except json.JSONDecodeError:
            self._set_headers(403)
            self.wfile.write(json.dumps({"error":"malformed request"}).encode("utf-8"))
            return

        if not all(k in payload for k in ("id", "type")):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing required fields: id, type"}).encode("utf-8"))
                return

        influx_bucket = "rtusystem"
        influx_id = payload["id"]
        global controller_init_time

        query = f'''
            from(bucket: "{influx_bucket}")
            |> range(start: {controller_init_time})
            |> filter(fn: (r) => r._measurement == "component_log")
            |> filter(fn: (r) => r["id"] == "{influx_id}")
            |> filter(fn: (r) => r._field == "stdout_log")
            |> sort(columns: ["_time"])
        '''

        query_api = Config.influxdb_client.query_api()
        result = query_api.query(org=Config.influxdb_client.org, query=query)

        logs = []
        for table in result:
            for record in table.records:
                logs.append({
                    "time": record.get_time().isoformat(),
                    "message": record.get_value()
                })

        self._set_headers()
        self.wfile.write(json.dumps({"logs":logs}).encode("utf-8"))


    def start_component(self):
        global process_metadata
        is_valid_token, perms = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        try:
            payload = json.loads(post_data)
        except json.JSONDecodeError:
            self._set_headers(403)
            self.wfile.write(json.dumps({"error":"malformed request"}).encode("utf-8"))
            return

        logging.debug(f"{payload.keys()}")
        if not all(k in payload for k in ("id", "type", "config_str", "rf")):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing required fields: id, type, config_str, rf"}).encode("utf-8"))
                return

        if not all(k in payload["rf"] for k in ("images_dir", "type")):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing required fields for rf: type, images_dir"}).encode("utf-8"))
                return

        if any(p["id"] == payload["id"] for p in process_metadata):
                self._set_headers(409)
                self.wfile.write(json.dumps({"error": "ID conflict with existing component"}).encode("utf-8"))
                return

        if not os.path.isdir("/host/.generated/"):
            os.makedirs("/host/.generated", exist_ok=True)

        file_ext = {
            "rtue": "conf",
            "sniffer": "toml"
        }.get(payload["type"], "yaml")

        config_file = f"/host/.generated/{payload['id']}.{file_ext}"

        try:
            with open(config_file, "w") as f:
                f.write(payload["config_str"])
        except IOError as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error":f"Failed to write config to file {config_file}"}))
            return

        # NOTE: config path must be translated to the host path
        config_file = config_file.replace("/host", os.getenv("DOCKER_SYSTEM_DIRECTORY"))
        logging.debug(f"Starting component with filename on host {config_file}")

        process_class = None
        try:
            process_class = globals()[payload["type"]]
        except KeyError:
            self._set_headers(403)
            self.wfile.write(json.dumps({"error":f"Invalid process type {payload['type']}"}).encode("utf-8"))
            return

        process_handle = process_class(Config.influxdb_client, Config.docker_client)

        new_process_config = {
            "config_file": config_file,
            "id": payload["id"],
            "type": payload["type"],
            "rf": payload["rf"],
            "permissions": [],
        }

        process_metadata.append({
            'id': payload['id'],
            'type': payload['type'],
            'config': new_process_config,
            'handle': process_handle,
            'token': {None: []}
        })
        process_handle.start(new_process_config)

        self._set_headers()
        self.wfile.write(json.dumps({"msg":f"process started: {payload['id']}"}).encode("utf-8"))

    def stop_component(self):
        global process_metadata
        is_valid_token, perms = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        try:
            payload = json.loads(post_data)
        except json.JSONDecodeError:
            self._send_unauthorized()
            return

        if "id" not in payload.keys():
            self._set_headers(400)
            self.wfile.write(json.dumps({"error":"Missing required field id"}).encode("utf-8"))
            return

        for i, process_config in enumerate(process_metadata):
            if process_config["id"] == payload["id"]:
                if process_config["type"] not in perms:
                    continue
                process_config["handle"].stop()
                self._set_headers()
                self.wfile.write(json.dumps({"id":process_config["id"]}).encode("utf-8"))
                del process_metadata[i]
                return
        self._set_headers(404)
        self.wfile.write(json.dumps({"error":"Component with ID does not exist"}).encode("utf-8"))


    def do_GET(self):
        if self.path.startswith("/list"):
            self.get_components()
        else:
            self._send_nonexistent()

    def do_POST(self):
        if self.path.startswith("/start"):
            self.start_component()
        elif self.path.startswith("/stop"):
            self.stop_component()
        elif self.path.startswith("/logs"):
            self.get_component_logs()
        else:
            self._send_nonexistent()


if __name__ == '__main__':
    global controller_init_time
    controller_init_time = f"{datetime.now().astimezone(timezone.utc)
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

    global process_list
    process_list = []

    configure()
    global process_metadata
    process_metadata = start_subprocess_threads()

    server = http.server.HTTPServer((control_ip, control_port), SystemControlHandler)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile="/server.pem", keyfile="/server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)

    logging.debug(f"control API setup on https://{control_ip}:{control_port}")

    server.serve_forever()
