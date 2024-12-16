import os
import sys
from datetime import datetime
import re
import threading

from utils import kill_subprocess, start_subprocess


class Ping:
    def __init__(self, send_message_callback):
        self.isRunning = False
        self.process = None
        self.output = []
        self.initialized = False
        self.name = "Ping -- Stopped"
        self.process_type = ""
        self.send_callback = send_message_callback

    def start(self, args):
        # Construct the ping command
        command = ["ping"] + args
        self.process = start_subprocess(command)
        self.isRunning = True
        self.name = "Ping -- Running"
        self.start_time = datetime.now()

        self.log_thread = threading.Thread(target=self.collect_logs, daemon=True)
        self.log_thread.start()
        self.initialized = True

    def stop(self):
        kill_subprocess(self.process)
        self.isRunning = False
        self.name = "Ping -- Stopped"

    def collect_logs(self):
        latency_pattern = re.compile(r'time=(\d+\.?\d*) ms')
        while self.isRunning:
            if self.process:
                line = self.process.stdout.readline()
                if line:
                    latency = latency_pattern.findall(line)
                    if latency:
                        self.output.append(
                            ((datetime.now() - self.start_time).total_seconds(),
                            float(latency[0]) * 1000)
                        )
                        self.send_callback("latency", latency[0])

            else:
                self.output.append(0.0)
                self.isRunning = False
                break

    def __repr__(self):
        return f"Ping Process Object, running: {self.isRunning}"

if __name__ == "__main__":
    ping_handle = Ping()
    ping_handle.start(["8.8.8.8"])
    while True:
        print(ping_handle.output)
