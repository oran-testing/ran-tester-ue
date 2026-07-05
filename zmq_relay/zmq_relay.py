#!/usr/bin/env python3
import argparse
import threading
import time
import struct
import ctypes
import zmq
import numpy as np

SAMPLE_SIZE = 8  # sizeof(cf_t) = 2 * sizeof(float) = 8 bytes
DEFAULT_SLOT_SAMPLES = 23040  # 1ms at 23.04 MHz
POLL_TIMEOUT_MS = 100

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

    def gnb_puller(self):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.REQ)
        sock.connect(self.gnb_tx_addr)
        sock.setsockopt(zmq.RCVTIMEO, 5000)
        sock.setsockopt(zmq.SNDTIMEO, 5000)
        dummy = struct.pack('B', 0)
        while self.running:
            try:
                sock.send(dummy, zmq.NOBLOCK)
                data = sock.recv()
            except zmq.Again:
                time.sleep(0.001)
                continue
            samples = np.frombuffer(data, dtype=np.complex64)
            with self.lock:
                n = min(len(samples), self.slot_samples)
                self.gnb_buf[:n] = samples[:n]
            self.gnb_ready.set()
        sock.close()
        ctx.term()

    def spoofer_puller(self):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.REQ)
        sock.connect(self.spoofer_tx_addr)
        sock.setsockopt(zmq.RCVTIMEO, 5000)
        sock.setsockopt(zmq.SNDTIMEO, 5000)
        dummy = struct.pack('B', 0)
        while self.running:
            try:
                sock.send(dummy, zmq.NOBLOCK)
                data = sock.recv()
            except zmq.Again:
                time.sleep(0.001)
                continue
            samples = np.frombuffer(data, dtype=np.complex64)
            if len(samples) > 0 and np.any(np.abs(samples) > 1e-12):
                with self.lock:
                    n = min(len(samples), self.slot_samples)
                    self.spoofer_buf[:n] = samples[:n]
                self.spoofer_ready.set()
        sock.close()
        ctx.term()

    def ue_server(self):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.REP)
        sock.bind(self.ue_rep_addr)
        self.gnb_ready.wait()
        while self.running:
            try:
                req = sock.recv()
            except zmq.ZMQError:
                continue
            with self.lock:
                combined = self.gnb_buf + self.spoofer_buf
            sock.send(combined.tobytes())
        sock.close()
        ctx.term()

    def spoofer_rx_server(self):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.REP)
        sock.bind(self.spoofer_rx_rep_addr)
        self.gnb_ready.wait()
        while self.running:
            try:
                req = sock.recv()
            except zmq.ZMQError:
                continue
            with self.lock:
                signal = self.gnb_buf.copy()
            sock.send(signal.tobytes())
        sock.close()
        ctx.term()

    def start(self):
        threads = [
            threading.Thread(target=self.gnb_puller, daemon=True, name="gnb-puller"),
            threading.Thread(target=self.spoofer_puller, daemon=True, name="spoofer-puller"),
            threading.Thread(target=self.ue_server, daemon=True, name="ue-server"),
            threading.Thread(target=self.spoofer_rx_server, daemon=True, name="spoofer-rx-server"),
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
    parser = argparse.ArgumentParser(description="ZMQ Signal Combiner Relay")
    parser.add_argument("--gnb-tx", default="tcp://172.22.0.1:5000",
                        help="gNB TX REP address")
    parser.add_argument("--spoofer-tx", default="tcp://zmq_ssb_spoof:6000",
                        help="SSB spoofer TX REP address")
    parser.add_argument("--ue-rep", default="tcp://*:5100",
                        help="UE RX REP bind address")
    parser.add_argument("--spoofer-rx-rep", default="tcp://*:5101",
                        help="Spoofer RX REP bind address")
    args = parser.parse_args()

    relay = SignalCombiner(
        gnb_tx_addr=args.gnb_tx,
        spoofer_tx_addr=args.spoofer_tx,
        ue_rep_addr=args.ue_rep,
        spoofer_rx_rep_addr=args.spoofer_rx_rep,
    )
    relay.start()
