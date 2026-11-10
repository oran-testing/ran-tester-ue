"""Sushant LLM backend: run the SSB spoofer sweep through sushant-XD/llm_worker.

This backend creates a config for the ``sushant`` branch of
``sushant-XD/llm_worker`` (https://github.com/sushant-XD/llm_worker/tree/sushant)
which supports OpenRouter API (no local GPU needed) and the JSON-array action
plan format.

The generated config uses the JSON-array action format where the LLM worker's
``Planner`` produces an array of actions (start/stop/logs/health/list) and the
``Executor`` generates per-component configuration JSON that a validator converts
to the controller's native config format (YAML/TOML/INI).

This backend handles both the ssb_spoofer sweep AND a victim rtue so that UE
debug logs are collected alongside spoofer metrics.

Usage via ssb_sweep.cli::

    uv run python3 -m ssb_sweep.cli --mode sushant --apply-spec

Then rebuild the llm_worker image and restart the controller::

    docker build -f dockerfiles/Dockerfile.llm_worker \\
        -t ghcr.io/sushant-XD/llm_worker .
    sudo docker compose up -d --force-recreate controller

After the llm_worker completes its sweep, collect logs with::

    uv run python3 -m ssb_sweep.cli --mode sushant --collect
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ssb_sweep.spec import (
    BURST_LENGTH_MS,
    DEFAULT_BASE_CONFIG,
    FIXED_TX_GAIN_DB,
    SWEEP_STEPS_US,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUSHANT_RUN_SPEC_ENTRY = {
    "component": "sushant-XD/llm_worker",
    "worker_thread": "llm_worker",
    "name": "sushant_llm_worker",
    "config_file": "configs/llm/sushant_ssb_spoofer_sweep.yaml",
    "results_dir": "sushant_ssb_sweep_logs",
    "rf": {"type": "none"},
}

SUSHANT_BUILD_SPEC_ENTRY = {
    "component": "sushant-XD/llm_worker",
    "branch": "sushant",
    "pull": False,
}

CONFIG_FILENAME = "sushant_ssb_spoofer_sweep.yaml"

CONFIG_OUTPUT_PATH = Path("configs") / "llm" / CONFIG_FILENAME

# OpenRouter model - no GPU needed on the host.
DEFAULT_MODEL = "openai/gpt-4o"

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

PLANNER_PROMPT = """\
You are a test orchestration planner for an SSB spoofer attack sweep against a 5G gNB.
Your task is to produce ONE JSON array of actions that will run the sweep.

Available component types:
  - "rtue" : a 5G User Equipment (victim UE) that will attempt to attach to the gNB
  - "ssb_spoofer" : an SSB spoofer that broadcasts fake SSB blocks to disrupt the UE

Available actions (endpoints):
  - "start" : start a component. Requires: "id", "type", "desc" (English description),
              "endpoint": "start", "rf": "b200"|"zmq"|"none"
  - "stop" : stop a component. Requires: "id", "endpoint": "stop"
  - "logs" : fetch logs. Requires: "id", "type", "endpoint": "logs"
  - "health" : check component health. Requires: "id", "endpoint": "health"
  - "list" : list running components. Requires: "endpoint": "list"

CRITICAL RULES:
1. Return ONLY a JSON array inside a ```json fenced block.
2. The victim UE (rtue) must be started FIRST and stopped LAST.
3. For each sweep step, start an ssb_spoofer with the appropriate burst_interval_us,
   check its health, fetch its logs, then stop it.
4. The "desc" field must describe the configuration to a skilled operator in detail,
   including RF parameters, frequencies, gain settings, and attack parameters.
5. The "rf" field must be "b200" for hardware USRP or "none" for the planner itself.

Example output format:
```json
[
  {"id": "victim_ue_001", "type": "rtue", "desc": "...", "endpoint": "start", "rf": "b200"},
  {"endpoint": "list"},
  {"id": "victim_ue_001", "endpoint": "health"},
  {"id": "ssb_spoofer_sweep_1_19000us", "type": "ssb_spoofer", "desc": "...", "endpoint": "start", "rf": "b200"},
  {"id": "ssb_spoofer_sweep_1_19000us", "endpoint": "health"},
  {"id": "ssb_spoofer_sweep_1_19000us", "type": "ssb_spoofer", "endpoint": "logs"},
  {"id": "ssb_spoofer_sweep_1_19000us", "endpoint": "stop"},
  ...
  {"id": "victim_ue_001", "type": "rtue", "endpoint": "stop"}
]
```"""

EXECUTOR_PROMPT = """\
You are a component configuration generator. Given an action description and
component type, produce a valid JSON configuration object that the controller
accepts.

For "rtue" (victim UE), produce a flat JSON object with these keys:
  id, rf_srate, rf_tx_gain, rf_rx_gain, rf_nof_antennas, rf_device_name,
  rf_device_args, rf_time_adv_nsamples, rat_eutra_dl_earfcn, rat_eutra_nof_carriers,
  rat_nr_bands, rat_nr_nof_carriers, rat_nr_max_nof_prb, rat_nr_nof_prb,
  pcap_enable, pcap_mac_filename, pcap_mac_nr_filename, pcap_nas_filename,
  log_all_level, usim_mode, usim_algo, usim_opc, usim_k, usim_imsi, usim_imei,
  rrc_release, rrc_ue_category, nas_apn, nas_apn_protocol, gui_enable,
  gw_ip_devname, gw_ip_netmask,
  general_metrics_influxdb_enable, general_metrics_influxdb_url,
  general_metrics_influxdb_port, general_metrics_influxdb_org,
  general_metrics_influxdb_token, general_metrics_influxdb_bucket,
  general_metrics_period_secs, general_ue_data_identifier

For "ssb_spoofer", produce a JSON object with nested sections:
  id (top level), rf: {device_name, device_args, rx_freq_hz, tx_freq_hz,
  srate_hz, rx_gain_db, tx_gain_db},
  ssb: {pattern, scs_khz, periodicity_ms, ssb_freq_offset_hz, beta_pss,
        beta_sss, beta_pbch, beta_pbch_dmrs},
  attack: {target_pci, scan_for_target, modify_cell_barred, cell_barred_value,
           modify_coreset0_idx, coreset0_idx_value, modify_ss0_idx, ss0_idx_value,
           modify_intra_freq_resel, intra_freq_resel_value, tx_power_offset_db,
           continuous_tx, max_bursts, burst_interval_us, burst_length_ms},
  operation: {scan_duration_sec, log_level, log_file, save_samples, samples_file}

Return ONLY valid JSON in a ```json fenced block.
"""


def _build_ssb_spoofer_prompt() -> str:
    sweeps = ", ".join(str(u) for u, _ in SWEEP_STEPS_US)
    return f"""\
You are configuring an SSB spoofer. Return a JSON object with an "id" plus
nested objects for rf, ssb, attack, and operation.

Use these guardrail values (B210 limits: max center freq 6 GHz, max sample rate 61.44 MHz):

rf:
  device_name: uhd
  device_args: "type=b200"
  rx_freq_hz: 1842050000            # band 3 downlink center
  tx_freq_hz: 1842050000
  srate_hz: 23040000
  rx_gain_db: 40.0
  tx_gain_db: {FIXED_TX_GAIN_DB}    # fixed by test

ssb:
  pattern: A
  scs_khz: 15
  periodicity_ms: 10
  ssb_freq_offset_hz: 0
  beta_pss: 1.0
  beta_sss: 1.0
  beta_pbch: 1.0
  beta_pbch_dmrs: 1.0

attack:                              # all fields must be present
  target_pci: 1
  scan_for_target: true
  modify_cell_barred: true
  cell_barred_value: true
  modify_coreset0_idx: true
  coreset0_idx_value: 15
  modify_ss0_idx: true
  ss0_idx_value: 15
  modify_intra_freq_resel: false
  intra_freq_resel_value: false
  tx_power_offset_db: 0.0
  continuous_tx: true
  max_bursts: 0
  burst_interval_us: <sweep value, one of {sweeps}>
  burst_length_ms: {BURST_LENGTH_MS}

operation:
  scan_duration_sec: 30.0
  log_level: info
  log_file: ssb_spoofer.log
  save_samples: false
  samples_file: rx_samples.dat

Return ONLY valid JSON in a ```json fenced block. The "id" must be at top level.
"""


def _build_rtue_prompt() -> str:
    return """\
You are configuring a 5G UE (rtue) that will act as a victim for an SSB spoofer
attack. Return a flat JSON object with the following keys and realistic values.

Use guardrail values:
  - Band 3 downlink, 20 MHz channel (106 PRB)
  - srate 23.04 Msps
  - tx_gain 70 dB, rx_gain 40 dB
  - UHD device (B210) with serial to disambiguate from the spoofer

Required keys with typical values:
  id: "victim_ue_001"  (or as specified)
  rf_srate: 23040000
  rf_tx_gain: 70
  rf_rx_gain: 40
  rf_nof_antennas: 1
  rf_device_name: "uhd"
  rf_device_args: "type=b200,serial=32C74B3"   # use a distinct serial
  rf_time_adv_nsamples: 300
  rat_eutra_dl_earfcn: 2850
  rat_eutra_nof_carriers: 0
  rat_nr_bands: 3
  rat_nr_nof_carriers: 1
  rat_nr_max_nof_prb: 106
  rat_nr_nof_prb: 106
  pcap_enable: "none"
  pcap_mac_filename: "/tmp/ue_mac.pcap"
  pcap_mac_nr_filename: "/tmp/ue_mac_nr.pcap"
  pcap_nas_filename: "/tmp/ue_nas.pcap"
  log_all_level: "debug"               # enable debug logging for UE diagnostics
  usim_mode: "soft"
  usim_algo: "milenage"
  usim_opc: "63BFA50EE6523365FF14C1F45F88737D"
  usim_k: "00112233445566778899aabbccddeeff"
  usim_imsi: "001010123456789"
  usim_imei: "353490069873319"
  rrc_release: 15
  rrc_ue_category: 4
  nas_apn: "srsapn"
  nas_apn_protocol: "ipv4"
  gui_enable: false
  gw_ip_devname: "tun_rtue"
  gw_ip_netmask: "255.255.255.0"
  general_metrics_influxdb_enable: true
  general_metrics_influxdb_url: "influxdb"
  general_metrics_influxdb_port: 8086
  general_metrics_influxdb_org: "rtu"
  general_metrics_influxdb_token: "605bc59413b7d5457d181ccf20f9fda15693f81b068d70396cc183081b264f3b"
  general_metrics_influxdb_bucket: "rtusystem"
  general_metrics_period_secs: 0.5
  general_ue_data_identifier: "victim_ue_001"

The log_all_level MUST be "debug" to collect UE debug logs.

Return ONLY valid JSON in a ```json fenced block.
"""


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------

def build_sushant_config() -> dict[str, Any]:
    """Build the llm_worker config dict for the SSB spoofer sweep.

    Uses the JSON-array action format supported by the ``sushant`` branch of
    ``sushant-XD/llm_worker``. Includes both ssb_spoofer and rtue prompts.
    """
    sweeps = ", ".join(str(u) for u, _ in SWEEP_STEPS_US)
    values_block = "[" + ", ".join(f'{{"burst_interval_us": {u}, "label": "{l}"}}' for u, l in SWEEP_STEPS_US) + "]"

    user_prompt = (
        f"Run an SSB spoofer attack sweep against the gNB.\n\n"
        f"1. FIRST, start a victim UE (rtue) with id 'victim_ue_001' that will attempt to "
        f"attach to the gNB. Enable debug logging (log_all_level=debug) so we can collect "
        f"UE debug logs.\n"
        f"2. Check the UE health and list components.\n"
        f"3. For each of these burst_interval_us values in order: {sweeps}, do:\n"
        f"   a. Start an ssb_spoofer with the current burst_interval_us, burst_length_ms={BURST_LENGTH_MS},\n"
        f"      and the fixed attack settings (modify_cell_barred=true, modify_coreset0_idx=true,\n"
        f"      modify_ss0_idx=true, tx_gain_db={FIXED_TX_GAIN_DB}).\n"
        f"   b. Wait a few seconds for the attack to take effect.\n"
        f"   c. Check the spoofer health and fetch its logs.\n"
        f"   d. Check the UE health and fetch its logs (to get UE debug information).\n"
        f"   e. Stop the spoofer.\n"
        f"4. After all sweep steps are done, stop the victim UE (rtue).\n\n"
        f"Name each ssb_spoofer component id like 'ssb_spoofer_sweep_1_19000us', "
        f"'ssb_spoofer_sweep_2_9000us', and so on.\n\n"
        f"Sweep steps definition:\n{values_block}\n\n"
        f"Periodicity ms = burst_length_ms + (burst_interval_us / 1000).\n"
        f"The UE debug logs are CRITICAL for measuring L1/L2/L3 metrics."
    )

    return {
        "model": DEFAULT_MODEL,
        "provider": "openrouter",
        "results_dir": "sushant_ssb_sweep_logs",
        "nof_plan_attempts": 10,
        "nof_exec_attempts": 10,
        "planner": PLANNER_PROMPT,
        "executor": EXECUTOR_PROMPT,
        "ssb_spoofer": _build_ssb_spoofer_prompt(),
        "rtue": _build_rtue_prompt(),
        "user_prompt": user_prompt,
    }


# ---------------------------------------------------------------------------
# Write config
# ---------------------------------------------------------------------------

def write_sushant_config(
    repo_root: Path,
    output_path: Path | None = None,
) -> Path:
    """Write the llm_worker config YAML to disk.

    Args:
        repo_root: Project root directory.
        output_path: Where to write. Defaults to ``configs/llm/sushant_ssb_spoofer_sweep.yaml``.

    Returns:
        Path to the written config file.
    """
    if output_path is None:
        output_path = repo_root / CONFIG_OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(build_sushant_config(), sort_keys=False, indent=2),
        "utf-8",
    )
    return output_path


# ---------------------------------------------------------------------------
# Spec manipulation
# ---------------------------------------------------------------------------

def _backup_spec(spec_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = spec_path.with_suffix(spec_path.suffix + f".bak_{stamp}")
    shutil.copy2(spec_path, backup)
    return backup


def inject_sushant_run_spec(
    spec_path: Path,
    apply: bool = False,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Insert the sushant llm_worker run_spec + build_spec entries into spec.yaml.

    Adds:
      - A ``build_spec`` entry for ``sushant-XD/llm_worker`` (branch ``sushant``,
        ``pull: false`` so a locally-built image is used).
      - A ``run_spec`` entry for the sushant llm_worker.

    Returns a dict with the diff/result. If ``apply`` is False, no file is
    modified and operator instructions are returned.
    """
    spec = yaml.safe_load(spec_path.read_text("utf-8"))

    # Add build_spec entry (dedup by component name).
    build_spec = [x for x in spec.get("build_spec", [])
                  if x.get("component") != SUSHANT_BUILD_SPEC_ENTRY["component"]]
    build_spec.append(SUSHANT_BUILD_SPEC_ENTRY)
    spec["build_spec"] = build_spec

    # Add run_spec entry (dedup by name).
    run_spec = [x for x in spec.get("run_spec", [])
                if x.get("name") != SUSHANT_RUN_SPEC_ENTRY["name"]]
    run_spec.append(SUSHANT_RUN_SPEC_ENTRY)
    spec["run_spec"] = run_spec

    if not apply:
        return {
            "applied": False,
            "spec_path": str(spec_path),
            "proposed_build_spec": SUSHANT_BUILD_SPEC_ENTRY,
            "proposed_run_spec": SUSHANT_RUN_SPEC_ENTRY,
            "instructions": (
                "Run the following to build the llm_worker image from the sushant branch:\n"
                "  docker build -f dockerfiles/Dockerfile.llm_worker"
                " -t ghcr.io/sushant-XD/llm_worker .\n\n"
                "Then restart the controller to pick up the new run_spec:\n"
                "  sudo docker compose up -d --force-recreate controller\n\n"
                "The controller will start the llm_worker automatically. Monitor with:\n"
                "  docker logs -f ran-tester-ue-controller-1\n"
                "  docker ps -a --filter name=sushant\n\n"
                "After the sweep completes, collect results:\n"
                "  uv run python3 -m ssb_sweep.cli --mode sushant --collect"
            ),
        }

    backup = _backup_spec(spec_path)
    with spec_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(spec, fh, sort_keys=False, indent=2)
    return {
        "applied": True,
        "backup": str(backup),
        "spec_path": str(spec_path),
        "build_spec": SUSHANT_BUILD_SPEC_ENTRY,
        "run_spec": SUSHANT_RUN_SPEC_ENTRY,
    }


# ---------------------------------------------------------------------------
# Log collection helpers (used after the llm_worker completes)
# ---------------------------------------------------------------------------

def build_log_collection_config() -> dict[str, Any]:
    """Build a log collection plan that fetches UE debug logs.

    Returns a dict with the component IDs that the sweep created, used
    for post-sweep log retrieval.
    """
    step_ids = [
        f"ssb_spoofer_sweep_{idx}_{burst_us}us"
        for idx, (burst_us, _) in enumerate(SWEEP_STEPS_US, start=1)
    ]
    return {
        "victim_ue_id": "victim_ue_001",
        "spoofer_ids": step_ids,
        "burst_values": [u for u, _ in SWEEP_STEPS_US],
    }