#!/bin/bash
python3 /zmq_relay.py \
  --gnb-tx "${GNB_TX:-tcp://172.22.0.1:5000}" \
  --spoofer-tx "${SPOOFER_TX:-tcp://zmq_ssb_spoof:7000}" \
  --ue-rep "${UE_REP:-tcp://*:5100}" \
  --spoofer-rx-rep "${SPOOFER_RX_REP:-tcp://*:5101}"