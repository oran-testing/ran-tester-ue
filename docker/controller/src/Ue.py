import time
import os
import threading
import asyncio
import uuid
import websockets
import configparser
import docker
import logging

from Iperf import Iperf
from Ping import Ping
from Metrics import Metrics
from utils import kill_subprocess, send_command, start_subprocess

asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

# UE process manager class:
# subprocesses: srsRAN UE, Iperf, Ping, Metrics monitor
#
# Handles all process and data management for one UE
#
# Collects data from UE iperf and ping, then sends them to the webui

class Ue:
    def __init__(self, enable_docker, ue_index):
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

        self.websocket_client = None
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

    async def websocket_handler(self, websocket, path=""):
        """Handle incoming WebSocket connection and stream logs to the client."""
        self.websocket_client = websocket
        try:
            # Send all buffered logs once the client connects
            for log in self.log_buffer:
                await websocket.send(log)
            self.log_buffer.clear()  # Clear buffer after sending

            # Keep the connection open to send new logs or commands
            while True:
                await asyncio.sleep(0.1)  # Prevent blocking the event loop
        except websockets.exceptions.ConnectionClosed:
            logging.error("WebSocket client disconnected")
        finally:
            self.websocket_client = None  # Reset client on disconnect

    def start_websocket_server(self):
        """Start the WebSocket server in a separate thread."""
        self.websocket_thread = threading.Thread(target=self.run_websocket_server, daemon=True)
        self.websocket_thread.start()


    def run_websocket_server(self):
        """Run the WebSocket server for sending logs."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        time.sleep(2)

        async def server_coroutine():
            server = await websockets.serve(self.websocket_handler, "0.0.0.0", 8765 + self.ue_index)
            logging.debug(f"Started server on port {8765 + self.ue_index}")
            await server.wait_closed()

        try:
            loop.run_until_complete(server_coroutine())
        except Exception as e:
            logging.error(f"Failed to run WebSocket server: {e}")
        finally:
            loop.close()

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
                containers = self.docker_client.containers.list(all=True, filters={"name": container_name})
                if containers:
                    self.docker_container = containers[0]
                    self.docker_container.start()  # Restart if stopped
                    logging.debug(f"Restarted existing Docker container {container_name}")
                else:
                    network_name = "docker_srsue_network"
                    self.docker_network = self.docker_client.networks.get(network_name)
                    self.docker_container = self.docker_client.containers.run(
                        image="srsran/ue",
                        name=container_name,
                        environment=environment,
                        volumes={
                            "/dev/bus/usb/": {"bind": "/dev/bus/usb/", "mode": "rw"},
                            "/usr/share/uhd/images": {"bind": "/usr/share/uhd/images", "mode": "ro"},
                            "ue-storage": {"bind": "/tmp", "mode": "rw"}
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
            self.start_websocket_server()
            self.log_thread = threading.Thread(target=self.collect_logs, daemon=True)
            self.log_thread.start()



    def send_message(self, message_type, message_text):
        """Send either a 'command' or 'log' message to the connected WebSocket client."""
        if not message_text or not message_type:
            return
        message_str = '{ "type": "' + message_type + '", "text": "' + message_text + '"}'
        command_str = '{ "type": "command", "text": "' + " ".join(self.ue_command) + '"}'

        if self.websocket_client:
            try:
                asyncio.run(self.websocket_client.send(message_str))
                if self.ue_command:
                    asyncio.run(self.websocket_client.send(command_str))
                    self.ue_command = []
            except Exception as e:
                logging.error(f"Failed to send message: {e}")
        else:
            if message_type == "log":
                self.log_buffer.append(message_str)

    def start_metrics(self):
        self.iperf_client.start(
            ["-c", "10.53.1.1", "-i", "1", "-t","36000", "-u", "-b", "100M", "-R"]
            , process_type="client",
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
                    line = line.strip()

            if self.process:
                line = self.process.stdout.readline()
                if line:
                    line = line.strip()

            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='replace')

            if line:
                logging.debug(f"SRSUE: {line}")
                self.send_message("log", line)  # Send log to WebSocket client

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

