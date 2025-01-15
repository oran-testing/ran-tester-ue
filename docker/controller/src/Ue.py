import time
import os
import threading
import asyncio
import uuid
import configparser
import docker
import logging
from datetime import datetime

from Metrics import Metrics

from influxdb_client import InfluxDBClient, WriteApi
from influxdb_client.client.write_api import SYNCHRONOUS

# UE process manager class:
# subprocesses: srsRAN UE, Metrics monitor
#
# Handles all process and data management for one UE
#
# Collects data from UE then sends them to the webui

class Ue:
    def __init__(self):
        self.influxdb_client = InfluxDBClient(
            "http://0.0.0.0:8086",
            org="srs",
            token="605bc59413b7d5457d181ccf20f9fda15693f81b068d70396cc183081b264f3b"
        )
        self.docker_client = docker.from_env()
        self.docker_container = None

        self.ue_config = ""
        self.isRunning = False
        self.isConnected = False
        self.process = None
        self.metrics_client = Metrics(self.send_message)
        self.output = []
        self.rnti = ""

        self.log_buffer = []
        self.ue_command = []

        self.usim_data = {}
        self.pcap_data = {}

    def get_info_from_config(self):
        config = configparser.ConfigParser()
        config.read(self.ue_config)

        self.pcap_data = {
            "mac_filename": config.get("pcap", "mac_filename", fallback=None),
            "mac_nr_filename": config.get("pcap", "mac_nr_filename", fallback=None),
            "nas_filename": config.get("pcap", "nas_filename", fallback=None)
        }

        self.usim_data = {
            "mode": config.get("usim", "mode", fallback=None),
            "algo": config.get("usim", "algo", fallback=None),
            "opc": config.get("usim", "opc", fallback=None),
            "k": config.get("usim", "k", fallback=None),
            "imsi": config.get("usim", "imsi", fallback=None),
            "imei": config.get("usim", "imei", fallback=None)
        }

    def start(self, config_path, args=[]):
        self.ue_config = config_path
        self.get_info_from_config()

        container_name = f"srsran_ue_{str(uuid.uuid4())}"
        environment = {
            "CONFIG": self.ue_config,
            "ARGS": " ".join(args),
        }

        try
            # Check if the container already exists
            # V
            containers = self.docker_client.containers.list(all=True, filters={"ancestor": "srsran/ue"})
            if containers:
                containers[0].stop()
                containers[0].remove()
                logging.debug(f"Removed existing container")
            network_name = "docker_srsue_network"
            self.docker_network = self.docker_client.networks.get(network_name)
            self.docker_container = self.docker_client.containers.run(
                image="srsran/ue",
                name=container_name,
                environment=environment,
                volumes={
                    "/dev/bus/usb/": {"bind": "/dev/bus/usb/", "mode": "rw"},
                    "/usr/share/uhd/images": {"bind": "/usr/share/uhd/images", "mode": "ro"},
                    "/tmp": {"bind": "/tmp", "mode": "rw"}
                },
                privileged=True,
                cap_add=["SYS_NICE", "SYS_PTRACE"],
                network=network_name,
                detach=True,
            )
            logging.debug(f"Started new Docker container {container_name}")


            self.docker_logs = self.docker_container.logs(stream=True, follow=True)
            self.isRunning = True
        except docker.errors.APIError as e:
            logging.error(f"Failed to start Docker container: {e}")

        if self.isRunning:
            self.stop_thread = threading.Event()
            self.log_thread = threading.Thread(target=self.collect_logs, daemon=True)
            self.log_thread.start()



    def send_message(self, message_type, message_text):
        if not message_text or not message_type:
            return

        with self.influxdb_client.write_api(write_options=SYNCHRONOUS) as write_api:
            try:
                utc_timestamp = datetime.utcnow()
                formatted_timestamp = utc_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                self.influx_push(write_api, bucket='srsran', record_time_key="time", 
                            record={
                                "measurement": "ue_info",
                                "tags": {
                                    "pci": "test",
                                    "rnti": f"{self.rnti}",
                                    "testbed": "testing",
                                },
                            "fields": {"type": message_type, "text": message_text},
                            "time": formatted_timestamp,
                            },
                            )
                logging.info("Sent message text")
                if self.ue_command:
                    self.influx_push(write_api, bucket='srsran', record_time_key="time", 
                                record={
                                    "measurement": "ue_info",
                                    "tags": {
                                        "pci": "test",
                                        "rnti": f"{self.rnti}",
                                        "testbed": "testing",
                                    },
                                "fields": {"type": "command", "text": " ".join(self.ue_command)},
                                "time": utc_timestamp,
                                },
                                )
                    self.ue_command = []
            except Exception as e:
                logging.error(f"send_message failed with error: {e}")
                message_str = '{ "type": "' + message_type + '", "text": "' + message_text + '"}'
                self.log_buffer.append(message_str)


    def influx_push(self, write_api: WriteApi, *args, **kwargs) -> None:
        while True:
            try:
                write_api.write(*args, **kwargs)
                break
            except (RemoteDisconnected, ConnectionRefusedError):
                logging.warning("Error pushing data. Retrying...")
                sleep(1)


    def start_metrics(self):
        self.metrics_client.start(self.ue_config, self.docker_container)


    def collect_logs(self):
        while self.isRunning and not self.stop_thread.is_set():
            line = next(self.docker_logs, None)
            if line:
                if isinstance(line, tuple):
                    line = line[0].strip()
                else:
                    line = line.strip()

            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='replace')

            if line:
                logging.debug(f"SRSUE: {line}")
                self.send_message("log", line)

                self.output.append(line)
                if "rnti" in line:
                    self.rnti = line.split("0x")[1][:4]
                if "PDU" in line:
                    self.start_metrics()
                    self.isConnected = True


    def stop(self):
        if self.docker_container:
            try:
                self.docker_container.stop()
                self.docker_container.remove()
                logging.info(f"Docker container stopped and removed: {self.docker_container.name}")
            except docker.errors.APIError as e:
                logging.error(f"Failed to stop Docker container: {e}")
        self.stop_thread.set()
        self.isRunning = False
