import re
import select
import sys
import threading
import os
import time
import csv
from datetime import datetime

from utils import kill_subprocess, start_subprocess


class Metrics:
    def __init__(self, send_message_callback):
        self.isRunning = False
        self.send_callback = send_message_callback
        self.file_path = ""


    def get_metrics_config(self, file_path):
        keys = ["metrics_csv_enable", "metrics_csv_filename"]
        metrics_config = {}

        try:
            with open(file_path, "r") as file:
                lines = file.readlines()

            for line in lines:
                # Strip whitespace and skip empty or comment lines
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith(";"):
                    continue

                # Check if line contains any of the keys
                for key in keys:
                    if stripped.startswith(key):
                        # Split the line by '=' and trim spaces
                        _, value = stripped.split("=", 1)
                        metrics_config[key] = value.strip()
                        break

            # Ensure all required keys are found
            for key in keys:
                if key not in metrics_config:
                    raise KeyError(f"Key '{key}' not found in the file.")

            metrics_config["metrics_csv_enable"] = metrics_config["metrics_csv_enable"].lower() == "true"

            return metrics_config

        except FileNotFoundError:
            raise FileNotFoundError(f"The file '{file_path}' was not found.")
        except ValueError as e:
            raise ValueError(f"Error processing file '{file_path}': {e}")

        return metrics_config

    def start(self, config_path, docker_container):
        self.docker_container = docker_container
        metrics_config = self.get_metrics_config(config_path)
        if not metrics_config["metrics_csv_enable"]:
            return
        self.file_path = metrics_config["metrics_csv_filename"]
        self.isRunning = True
        self.log_thread = threading.Thread(target=self.report_new_metric, daemon=True)
        self.log_thread.start()

    def report_new_metric(self):
        last_index = 0
        while True:
            metrics_output = []
            if self.docker_container:
                command = f"cat {self.file_path}"
                exec_result = self.docker_container.exec_run(command)
                if exec_result.exit_code != 0:
                    logging.error(f"Failed to read {self.file_path}")
                    time.sleep(10)
                    continue
                file_content = exec_result.output.decode('utf-8')
                metrics_output = file_content.split()
            else:
                with open(self.file_path, 'r') as file:
                    metrics_output = file.readlines()

            if len(metrics_output) > last_index:
                metrics_index_map = metrics_output[0].split(";")
                for i in range(last_index, len(metrics_output) - 1):
                    for value in metrics_output[i].split(';'):
                        if value and i < len(metrics_index_map) and metrics_index_map[i] in ["dl_brate", "rsrp", "dl_mcs", "dl_snr"]:
                            self.send_callback(metrics_index_map[i], value)
                last_index = len(metrics_output)
            time.sleep(10)

    def __repr__(self):
        return f"Metrics Manager Process Object, running: {self.isRunning}"

if __name__ == "__main__":
    # test class functionality
    test = Metrics(lambda msg_type, msg_text: print(msg_type + " : " + msg_text))
    test.start("../../../configs/zmq/ue_zmq.conf")
    while True:
        time.sleep(1)
