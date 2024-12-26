import re
import select
import sys
import threading
import os
import time
import logging
from datetime import datetime

from utils import kill_subprocess, start_subprocess


class Iperf:
    def __init__(self, send_message_callback):
        self.isRunning = False
        self.process = None
        self.output = []
        self.initialized = False
        self.name = "Iperf -- Stopped"
        self.send_callback = send_message_callback
        self.docker_enabled = False

    def start(self, args, ue_index=1, docker_container=None):
        self.docker_container = docker_container
        if not self.docker_container:
            command = []
            command = ["ip", "netns","exec", f"ue{ue_index}", "stdbuf", "-oL", "-eL", "iperf3"] + args
            os.system(f"ip netns exec ue{ue_index} ip ro add default via 10.45.1.1 dev tun_srsue > /dev/null 2>&1")
            time.sleep(2)
            self.process = start_subprocess(command)
        else:
            route_command = f"ip ro add 10.53.0.0/16 via 10.45.1.1 dev tun_srsue"
            iperf_command = f"bash -c 'iperf3 {' '.join(args)} 2>&1'"
            route_exec_result = self.docker_container.exec_run(route_command)
            if route_exec_result.exit_code != 0:
                logging.error(f"Failed to setup route with command: {route_command}")
                return

            time.sleep(2)
            iperf_exec_result = self.docker_container.exec_run(
                iperf_command,
                stream=True,
            )

            self.docker_enabled = True
            try:
                self.docker_stdout_stream = iperf_exec_result.output
            except Exception as e:
                logging.error(f"Failed to get iperf3 output {e}")
                return

        self.isRunning = True
        self.name = f"Iperf -- Started"
        self.start_time = datetime.now()

        self.log_thread = threading.Thread(target=self.collect_logs, daemon=True)
        self.log_thread.start()
        self.initialized = True

    def stop(self):
        kill_subprocess(self.process)
        self.isRunning = False
        self.name = "Iperf -- Stopped"

    def collect_logs(self):
        bitrate_pattern = re.compile(r'(\d+\.\d+) Mbits/sec')
        while self.isRunning:
            if self.process:
                line = self.process.stdout.readline()
                if line:
                    line = line.strip()
                    bitrate = bitrate_pattern.findall(line)
                    if len(bitrate) > 0:
                        self.output.append(
                            ((datetime.now() - self.start_time).total_seconds(),
                            float(bitrate[0]))
                        )
                        self.send_callback("brate", bitrate[0])

            if self.docker_enabled:
                line = next(self.docker_stdout_stream, None)

                logging.debug(f"IPERF {line}")

                if isinstance(line, bytes):
                    line = line.decode('utf-8', errors='replace')

                for l in line.split("\n"):
                    l.strip()
                    bitrate = bitrate_pattern.findall(l)
                    if len(bitrate) > 0:
                        self.output.append(
                            ((datetime.now() - self.start_time).total_seconds(),
                            float(bitrate[0]))
                        )
                        self.send_callback("brate", bitrate[0])

        self.isRunning = False

    def __repr__(self):
        return f"Iperf Process Object, running: {self.isRunning}"

