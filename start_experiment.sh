#!/bin/bash
set -e
sudo rm -f /tmp/gnb.log /tmp/gnb_nohup.out /tmp/gnb.pid
sudo sh -c 'nohup /usr/local/bin/gnb -c /home/charles/ran-tester-ue/configs/srsran/gnb_zmq_relay.yaml > /tmp/gnb_nohup.out 2>&1 & echo $! > /tmp/gnb.pid'
echo "gNB PID=$(cat /tmp/gnb.pid)"

for i in $(seq 1 20); do
  if grep -q "Cell was activated" /tmp/gnb.log 2>/dev/null; then
    echo "gNB cell activated"
    break
  fi
  sleep 1
done

docker compose -f /home/charles/ran-tester-ue/docker-compose.relay.yml up -d 2>&1 | grep -E "Created|Started" || true
echo "relay started"

docker compose up -d controller influxdb 2>&1 | grep -E "Created|Started" || true
echo "controller+influxdb started"