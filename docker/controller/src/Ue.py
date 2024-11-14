import time
import os
import threading
import asyncio
from Iperf import Iperf
from Ping import Ping
from utils import kill_subprocess, send_command, start_subprocess
import websockets

class Ue:
    def __init__(self, ue_index):
        self.ue_index = ue_index
        self.isRunning = False
        self.isConnected = False
        self.process = None
        self.iperf_client = Iperf()
        self.ping_client = Ping()
        self.output = ""
        self.rnti = ""
        self.websocket_client = None  # Single WebSocket client
        self.log_buffer = []  # Store logs until a client connects

    async def websocket_handler(self, websocket, path):
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
            print("WebSocket client disconnected")
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
        start_server = websockets.serve(self.websocket_handler, "localhost", 8765 + self.ue_index)
        loop.run_until_complete(start_server)
        loop.run_forever()

    def start(self, args, mode="baremetal"):
        if mode == "docker":
            # Docker setup if needed
            pass
        else:
            command = ["sudo", "srsue"] + args
            self.process = start_subprocess(command)
            self.isRunning = True
            self.stop_thread = threading.Event()

            # Start the WebSocket server
            self.start_websocket_server()

            # Start the log collection thread
            self.log_thread = threading.Thread(target=self.collect_logs, daemon=True)
            self.log_thread.start()
            self.send_message("command", " ".join(command))

    def send_message(self, message_type, message_text):
        """Send either a 'command' or 'log' message to the connected WebSocket client."""
        message_str = '{ "type": "' + message_type + '", "text": "' + message_text + '"}'
        if self.websocket_client:
            try:
                # Send the message to the connected WebSocket client
                asyncio.run(self.websocket_client.send(message_str))
            except Exception as e:
                print(f"Failed to send message: {e}")
        else:
            # Buffer log messages if no client is connected
            if message_type == "log":
                self.log_buffer.append(message_str)

    def collect_logs(self):
        """Collect logs from the process and send them to the WebSocket client."""
        while self.isRunning and not self.stop_thread.is_set():
            if self.process and self.process.poll() is None:
                line = self.process.stdout.readline().strip()

                if isinstance(line, bytes):
                    line = line.decode('utf-8', errors='replace')

                if line:
                    self.send_message("log", line)  # Send log to WebSocket client

                    self.output += line
                    if "rnti" in line:
                        self.rnti = line.split("0x")[1][:4]
                    if "PDU" in line:
                        self.start_metrics()
                        self.isConnected = True
            else:
                if self.websocket_client:
                    self.send_message("log", "Process Terminated")
                self.isRunning = False
                break

    def stop(self):
        self.stop_thread.set()
        kill_subprocess(self.process)
        self.iperf_client.stop()
        self.isRunning = False

    def __repr__(self):
        return f"srsRAN UE{self.ue_index} object, running: {self.isRunning}"

if __name__ == "__main__":
    test = Ue(1)
    test.start(["./configs/zmq/ue_zmq.conf"])
    while True:
        time.sleep(1)

