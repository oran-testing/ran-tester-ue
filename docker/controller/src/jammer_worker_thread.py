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
# subprocesses: srsRAN UE, Metrics monitor
#
# Handles all process and data management for one UE
#
# Collects data from UE then sends them to the webui
#

class jammer:
    def __init__(self, influxdb_client, docker_client):
        self.influxdb_client = influxdb_client
        self.docker_client = docker_client


    def start(self, config="", args=[]):
        """
        Gets data identifier and pcap info from ue config
        Starts srsue container with volumes
        Starts log report thread
        """
        self.jammer_config = config

        container_name = f"jammer_{str(uuid.uuid4())}"

        environment = {
            "CONFIG": self.jammer_config,
            "UHD_IMAGES_DIR": "/usr/local/share/uhd/images"
        }

        try:
            containers = self.docker_client.containers.list(all=True, filters={"ancestor": "stu/jammer"})
            if containers:
                containers[0].stop()
                containers[0].remove()
                logging.debug(f"Removed existing container")

            self.docker_container = self.docker_client.containers.run(
                image="stu/jammer",
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

            logging.debug(f"jammer container initialized: {container_name}")


            self.docker_logs = self.docker_container.logs(stream=True, follow=True)

        except docker.errors.APIError as e:
            logging.error(f"Failed to start Docker container: {e}")
            return

        self.stop_thread = threading.Event()
        self.log_thread = threading.Thread(target=self.log_report_thread, daemon=True)
        self.log_thread.start()


    def stop(self):
        """
        Stops jammer cotainer if existing
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
                self.influx_push(write_api, bucket='srsran', record_time_key="time", 
                            record={
                                "measurement": "jammer_log",
                                "tags": {
                                    "testbed": "default",
                                },
                            "fields": {"jammer_stdout_log": message_text},
                            "time": formatted_timestamp,
                            },
                            )
                logging.debug(f"[JAMMER]: {message_text}")
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

