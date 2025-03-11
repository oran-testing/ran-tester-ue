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

class sniffer:
    def __init__(self, influxdb_client, docker_client):
        self.influxdb_client = influxdb_client
        self.docker_client = docker_client


    def start(self, config="", args=[]):
        self.sniffer_config = config

        container_name = f"sniffer_{str(uuid.uuid4())}"
        self.image_name = "ghcr.io/oran-testing/sniffer"

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

        environment = {
            "CONFIG": self.sniffer_config,
            "UHD_IMAGES_DIR": os.getenv("UHD_IMAGES_DIR")
        }

        try:
            # Stop all existing instances
            containers = self.docker_client.containers.list(all=True, filters={"ancestor": self.image_name})
            if containers:
                for container in containers:
                    logging.debug(f"Removing existing container {container}")
                    container.stop()
                    container.remove()

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
                detach=True,
            )

            logging.debug(f"sniffer container initialized: {container_name}")


            self.docker_logs = self.docker_container.logs(stream=True, follow=True)

        except docker.errors.APIError as e:
            logging.error(f"Failed to start Docker container: {e}")
            return

        self.stop_thread = threading.Event()
        self.log_thread = threading.Thread(target=self.log_report_thread, daemon=True)
        self.log_thread.start()


    def stop(self):
        """
        Stops sniffer cotainer if existing
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


    def send_message(self, message_text):
        with self.influxdb_client.write_api(write_options=SYNCHRONOUS) as write_api:
            try:
                utc_timestamp = datetime.utcnow()
                formatted_timestamp = utc_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                self.influx_push(write_api, bucket='rtusystem', record_time_key="time", 
                            record={
                                "measurement": "sniffer_log",
                                "tags": {
                                    "testbed": "default",
                                },
                            "fields": {"sniffer_stdout_log": message_text},
                            "time": formatted_timestamp,
                            },
                            )
                logging.debug(f"[sniffer]: {message_text}")
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

