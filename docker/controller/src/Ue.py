import time
import os
import threading
import asyncio
import uuid
import configparser
import docker
import logging
from datetime import datetime

from Iperf import Iperf
from Ping import Ping
from Metrics import Metrics

from influxdb_client import InfluxDBClient, WriteApi
from utils import kill_subprocess, send_command, start_subprocess, influx_push

from influxdb_client import InfluxDBClient, WriteApi
from influxdb_client.client.write_api import SYNCHRONOUS

# UE process manager class:
# subprocesses: srsRAN UE, Iperf, Ping, Metrics monitor
#
# Handles all process and data management for one UE
#
# Collects data from UE iperf and ping, then sends them to the webui

class Ue:
    def __init__(self, enable_docker, ue_index):
        self.influxdb_client = InfluxDBClient(
            "http://influxdb:8086" if enable_docker else "http://0.0.0.0:8086",
            org="srs",
            token="605bc59413b7d5457d181ccf20f9fda15693f81b068d70396cc183081b264f3b"
        )
        self.docker_enabled = enable_docker
        self.docker_client = docker.from_env() if self.docker_enabled else None
        self.docker_container = None


        self.ue_index = ue_index

        self.ue_config = ""
        self.isRunning = False
        self.isConnected = False
        self.process = None
        self.iperf_client = Iperf(self.send_message)
        self.ping_client = Ping(self.send_message)
        self.metrics_client = Metrics(self.send_message)
        self.output = []
        self.rnti = ""

        self.log_buffer = []
        self.ue_command = []

        self.usim_data = {}
        self.pcap_data = {}

    def get_output_filename(self):
        return f"srsue_{self.ue_config.split('/')[-1]}_{self.ue_index}.log"

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


    def get_unwritten_output(self):
        """
        Get a list of all unsaved output from each child process
        """
        unwritten_output = {}
        if self.iperf_client.isRunning and self.iperf_client.output:
            unwritten_output["iperf"] = [str(item[1]) for item in self.iperf_client.output]
            self.iperf_client.output = []

        if self.ping_client.isRunning and self.ping_client.output:
            unwritten_output["ping"] = [str(item[1]) for item in self.ping_client.output]
            self.ping_client.output = []

        return unwritten_output

    def start(self, args):
        for argument in args:
            if ".conf" in argument:
                self.ue_config = argument
                self.get_info_from_config()

        if self.docker_enabled:
            container_name = f"srsran_ue_{str(uuid.uuid4())}"
            environment = {
                "CONFIG": self.ue_config,
                "ARGS": " ".join(args[1:]),
            }
            try:
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
        else:
            command = ["srsue"] + args
            self.ue_command = command
            self.process = start_subprocess(command)
            self.isRunning = True


        if self.isRunning:
            self.stop_thread = threading.Event()
            self.log_thread = threading.Thread(target=self.collect_logs, daemon=True)
            self.log_thread.start()



    def send_message(self, message_type, message_text):
        if not message_text or not message_type:
            return
        message_str = '{ "type": "' + message_type + '", "text": "' + message_text + '"}'

        with self.influxdb_client.write_api(write_options=SYNCHRONOUS) as write_api:
            try:
                utc_timestamp = datetime.utcnow()
                formatted_timestamp = utc_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                influx_push(write_api, bucket='srsran', record_time_key="time", 
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
                    influx_push(write_api, bucket='srsran', record_time_key="time", 
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
                self.log_buffer.append(message_str)

    def start_metrics(self):
        self.iperf_client.start(
            ["-c", "10.53.1.1", "-i", "1", "-t","36000", "-u", "-b", "100M", "-R"],
            ue_index=self.ue_index,
            docker_container=self.docker_container,
        )
        self.ping_client.start(["10.45.1.1"])
        self.metrics_client.start(self.ue_config, self.docker_container)


    def collect_logs(self):
        """Collect logs from the process and send them to the WebSocket client."""

        while self.isRunning and not self.stop_thread.is_set():
            line = None

            if self.docker_enabled:
                line = next(self.docker_logs, None)
                if line:
                    if isinstance(line, tuple):
                        line = line[0].strip()
                    else:
                        line = line.strip()

            if self.process:
                line = self.process.stdout.readline()
                if line:
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
        if self.docker_enabled:
            if self.docker_container:
                try:
                    self.docker_container.stop()
                    self.docker_container.remove()
                    logging.info(f"Docker container stopped and removed: {self.docker_container.name}")
                except docker.errors.APIError as e:
                    logging.error(f"Failed to stop Docker container: {e}")
        else:
            kill_subprocess(self.process)

        self.stop_thread.set()
        self.iperf_client.stop()
        self.isRunning = False

    def __repr__(self):
        return f"srsRAN UE{self.ue_index} object, running: {self.isRunning}"

if __name__ == "__main__":
    test = Ue(True, 1)
    test.start(["./configs/zmq/ue_zmq_docker.conf"])
    while True:
        time.sleep(1)

