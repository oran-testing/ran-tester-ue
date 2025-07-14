#!/usr/bin/python3

import os
import time
import sys
import shutil
import docker
from datetime import datetime
import websockets

import uuid
import argparse
import pathlib
import yaml
import logging
import signal
from typing import List, Dict, Union, Optional, Any


from fastapi import FastAPI
from pydantic import BaseModel
import threading
import requests
import uvicorn
import time


from influxdb_client import InfluxDBClient, WriteApi


async def ws_handler(ws, path):
    """
    Handles both text logs and binary file uploads.
    Path will be '/llm' or '/jammer' depending on who connects. 
    """
    client = path.lstrip("/")  # e.g. "llm"
    logging.info(f"[WS] {client} connected")

    try:
        async for msg in ws:
            if isinstance(msg, bytes):
                # Binary file received
                fn = f"/tmp/{client}_llm_output.txt"
                with open(fn, "wb") as f:
                    f.write(msg)
                logging.info(f"[WS] Saved binary file to {fn}")
                await ws.send("FILE RECEIVED")
            else:
                # Text log line
                logging.info(f"[WS] ←{client}: {msg}")
                await ws.send("ACK")
    except websockets.ConnectionClosed:
        logging.info(f"[WS] {client} disconnected")

async def ws_serve():
    # listen on 0.0.0.0:8000, handle /llm and /jammer
    await websockets.serve(ws_handler, "0.0.0.0", 8000)
    await asyncio.Future()  # run forever

def start_ws_thread():
    asyncio.run(websockets.serve(ws_handler, "0.0.0.0", 8000))

class Config:
    filename : str = ""
    options : Optional[Dict[str,Any]] = None
    log_level : int = logging.DEBUG
    docker_client = None

from rtue_worker_thread import rtue
from jammer_worker_thread import jammer
from sniffer_worker_thread import sniffer
from decoder_worker_thread import decoder
from llm_worker_thread import llm_config
from rach_worker_thread import rach_agent



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

    influxdb_client = InfluxDBClient(
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

        process_class = None
        try:
            process_class = globals()[process_config["type"]]
        except KeyError:
            raise RuntimeError(f"Invalid process type {process_config['type']}")

        logging.debug("USING CONFIG: {process_config['config_file']}")
        process_handle = process_class(influxdb_client, Config.docker_client)

        process_metadata.append({
            'id': process_config['id'],
            'type': process_config['type'],
            'config': process_config,
            'handle': process_handle,
        })

        process_handle.start(process_config)

    return process_metadata

def send_to_llm_worker():
    url = "http://llm_worker:8000/message"
    payload = {
        "sender": "controller",
        "content": "Hello from controller"
    }

    try:
        r = requests.post(url, json=payload)
        print("Response from llm_worker:", r.json())
    except Exception as e:
        print("Error contacting llm_worker:", e)


app = FastAPI()

class Message(BaseModel):
    sender: str
    content: str

@app.post("/from-worker")
async def receive_response(msg: Message):
    print(f"[Controller] Received from {msg.sender}: {msg.content}")
    return {"status": "controller received"}

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=9000)


if __name__ == '__main__':

    if os.geteuid() != 0:
        logging.error("The RAN Tester UE controller must be run as root.")
        sys.exit(1)

    global process_list
    process_list = []

    configure()
    global process_metadata
    process_metadata = start_subprocess_threads()

    # Start the REST API server in a daemon thread for receiving 1 response from llm_worker
    threading.Thread(target=run_api, daemon=True).start()

    # Start the WebSocket server in a daemon thread
    threading.Thread(target=start_ws_thread, daemon=True).start()

    send_to_llm_worker()

    while True:
        time.sleep(1)