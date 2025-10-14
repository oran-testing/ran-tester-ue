#!/bin/bash
set -u
set -o pipefail

print_progress() {
  local progress=$(( 100 * current / total ))
  local done=$(( progress / 2 ))
  local left=$(( 50 - done ))
  local fill
  local empty
  fill=$(printf "%${done}s" | tr ' ' '=')
  empty=$(printf "%${left}s" | tr ' ' ' ')
  printf "\rProgress: [${fill}${empty}] %d%% (%d/%d)" "$progress" "$current" "$total"
}

: "${ATTACKER_DIR:?set ATTACKER_DIR}"
: "${TRAFFIC_DIR:?set TRAFFIC_DIR}"
: "${RESULTS_DIR:?set RESULTS_DIR}"
: "${INTERFACE_DU:?set INTERFACE_DU}"
: "${INTERFACE_RU:?set INTERFACE_RU}"
: "${INJECTION_POINTS:?set INJECTION_POINTS (comma-separated)}"
: "${ATTACK_LIST:?set ATTACK_LIST (comma-separated .pcap filenames)}"
: "${TCPREPLAY_LOOP:?set TCPREPLAY_LOOP}"
: "${TCPREPLAY_TOPSPEED:?set TCPREPLAY_TOPSPEED (0 or 1)}"
: "${DURATION_SECONDS:?set DURATION_SECONDS}"
: "${KEEP_HISTORY:?set KEEP_HISTORY (0 or 1)}"
HOST_UID="${HOST_UID:-1000}"
HOST_GID="${HOST_GID:-1000}"

IFS=',' read -r -a INJECTION_POINTS_ARR <<< "$INJECTION_POINTS"
IFS=',' read -r -a ATTACK_LIST_ARR <<< "$ATTACK_LIST"

echo "[DEBUG] ATTACKER_DIR: $ATTACKER_DIR"
echo "[DEBUG] TRAFFIC_DIR: $TRAFFIC_DIR"
echo "[DEBUG] RESULTS_DIR: $RESULTS_DIR"
echo "[DEBUG] INJECTION_POINTS: $INJECTION_POINTS"
echo "[DEBUG] INTERFACE_DU: $INTERFACE_DU"
echo "[DEBUG] INTERFACE_RU: $INTERFACE_RU"
echo "[DEBUG] TCPREPLAY_LOOP: $TCPREPLAY_LOOP"
echo "[DEBUG] TCPREPLAY_TOPSPEED: $TCPREPLAY_TOPSPEED"
echo "[DEBUG] DURATION_SECONDS: $DURATION_SECONDS"
echo "[DEBUG] KEEP_HISTORY: $KEEP_HISTORY"

if [ "${#ATTACK_LIST_ARR[@]}" -eq 0 ]; then
  echo "[ERROR] ATTACK_LIST is empty"
  exit 1
fi

echo "Total attacks to run: ${#ATTACK_LIST_ARR[@]} files × ${#INJECTION_POINTS_ARR[@]} points"

total=$(( ${#ATTACK_LIST_ARR[@]} * ${#INJECTION_POINTS_ARR[@]} ))
current=0

mkdir -p "$RESULTS_DIR"
RESULTS_ROOT="$(cd "$RESULTS_DIR" && pwd -P)"

if [ "$KEEP_HISTORY" = "0" ]; then
  find "$RESULTS_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'run_*' -exec rm -rf --one-file-system {} +
fi

RUN_DIR="$(mktemp -d -p "$RESULTS_ROOT" "run_$(date +%Y%m%d_%H%M%S)_XXXX")"
RESULTS_DIR="$RUN_DIR"
echo "[DEBUG] Results will be saved to: $RESULTS_DIR"

CRASH_LOG="$RESULTS_DIR/crash_logs.txt"
: > "$CRASH_LOG"

if ! command -v tcpreplay >/dev/null 2>&1; then
  echo "[ERROR] tcpreplay not found"
  exit 1
fi

for ATTACK_FILE in "${ATTACK_LIST_ARR[@]}"; do
  for INJ in "${INJECTION_POINTS_ARR[@]}"; do
    ATTACK_NAME="${ATTACK_FILE%.pcap}"
    ATTACK_DIR="$RESULTS_DIR/${ATTACK_NAME}_INJ_${INJ}"
    mkdir -p "$ATTACK_DIR"

    echo ""
    echo "Starting replay: $ATTACK_FILE | Injection Point: $INJ"

    if [ "$INJ" = "DU" ]; then
      INTF="$INTERFACE_DU"
    else
      INTF="$INTERFACE_RU"
    fi
    if [ -z "${INTF:-}" ] || [ ! -e "/sys/class/net/$INTF" ]; then
      echo "[ERROR] Invalid or missing interface for $INJ: '$INTF'" | tee -a "$CRASH_LOG"
      ((current++)); print_progress; echo
      continue
    fi

    if [ ! -r "$TRAFFIC_DIR/$ATTACK_FILE" ]; then
      echo "[ERROR] PCAP not found or unreadable: $TRAFFIC_DIR/$ATTACK_FILE" | tee -a "$CRASH_LOG"
      ((current++)); print_progress; echo
      continue
    fi

    LOG_FILE="$ATTACK_DIR/tcpreplay_${ATTACK_NAME}_${INJ}.log"
    CMD=( tcpreplay --intf1="$INTF" --loop="$TCPREPLAY_LOOP" )
    if [ "$TCPREPLAY_TOPSPEED" = "1" ]; then
      CMD+=( --topspeed )
    fi
    CMD+=( "$TRAFFIC_DIR/$ATTACK_FILE" )

    echo "[DEBUG] $(printf "%q " "${CMD[@]}")"
    "${CMD[@]}" >"$LOG_FILE" 2>&1 &
    attacker_pid=$!

    sleep "$DURATION_SECONDS" || true
    kill $attacker_pid 2>/dev/null || true
    wait $attacker_pid 2>/dev/null || true

    echo "Completed $ATTACK_FILE | Injection $INJ"

    ((current++))
    print_progress
  done
done

echo ""
echo "[DEBUG] Cleaning up any stray tcpreplay..."
pkill -f tcpreplay 2>/dev/null || true

echo "All replays completed. See logs in: $RESULTS_DIR"

echo "[DEBUG] Restoring ownership on Traffic/ and attack_results/"
chown -R "$HOST_UID:$HOST_GID" "$TRAFFIC_DIR" "$RESULTS_DIR" 2>/dev/null || true
