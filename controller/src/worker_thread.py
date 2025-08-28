import time
import os
import threading
import asyncio
import uuid
import configparser
import docker
import logging
from datetime import datetime
from enum import Enum

from docker.client import DockerClient
from influxdb_client import InfluxDBClient, WriteApi
from influxdb_client.client.write_api import SYNCHRONOUS

class RfType(Enum):
    NONE = 0
    ZMQ = 1
    B200 = 1

class WorkerThreadConfig():
    def __init__(self):
        self.influxdb_client : InfluxDBClient = None
        self.docker_client : DockerClient = None
        self.config_file : str = ""
        self.container_id : str = ""
        self.cli_args : list[str] = []
        self.image_name : str = ""
        self.image_name : str = ""
        self.rf_type : RfType = NONE;
        self.rf_config = {}
        self.container_env = {}
        self.container_volumes = {}
        self.container_networks = [
            "rt_metrics"
        ]
        self.container_privileged = True


class WorkerThread:
    def __init__(self, influxdb_client, docker_client, process_config):
        self.config = WorkerThreadConfig()
        self.config.influxdb_client = influxdb_client
        self.config.docker_client = docker_client
        if "config_file" in process_config.keys():
            self.config.config_file = process_config["config_file"]

        if "id" in process_config.keys():
            self.config.container_id = process_config["id"]

        if "args" in process_config.keys():
            self.config.cli_args = process_config["args"]

        # Process RF
        self.config.rf_config = process_config["rf"]
        if rf_config["type"] == "b200":
            self.config.rf_type = B200
            if "images_dir" not in self.config.rf_config:
                raise RuntimeError(f"Error parsing rf configuration of {self.config.container_id}: RF type b200 requires images_dir")
        elif rf_config["type"] == "zmq":
            self.config.rf_type = ZMQ
            if "tcp_subnet" not in self.config.rf_config:
                raise RuntimeError(f"Error parsing rf configuration of {self.config.container_id}: RF type ZMQ requires tcp_subnet")
        else:
            raise RuntimeError(f"Unsupported RF type: {rf_config['type']}")

    def cleanup_old_containers(self):
        # Verify Image
        image_exists = False
        for img in self.config.docker_client.images.list():
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

    def start(self, process_config):
        raise RuntimeError("start behavior must be defined by individual worker class")




        # Start Container
        try:
            environment = {
                "CONFIG": self.ue_config,
                "ARGS": " ".join(self.ue_args),
                "UHD_IMAGES_DIR": uhd_images_dir
            }


            self.network_name = "rt_metrics"
            self.docker_network = self.docker_client.networks.get(self.network_name)
            self.docker_container = self.docker_client.containers.run(
                image=self.image_name,
                name=self.container_name,
                environment=environment,
                volumes={
                    "/dev/bus/usb/": {"bind": "/dev/bus/usb/", "mode": "rw"},
                    uhd_images_dir: {"bind": uhd_images_dir, "mode": "ro"},
                    "/tmp": {"bind": "/tmp", "mode": "rw"},
                    self.ue_config: {"bind": "/ue.conf", "mode": "ro"}
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
        Stops current container if running
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

    def get_status(self):
        return self.docker_container.status


    def send_message(self, message_text):
        with self.influxdb_client.write_api(write_options=SYNCHRONOUS) as write_api:
            try:
                utc_timestamp = datetime.utcnow()
                formatted_timestamp = utc_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                self.influx_push(write_api, bucket='rtusystem', record_time_key="time", 
                            record={
                                "measurement": "component_log",
                                "tags": {
                                    "id": f"{self.container_name}",
                                    "msg_uuid": uuid.uuid4(),
                                },
                            "fields": {"stdout_log": message_text},
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

