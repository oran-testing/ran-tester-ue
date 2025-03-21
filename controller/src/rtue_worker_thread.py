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


    def start(self, process_config):
        """
        Gets data identifier and pcap info from ue config
        Starts rtue container with volumes and network
        Starts log report thread
        """
        self.ue_config = process_config["config_file"]
        self.container_name = process_config["id"]
        self.ue_args = process_config["args"] if "args" in process_config.keys() else [""]

        self.image_name = "ghcr.io/oran-testing/rtue"

        # Verify Image
        image_exists = False
        for img in self.docker_client.images.list():
            image_tags = [image_tag.split(':')[0] for image_tag in img.tags]
            if self.image_name in image_tags:
                image_exists = True
                break
        if not image_exists:
            raise RuntimeError(f"Required Docker image {self.image_name} not found: Please run 'sudo docker compose --profile components build' or 'sudo docker compose --profile components pull'")

        # Remove old container
        try:
            old_container = self.docker_client.containers.get(self.container_name)
            old_container.remove(force=True)
            logging.debug(f"Container '{self.container_name}' has been removed.")
        except docker.errors.NotFound:
            logging.debug(f"Container '{self.container_name}' does not exist.")
        except Exception as e:
            raise RuntimeError(f"Failed to remove old container: {e}")

        # Process RF
        uhd_images_dir = ""
        rf_config = process_config["rf"]
        if rf_config["type"] == "b200":
            uhd_images_dir = rf_config["images_dir"]
        else:
            raise RuntimeError(f"Invalid RF type for rtUE: {rf_config['type']}")


        # Start Container
        try:
            environment = {
                "CONFIG": self.ue_config,
                "ARGS": " ".join(self.ue_args),
                "UHD_IMAGES_DIR": uhd_images_dir
            }


            self.network_name = "docker_metrics"
            self.docker_network = self.docker_client.networks.get(self.network_name)
            self.docker_container = self.docker_client.containers.run(
                image=self.image_name,
                name=self.container_name,
                environment=environment,
                volumes={
                    "/dev/bus/usb/": {"bind": "/dev/bus/usb/", "mode": "rw"},
                    uhd_images_dir: {"bind": uhd_images_dir, "mode": "ro"},
                    "/tmp": {"bind": "/tmp", "mode": "rw"}
                },
                privileged=True,
                cap_add=["SYS_NICE", "SYS_PTRACE"],
                network=self.network_name,
                detach=True,
            )
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
                                    "ue_data_identifier": f"{self.container_name}",
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

