#!/bin/bash
RESULTS_FILE="/tmp/experiment_results.txt"
SSB_COUNT=0
TOTAL_RUNS=100

echo "Experiment: $TOTAL_RUNS runs, recording SSB with barred=y" > "$RESULTS_FILE"
date >> "$RESULTS_FILE"
echo "---" >> "$RESULTS_FILE"

for i in $(seq 1 $TOTAL_RUNS); do
  # Start gNB
  sudo rm -f /tmp/gnb.log
  sudo nohup /usr/local/bin/gnb -c /home/charles/ran-tester-ue/configs/srsran/gnb_zmq_relay.yaml &>/tmp/gnb_nohup.out &
  GNB_PID=$!

  for j in $(seq 1 20); do
    if grep -q "Cell was activated" /tmp/gnb.log 2>/dev/null; then
      break
    fi
    sleep 1
  done

  # Start relay
  docker compose -f /home/charles/ran-tester-ue/docker-compose.relay.yml up -d 2>/dev/null
  # Start controller + influxdb (controller starts UE automatically)
  docker compose up -d controller influxdb 2>/dev/null

  # Wait for UE to attempt connection
  sleep 15

  # Check controller logs for SSB with barred=y
  if docker logs controller 2>/dev/null | grep -q "barred=y"; then
    SSB_COUNT=$((SSB_COUNT + 1))
    echo "RUN $i: SSB with barred=y FOUND" >> "$RESULTS_FILE"
    docker logs controller 2>/dev/null | grep "barred=y" | head -3 >> "$RESULTS_FILE"
  else
    echo "RUN $i: no barred=y" >> "$RESULTS_FILE"
  fi

  # Kill all
  sudo pkill -f "gnb -c" 2>/dev/null || true
  docker compose -f /home/charles/ran-tester-ue/docker-compose.relay.yml down 2>/dev/null || true
  docker compose down controller influxdb 2>/dev/null || true
  sleep 3
done

echo "---" >> "$RESULTS_FILE"
echo "Total runs: $TOTAL_RUNS" >> "$RESULTS_FILE"
echo "SSB with barred=y found: $SSB_COUNT times" >> "$RESULTS_FILE"
date >> "$RESULTS_FILE"
cat "$RESULTS_FILE"