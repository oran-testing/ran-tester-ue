#!/usr/bin/env python3
import argparse
import threading
import time
import struct
import sys
import zmq
import numpy as np

SAMPLE_SIZE = 8
DEFAULT_SLOT_SAMPLES = 23040


class SignalCombiner:
    def __init__(self, gnb_tx_addr, spoofer_tx_addr,
                 ue_rep_addr, spoofer_rx_rep_addr,
                 slot_samples=DEFAULT_SLOT_SAMPLES):
        self.gnb_tx_addr = gnb_tx_addr
        self.spoofer_tx_addr = spoofer_tx_addr
        self.ue_rep_addr = ue_rep_addr
        self.spoofer_rx_rep_addr = spoofer_rx_rep_addr
        self.slot_samples = slot_samples
        self.gnb_buf = np.zeros(slot_samples, dtype=np.complex64)
        self.spoofer_buf = np.zeros(slot_samples, dtype=np.complex64)
        self.gnb_ready = threading.Event()
        self.spoofer_ready = threading.Event()
        self.lock = threading.Lock()
        self.running = True

    def eprint(self, msg):
        print(msg, file=sys.stderr)

    def iprint(self, msg):
        print(msg)

    def _poll_req(self, addr, buf, ready_event, name):
        self.iprint(f"[relay:{name}] starting {addr}")
        dummy = struct.pack('B', 0)
        ctx = zmq.Context()
        loop_n = 0
        while self.running:
            loop_n += 1
            sock = ctx.socket(zmq.REQ)
            sock.setsockopt(zmq.LINGER, 0)
            sock.setsockopt(zmq.RCVTIMEO, 500)
            if loop_n % 10 == 0:
                self.iprint(f"[relay:{name}] loop {loop_n}")
            try:
                sock.connect(addr)
            except zmq.ZMQError as e:
                self.eprint(f"[relay:{name}] connect: {e}")
                sock.close()
                time.sleep(2)
                continue
            try:
                sock.send(dummy)
            except zmq.ZMQError as e:
                self.eprint(f"[relay:{name}] send: {e}")
                sock.close()
                time.sleep(1)
                continue
            try:
                # zmq.RCVTIMEO=500ms — if no response, raises zmq.Again
                data = sock.recv()
                self.iprint(f"[relay:{name}] got {len(data)} bytes")
                samples = np.frombuffer(data, dtype=np.complex64)
                with self.lock:
                    n = min(len(samples), len(buf))
                    buf[:n] = samples[:n]
                ready_event.set()
                sock.close()
            except zmq.Again:
                self.eprint(f"[relay:{name}] recv timeout")
                sock.close()
                continue
            except zmq.ZMQError as e:
                self.eprint(f"[relay:{name}] recv: {e}")
                sock.close()
                time.sleep(1)
                continue

    def gnb_puller(self):
        self._poll_req(self.gnb_tx_addr, self.gnb_buf, self.gnb_ready, "gnb")

    def spoofer_puller(self):
        self._poll_req(self.spoofer_tx_addr, self.spoofer_buf, self.spoofer_ready, "spoofer")

    def ue_server(self, name="ue-server"):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.REP)
        sock.bind(self.ue_rep_addr)
        while self.running:
            try:
                sock.recv()
            except zmq.ZMQError:
                continue
            with self.lock:
                if self.gnb_ready.is_set():
                    signal = self.gnb_buf + self.spoofer_buf
                else:
                    signal = np.zeros(self.slot_samples, dtype=np.complex64)
            sock.send(signal.tobytes())
        sock.close()

    def spoofer_rx_server(self, name="spoofer-rx"):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.REP)
        sock.bind(self.spoofer_rx_rep_addr)
        while self.running:
            try:
                sock.recv()
            except zmq.ZMQError:
                continue
            with self.lock:
                if self.gnb_ready.is_set():
                    signal = self.gnb_buf.copy()
                else:
                    signal = np.zeros(self.slot_samples, dtype=np.complex64)
            sock.send(signal.tobytes())
        sock.close()

    def start(self):
        threads = [
            threading.Thread(target=self.gnb_puller, daemon=True, name="gnb-puller"),
            threading.Thread(target=self.spoofer_puller, daemon=True, name="spoofer-puller"),
            threading.Thread(target=self.ue_server, daemon=True, name="ue-server"),
            threading.Thread(target=self.spoofer_rx_server, daemon=True, name="spoofer-rx"),
        ]
        for t in threads:
            t.start()
        try:
            while all(t.is_alive() for t in threads):
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gnb-tx", default="tcp://172.22.0.1:5000")
    parser.add_argument("--spoofer-tx", default="tcp://zmq_ssb_spoof:7000")
    parser.add_argument("--ue-rep", default="tcp://*:5100")
    parser.add_argument("--spoofer-rx-rep", default="tcp://*:5101")
    args = parser.parse_args()
    SignalCombiner(args.gnb_tx, args.spoofer_tx, args.ue_rep,
                   args.spoofer_rx_rep).start()