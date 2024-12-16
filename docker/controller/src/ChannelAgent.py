# NOTE: this software is still under development, use with caution, do not include in the main system
import threading


from utils import kill_subprocess, start_subprocess


class ChannelAgent:
    def __init__(self):
        self.isRunning = False
        self.process = None
        self.output = ""
        self.initialized = False
        self.name = "NTIA User to User interface Agent"

    def start(self, config_file):
        self.process = start_subprocess(["uuagent", config_file])
        self.isRunning = True

        self.log_thread = threading.Thread(target=self.collect_logs,
                                           daemon=True)
        self.log_thread.start()

    def stop(self):
        kill_subprocess(self.process)
        self.isRunning = False

    def collect_logs(self):
        completed_text = "placeholder"
        while self.isRunning:
            if self.process:
                line = self.process.stdout.readline()
                if line:
                    self.output += line
                    if completed_text in self.output:
                        self.initialized = True

            else:
                self.output += "Process Terminated"
                break

    def __repr__(self):
        return f"{self.name}, running: {self.isRunning}"
