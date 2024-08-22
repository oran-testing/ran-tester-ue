from utils import start_subprocess, kill_subprocess
import threading
import time

class Iperf:
    def __init__(self):
        self.isRunning = False
        self.process = None
        self.output = ""
        self.initialized = False
        self.name = "Iperf -- Stopped"

    def start(self, args, process_type="server"):
        if process_type == "server":
            command = ["iperf3", "-s"] + args
        elif process_type == "client":
            command = ["sudo", "ip", "netns", "ue1","exec", "iperf3", "-c"] + args
        else:
            raise ValueError("Invalid Process Type")
            return
        self.process = start_subprocess(command)
        self.isRunning = True
        self.name = f"Iperf -- {process_type}"

        self.log_thread = threading.Thread(target=self.collect_logs, daemon=True)
        self.log_thread.start()
        time.sleep(5)
        self.initialized = True

    def stop(self):
        kill_subprocess(self.process)
        self.isRunning = False
        self.name = "Iperf -- Stopped"

    def collect_logs(self):
        while self.isRunning:
            if self.process:
                line = self.process.stdout.readline()
                if line:
                    self.output += '\n' + line.decode().strip()
            else:
                self.output += "Process Terminated"
                break

    def __repr__(self):
        return f"Iperf Process Object, running: {self.isRunning}"

