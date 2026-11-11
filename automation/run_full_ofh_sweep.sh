#!/bin/bash
set -euo pipefail

BASE="/home/charles/mcp-intelligent-tester-ue/ofh"
REPO="/home/charles/ran-tester-ue"
AUTOMATION="$REPO/automation"

mkdir -p "$BASE"

echo "============================================="
echo " OFH Full Sweep — Victim Collection"
echo " Base: $BASE"
echo "============================================="

# 1. Verify emulators are running (pre-existing from sibling repo)
echo
echo "--- Verifying emulators ---"
for c in ru_emulator gnb_emulator; do
    if docker inspect "$c" >/dev/null 2>&1; then
        echo "  $c: RUNNING"
    else
        echo "  ERROR: $c not running — start sibling repo stack first"
        exit 1
    fi
done

# 2. Verify controller
echo
echo "--- Verifying controller API ---"
curl -sf -m 5 -H 'Authorization: Bearer default_changeme' http://localhost:1343/list | grep -q running || {
    echo "ERROR: Controller not responding"
    exit 1
}
echo "  Controller OK"

# 3. Ensure pcap exists
echo
echo "--- Staging pcap ---"
mkdir -p "$REPO/.generated/Traffic"
if [ ! -f "$REPO/.generated/Traffic/cp_dl_long_1mb_DR_10.pcap" ]; then
    cp /home/charles/mcp-intelligent-tester-ue/configs/ofh/Traffic/*.pcap "$REPO/.generated/Traffic/" 2>/dev/null || true
fi
ls -lh "$REPO/.generated/Traffic/"

# 4. Ensure attacker image is pulled
docker image inspect ghcr.io/oran-testing/ofh >/dev/null 2>&1 || docker pull ghcr.io/oran-testing/ofh

# Helper: collect victim logs into a step dir
collect_victim_logs() {
    local step_dir=$1
    [ -d "$step_dir" ] || return 0

    # ru_emu docker logs - OFH stats, loss messages
    docker logs --tail 500 ru_emulator 2>/dev/null > "$step_dir/ru_emu_logs.txt" 2>/dev/null
    [ -s "$step_dir/ru_emu_logs.txt" ] || echo "[No ru_emu logs]" > "$step_dir/ru_emu_logs.txt"

    # gnb docker logs - srsRAN gNB output
    docker logs --tail 500 gnb_emulator 2>/dev/null > "$step_dir/gnb_logs.txt" 2>/dev/null
    [ -s "$step_dir/gnb_logs.txt" ] || echo "[No gnb logs]" > "$step_dir/gnb_logs.txt"

    echo "  Victim logs -> $(basename "$step_dir")"
}

collect_all_victim_logs() {
    local out_dir=$1
    echo "  Collecting per-step victim logs..."
    for sd in "$out_dir"/step_ofh_sweep_*; do
        [ -d "$sd" ] || continue
        collect_victim_logs "$sd"
    done
}

# 5. CONFIG MODE
echo
echo "===================== MODE: config ====================="
OUT_CONFIG="$BASE/config"
rm -rf "$OUT_CONFIG"
cd "$AUTOMATION"
uv run python3 -m ofh_sweep.cli \
    --mode config \
    --output "$OUT_CONFIG" \
    --no-sudo \
    --settle 10 \
    --rf-type none 2>&1
echo "--- Config mode rc=$? ---"
collect_all_victim_logs "$OUT_CONFIG"

# 6. MCP MODE
echo
echo "===================== MODE: mcp ========================"
OUT_MCP="$BASE/mcp"
rm -rf "$OUT_MCP"
cd "$AUTOMATION"
uv run python3 -m ofh_sweep.cli \
    --mode mcp \
    --output "$OUT_MCP" \
    --no-sudo \
    --settle 10 \
    --rf-type none 2>&1
echo "--- MCP mode rc=$? ---"
collect_all_victim_logs "$OUT_MCP"

# 7. LLM MODE
echo
echo "===================== MODE: llm ========================"
OUT_LLM="$BASE/llm"
rm -rf "$OUT_LLM"
cd "$AUTOMATION"
uv run python3 -m ofh_sweep.cli \
    --mode llm \
    --output "$OUT_LLM" \
    --rf-type none 2>&1
echo "--- LLM mode rc=$? ---"

# 8. Summary
echo
echo "============================================="
echo " RESULTS"
echo "============================================="

for d in "$BASE/config" "$BASE/mcp" "$BASE/llm"; do
    name=$(basename "$d")
    if [ -d "$d" ]; then
        step_count=$(find "$d" -maxdepth 1 -type d -name 'step_ofh_sweep_*' 2>/dev/null | wc -l)
        ru_count=$(find "$d" -maxdepth 2 -name 'ru_emu_logs.txt' -not -empty 2>/dev/null | wc -l)
        gnb_count=$(find "$d" -maxdepth 2 -name 'gnb_logs.txt' -not -empty 2>/dev/null | wc -l)
        echo "  $name: $step_count steps, $ru_count with RU logs, $gnb_count with gNB logs"
        [ -f "$d/SUMMARY.md" ] && echo "    summary: $d/SUMMARY.md"
        [ -f "$d/metrics.csv" ] && echo "    metrics: $d/metrics.csv"
        [ -f "$d/metrics.json" ] && echo "    metrics_json: $d/metrics.json"
    fi
done

echo
echo "All outputs in: $BASE"
echo "Done."