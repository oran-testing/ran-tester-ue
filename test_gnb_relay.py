#!/usr/bin/env python3
import zmq, struct, sys, time, numpy as np

def main():
    ctx = zmq.Context()
    s = ctx.socket(zmq.REQ)
    s.setsockopt(zmq.LINGER, 0)
    s.setsockopt(zmq.RCVTIMEO, 3000)
    s.setsockopt(zmq.SNDTIMEO, 1000)
    
    print(f"Connecting to tcp://172.22.0.1:5000...")
    s.connect('tcp://172.22.0.1:5000')
    print("Connected, sending request...")
    
    s.send(struct.pack('B', 0))
    print("Sent, waiting for response...")
    
    t0 = time.time()
    try:
        data = s.recv()
        elapsed = time.time() - t0
        n = len(data) // 8  # complex64 = 8 bytes
        arr = np.frombuffer(data, dtype=np.complex64)
        power = np.mean(np.abs(arr)**2)
        print(f"Received {len(data)} bytes ({n} samples) in {elapsed*1000:.0f}ms, avg power={power:.2e}")
    except zmq.Again:
        print(f"TIMEOUT after {time.time()-t0:.1f}s - no response from gNB")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
