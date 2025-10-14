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
from docker.types import IPAMConfig, IPAMPool

class RfType(Enum):
    NONE = 0
    ZMQ = 1
    B200 = 2

class WorkerThreadConfig:
    def __init__(self):
        self.process_config : dict = None
        self.influxdb_client : InfluxDBClient = None
        self.docker_client : DockerClient = None
        self.config_file : str = ""
        self.container_id : str = ""
        self.cli_args : list[str] = []
        self.image_name : str = ""
        self.rf_type : RfType = RfType.NONE;
        self.rf_config = {}
        self.container_env = {}
        self.container_volumes = {}
        self.container_networks = []
        self.container_privileged = True
        self.device_requests = []
        self.host_network = False


class WorkerThread:
    def __init__(self, influxdb_client, docker_client, process_config):
        self.docker_container = None
        self.docker_logs = None
        self.config = WorkerThreadConfig()
        self.config.process_config = process_config
        self.config.influxdb_client = influxdb_client
        self.config.docker_client = docker_client
        if "config_file" in process_config.keys():
            self.config.config_file = process_config["config_file"]

        if "id" in process_config.keys():
            self.config.container_id = process_config["id"]
        else:
            raise RuntimeError("Process id is required")

        if "args" in process_config.keys():
            self.config.cli_args = process_config["args"]

        # Process RF
        self.config.rf_config = process_config["rf"]
        if self.config.rf_config["type"] == "b200":
            self.config.rf_type = RfType.B200
            if "images_dir" not in self.config.rf_config:
                raise RuntimeError(f"Error parsing rf configuration of {self.config.container_id}: RF type b200 requires images_dir")
        elif self.config.rf_config["type"] == "zmq":
            self.config.rf_type = RfType.ZMQ
            if "tcp_subnet" not in self.config.rf_config:
                raise RuntimeError(f"Error parsing rf configuration of {self.config.container_id}: RF type ZMQ requires tcp_subnet")
            if "gateway" not in self.config.rf_config:
                raise RuntimeError(f"Error parsing rf configuration of {self.config.container_id}: RF type ZMQ requires gateway")
        elif self.config.rf_config["type"] == "none":
            logging.debug(f"{self.config.container_id}: configured with no RF")
        else:
            raise RuntimeError(f"Unsupported RF type: {self.config.rf_config['type']}")
        
        self.config.host_network = bool(process_config.get("host_network", False))

    def cleanup_old_containers(self):
        # Verify Image
        image_exists = False
        for img in self.config.docker_client.images.list():
            image_tags = [image_tag.split(':')[0] for image_tag in img.tags]
            if self.config.image_name in image_tags:
                image_exists = True
                break
        if not image_exists:
            raise RuntimeError(f"Required Docker image {self.config.image_name} not found: Please run 'sudo docker compose --profile components build' or 'sudo docker compose --profile components pull'")

        # Remove old container
        try:
            old_container = self.config.docker_client.containers.get(self.config.container_id)
            old_container.remove(force=True)
            logging.debug(f"Container '{self.config.container_id}' has been removed.")
        except docker.errors.NotFound:
            logging.debug(f"Container '{self.config.container_id}' does not exist.")
        except Exception as e:
            raise RuntimeError(f"Failed to remove old container: {e}")

    def setup_volumes(self):
        self.config.container_volumes["/tmp"] = {"bind":"/tmp", "mode": "rw"}
        if self.config.rf_type == RfType.B200:
            self.config.container_volumes["/dev/bus/usb/"] = {"bind": "/dev/bus/usb/", "mode": "rw"}
            if "images_dir" not in self.config.rf_config.keys():
                raise RuntimeError("images_dir is required for UHD RF")
            if type(self.config.rf_config["images_dir"]) != str:
                raise RuntimeError("images_dir must be a string")
            self.config.container_volumes[self.config.rf_config["images_dir"]] = {"bind": self.config.rf_config["images_dir"], "mode": "ro"}

            firmware_file = os.path.join(self.config.rf_config["images_dir"], "usrp_b200_fw.hex")
            image_file = os.path.join(self.config.rf_config["images_dir"], "usrp_b200_fpga.bin")
            logging.debug(f"Checking for {firmware_file} and {image_file}")
            if not os.path.exists(firmware_file) or not os.path.exists(image_file):
                raise RuntimeError(f"Required images for {self.config.rf_config['type']} missing in {self.config.rf_config['images_dir']}: run uhd_images_downloader")

    def setup_env(self):
        self.config.container_env["ARGS"] = " ".join(self.config.cli_args)
        if self.config.rf_type == RfType.B200:
            self.config.container_env["UHD_IMAGES_DIR"] = self.config.rf_config["images_dir"]

    def setup_networks(self):
        self.config.container_networks.append(self.config.docker_client.networks.get("rt_metrics"))

        if self.config.rf_type == RfType.ZMQ:
            try:
                self.config.container_networks.append(self.config.docker_client.networks.get("rt_zmq"))
            except docker.errors.NotFound:
                ipam_pool = IPAMPool(
                    subnet=self.config.rf_config["tcp_subnet"],
                    gateway=self.config.rf_config["gateway"]
                )
                ipam_config = IPAMConfig(pool_configs=[ipam_pool])
                self.config.container_networks.append(self.config.docker_client.networks.create(name="rt_zmq", driver="bridge", ipam=ipam_config, check_duplicate=True))

    def start_container(self):
        try:
            if self.config.host_network:
                self.docker_container = self.config.docker_client.containers.run(
                    image=self.config.image_name,
                    name=self.config.container_id,
                    environment=self.config.container_env,
                    volumes=self.config.container_volumes,
                    privileged=True,
                    cap_add=["SYS_NICE", "SYS_PTRACE"],
                    detach=True,
                    device_requests=self.config.device_requests,
                    network_mode="host",
                )
            else:
                self.docker_container = self.config.docker_client.containers.run(
                    image=self.config.image_name,
                    name=self.config.container_id,
                    environment=self.config.container_env,
                    volumes=self.config.container_volumes,
                    privileged=True,
                    cap_add=["SYS_NICE", "SYS_PTRACE"],
                    detach=True,
                    device_requests=self.config.device_requests,
                )

                for network in self.config.container_networks:
                    network.connect(self.docker_container)
            self.docker_logs = self.docker_container.logs(stream=True, follow=True)

        except docker.errors.APIError as e:
            logging.error(f"Failed to start Docker container: {e}")
            return

        self.stop_thread = threading.Event()
        self.log_thread = threading.Thread(target=self.log_report_thread, daemon=True)
        self.log_thread.start()


    def start(self):
        raise RuntimeError("start behavior must be defined by individual worker class")


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
        self.docker_container.reload()
        info = self.docker_container.attrs
        if info["State"]["Running"]:
            return { "id": self.config.container_id, "healthy": True, info["Image"] : info["State"] }
        return { "id": self.config.container_id, "healthy": False, "exit_code": info["State"]["ExitCode"]}


    def send_message(self, message_text):
        with self.config.influxdb_client.write_api(write_options=SYNCHRONOUS) as write_api:
            try:
                utc_timestamp = datetime.utcnow()
                formatted_timestamp = utc_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                self.influx_push(write_api, bucket='rtusystem', record_time_key="time", 
                            record={
                                "measurement": "component_log",
                                "tags": {
                                    "id": f"{self.config.container_id}",
                                    "msg_uuid": uuid.uuid4(),
                                },
                            "fields": {"stdout_log": message_text},
                            "time": formatted_timestamp,
                            },
                            )
                logging.debug(f"[{self.config.container_id}]: {message_text}")
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

