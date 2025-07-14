import time
import os
import threading
import socket
import logging
import docker
from datetime import datetime
from influxdb_client import InfluxDBClient, WriteApi
from influxdb_client.client.write_api import SYNCHRONOUS

class llm_config:
    def __init__(self, influxdb_client, docker_client):
        self.influxdb_client = influxdb_client
        self.docker_client = docker_client
        self.docker_container = None

    def start(self, process_config):
        self.llm_config = process_config["config_file"]
        self.container_name = process_config["id"]
        self.llm_args = process_config.get("args", [""])
        # This is the name of the image you will build locally with the Dockerfile
        self.image_name = "llm-agent-env:latest"

        # Verify the local image exists
        try:
            self.docker_client.images.get(self.image_name)
        except docker.errors.ImageNotFound:
            raise RuntimeError(f"Docker image {self.image_name} not found. Build it first using the provided Dockerfile.")

        # Remove old container if it exists to ensure a clean start
        try:
            old_container = self.docker_client.containers.get(self.container_name)
            old_container.remove(force=True)
            logging.debug(f"Removed old container: {self.container_name}")
        except docker.errors.NotFound:
            logging.debug(f"No existing container to remove: {self.container_name}")
        except Exception as e:
            raise RuntimeError(f"Failed to remove old container: {e}")

        rf_config = process_config["rf"]
        if rf_config["type"] != "b200":
            raise RuntimeError(f"Unsupported RF type: {rf_config['type']}")
        uhd_images_dir = rf_config["images_dir"]

        # Launch the container
        try:
            environment = {
                "CONFIG": self.llm_config,
                "ARGS": " ".join(self.llm_args),
                "UHD_IMAGES_DIR": uhd_images_dir,
            }
            
            # network_mode="host" is crucial for port communication via localhost
            self.docker_container = self.docker_client.containers.run(
                image=self.image_name,
                name=self.container_name,
                environment=environment,
                volumes={
                    "/dev/bus/usb/": {"bind": "/dev/bus/usb/", "mode": "rw"},
                    uhd_images_dir: {"bind": uhd_images_dir, "mode": "ro"},
                    "/tmp": {"bind": "/tmp", "mode": "rw"},
                    self.llm_config: {"bind": "/llm.conf", "mode": "ro"}
                },
                privileged=True,
                cap_add=["SYS_NICE", "SYS_PTRACE"],
                network_mode="host",
                detach=True
            )

            logging.info(f"[llm_worker] Container '{self.container_name}' started.")
            time.sleep(5) 

            self.send_start_signal_to_llm("localhost", 8989)

            self.docker_logs = self.docker_container.logs(stream=True, follow=True)

        except docker.errors.APIError as e:
            logging.error(f"Failed to start Docker container: {e}")
            return

        self.stop_thread = threading.Event()
        self.log_thread = threading.Thread(target=self.log_report_thread, daemon=True)
        self.log_thread.start()

    def stop(self):
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
                utc_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                self.influx_push(
                    write_api,
                    bucket='rtusystem',
                    record_time_key="time",
                    record={
                        "measurement": "jammer_log",
                        "tags": {
                            "testbed": "default",
                            "jammer_data_identifier": self.container_name,
                        },
                        "fields": {"jammer_stdout_log": message_text},
                        "time": utc_timestamp,
                    }
                )
                logging.debug(f"[{self.container_name}]: {message_text}")
            except Exception as e:
                logging.error(f"send_message failed: {e}")

    def influx_push(self, write_api: WriteApi, *args, **kwargs):
        while True:
            try:
                write_api.write(*args, **kwargs)
                break
            except ConnectionError as e:
                logging.warning(f"InfluxDB push error: {e}. Retrying...")
                time.sleep(1)

    def log_report_thread(self):
        while not self.stop_thread.is_set():
            try:
                line = next(self.docker_logs, None)
                if not line:
                    time.sleep(0.1)
                    continue
                if isinstance(line, bytes):
                    line = line.decode('utf-8', errors='replace')
                if isinstance(line, (tuple, list)):
                    line = str(line[0])
                self.send_message(line.strip())
            except StopIteration:
                logging.info(f"Log stream ended for {self.container_name}.")
                break


    def send_start_signal_to_llm(self, host, port, retry_count=5):
        """Connects to a TCP socket and sends the 'start' signal with retries."""
        logging.info(f"[llm_worker] Attempting to send 'start' signal to {host}:{port}")
        for attempt in range(retry_count):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                    client.connect((host, port))
                    client.sendall(b"start")
                    logging.info("[llm_worker] Sent start signal to LLM agent.")
                    return
            except ConnectionRefusedError:
                logging.warning(f"[llm_worker] Connection refused. Retrying in 2 seconds... ({attempt+1}/{retry_count})")
                time.sleep(2)
            except Exception as e:
                logging.error(f"[llm_worker] Failed to send start signal: {e}")
                break
        logging.error(f"[llm_worker] Could not connect to the LLM agent after {retry_count} attempts.")