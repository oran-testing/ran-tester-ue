import time
import os
import threading
import asyncio
import uuid
import configparser
import docker
import logging
from datetime import datetime

from influxdb_client import InfluxDBClient, WriteApi
from influxdb_client.client.write_api import SYNCHRONOUS

# UE process manager class:
# Handles all process and data management for one UE
#
# Collects data from UE then sends them to the webui
#

class rtue:
    def __init__(self, influxdb_client, docker_client):
        self.influxdb_client = influxdb_client
        self.docker_client = docker_client


    def start(self, config="", args=[]):
        """
        Gets data identifier and pcap info from ue config
        Starts rtue container with volumes and network
        Starts log report thread
        """
        self.ue_config = config
        self.get_info_from_config()

        container_name = f"rtue_{uuid.uuid4()}"
        self.container_name = container_name
        self.image_name = "ghcr.io/oran-testing/rtue"

        try:
            image_exists = any(img.tags and self.image_name in img.tags for img in self.docker_client.images.list())

            if not image_exists:
                logging.error(f"Image {self.image_name} not found locally.")
                raise RuntimeError(f"Required Docker image {self.image_name} not found")

        except docker.errors.ImageNotFound:
            logging.error(f"Required image {self.image_name} not found and could not be pulled.")
            raise RuntimeError(f"Required Docker image {self.image_name} not found.")

        except docker.errors.APIError as e:
            logging.error(f"Error checking or pulling Docker image {self.image_name}: {e}")
            raise RuntimeError(f"Failed to check or pull Docker image {self.image_name}: {e}")



        try:
            environment = {
                "CONFIG": self.ue_config,
                "ARGS": " ".join(args),
                "UHD_IMAGES_DIR": os.getenv("UHD_IMAGES_DIR")
            }

            self.docker_network = self.docker_client.networks.get(network_name)
            self.docker_container = self.docker_client.containers.run(
                image=self.image_name,
                name=container_name,
                environment=environment,
                volumes={
                    "/dev/bus/usb/": {"bind": "/dev/bus/usb/", "mode": "rw"},
                    "/usr/share/uhd/images": {"bind": "/usr/share/uhd/images", "mode": "ro"},
                    "/usr/local/share/uhd/images": {"bind": "/usr/local/share/uhd/images", "mode": "ro"},
                    "/tmp": {"bind": "/tmp", "mode": "rw"}
                },
                privileged=True,
                cap_add=["SYS_NICE", "SYS_PTRACE"],
                network="docker_metrics",
                detach=True,
            )

            logging.debug(f"rtue container initialized: {container_name}")


            self.docker_logs = self.docker_container.logs(stream=True, follow=True)

        except docker.errors.APIError as e:
            logging.error(f"Failed to start Docker container: {e}")
            return

        self.stop_thread = threading.Event()
        self.log_thread = threading.Thread(target=self.log_report_thread, daemon=True)
        self.log_thread.start()


    def stop(self):
        """
        Stops rtue cotainer if existing
        Stops log reporting thread
        """
        if self.docker_container:
            try:
                self.docker_container.stop()
                self.docker_container.remove()
                logging.info(f"Docker container stopped and removed: {self.docker_container.name}")
            except docker.errors.APIError as e:
                logging.error(f"Failed to stop Docker container: {e}")
        self.stop_thread.set()


    def get_info_from_config(self):
        config = configparser.ConfigParser()
        config.read(self.ue_config)

        self.pcap_data = {
            "mac_filename": config.get("pcap", "mac_filename", fallback=None),
            "mac_nr_filename": config.get("pcap", "mac_nr_filename", fallback=None),
            "nas_filename": config.get("pcap", "nas_filename", fallback=None)
        }

        self.ue_data_identifier = config.get("general", "ue_data_identifier", fallback=str(uuid.uuid4()))


    def send_message(self, message_text):
        with self.influxdb_client.write_api(write_options=SYNCHRONOUS) as write_api:
            try:
                utc_timestamp = datetime.utcnow()
                formatted_timestamp = utc_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                self.influx_push(write_api, bucket='rtusystem', record_time_key="time", 
                            record={
                                "measurement": "ue_info",
                                "tags": {
                                    "pci": "test",
                                    "ue_data_identifier": f"{self.ue_data_identifier}",
                                    "testbed": "testing",
                                },
                            "fields": {"rtue_stdout_log": message_text},
                            "time": formatted_timestamp,
                            },
                            )
                logging.debug(f"[{self.container_name}]: {message_text}")
            except Exception as e:
                logging.error(f"send_message failed with error: {e}")

    def influx_push(self, write_api: WriteApi, *args, **kwargs) -> None:
        while True:
            try:
                write_api.write(*args, **kwargs)
                break
            except ConnectionError as e:
                logging.warning(f"Error pushing data: {e}. Retrying...")
                time.sleep(1)

    def log_report_thread(self):
        while not self.stop_thread.is_set():
            line = next(self.docker_logs, None)
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='replace')
            if isinstance(line, tuple) or isinstance(line, list):
                line = str(line[0])

            self.send_message(line.strip())

