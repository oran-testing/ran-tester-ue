#!/bin/bash
set -e
echo "Killing all experiment processes..."
sudo kill $(cat /tmp/gnb.pid 2>/dev/null) 2>/dev/null || true
sudo pkill -f "gnb -c" 2>/dev/null || true
docker compose -f /home/charles/ran-tester-ue/docker-compose.relay.yml down 2>/dev/null || true
docker compose down controller influxdb 2>/dev/null || true
sleep 2
pgrep -x gnb && echo "WARNING: gnb still running" || echo "gNB stopped"