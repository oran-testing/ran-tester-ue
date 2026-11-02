"""LLM backend: generate an llm_worker config for the SSB spoofer sweep.

The llm_worker runs *only* via a ``run_spec`` entry in ``spec.yaml`` because it
requires ``results_dir`` in its process_config (its ``start()`` exits unless it
is present), and it is not registered in the controller's ``CONFIG_CONVERTERS``
nor in the MCP ``start_component`` component enum. So this backend:

  1. Writes ``configs/llm_worker/ssb_spoofer_sweep.yaml`` whose everyday
     ``user_prompt`` encodes the sweep + fixed attack flags.
  2. If ``--apply-spec`` is given, backs up ``spec.yaml``, inserts a
     ``run_spec`` entry for ``oran-testing/llm_worker``, then prints the
     ``docker compose up -d`` instruction (the script does not run compose).
  3. Otherwise, prints the exact steps the operator should take.

The LLM is expected to emit a JSON array plan with one ``start`` action per
sweep step (type ``ssb_spoofer``), which the llm_worker's plan loop posts to the
controller. Because the remote llm_worker image is prebuilt
(``ghcr.io/oran-testing/llm_worker``) it may predate the client-driven sweep; a
locally built image is required for this mode to actually spawn spoofers.
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

LLM_RUN_SPEC_ENTRY = {
    "component": "oran-testing/llm_worker",
    "worker_thread": "llm_worker",
    "name": "llm_worker",
    "config_file": "configs/llm_worker/ssb_spoofer_sweep.yaml",
    "results_dir": "ssb_spoofer_sweep_logs",
    "rf": {"type": "none"},
}

USER_PROMPT_TEMPLATE = (
    "Run an SSB spoofer attack sweep against the gNB. For each step, start an "
    "ssb_spoofer component and then report health. Use the following fixed "
    "settings for every step: rf.tx_gain_db = {tx_gain_db}, "
    "attack.modify_cell_barred = true, attack.modify_coreset0_idx = true, "
    "attack.modify_ss0_idx = true, attack.burst_length_ms = {burst_ms}. "
    "Sweep attack.burst_interval_us over these values in this order: "
    "{values}. Effective periodicity ms = burst_length_ms + "
    "(burst_interval_us/1000). Name each component id like "
    "ssb_spoofer_sweep_1_19000us, ssb_spoofer_sweep_2_9000us, and so on."
)


def build_llm_config() -> dict[str, Any]:
    base = yaml.safe_load(DEFAULT_BASE_CONFIG.read_text("utf-8"))
    sweeps = ", ".join(str(u) for u, _ in SWEEP_STEPS_US)

    ssb_spoofer_prompt = f"""
You are configuring an SSB spoofer. Return a JSON object with an "id" plus these
nested objects.

Fields from the reference guardrail config (keep values realistic for a B210,
max center freq 6 GHz, max sample rate 61.44 MHz):

rf:
  device_name: uhd
  device_args: "type=b200"
  rx_freq_hz: 1842050000          # band 3 downlink center
  tx_freq_hz: 1842050000
  srate_hz: 23040000
  rx_gain_db: 40.0
  tx_gain_db: {FIXED_TX_GAIN_DB}  # fixed by test

ssb:
  pattern: A
  scs_khz: 15
  periodicity_ms: 10
  ssb_freq_offset_hz: 0
  beta_pss: 1.0
  beta_sss: 1.0
  beta_pbch: 1.0
  beta_pbch_dmrs: 1.0

attack:   # all of these must be present and valid
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

Return ONLY valid JSON in a ```json fenced block. Do not include the top-level
"id" twice; the id belongs at top level.""".lstrip()

    return {
        "model": "deepseek-ai/DeepSeek-Coder-6.7B-Instruct",
        "results_dir": "ssb_spoofer_sweep_logs",
        "nof_plan_attempts": 10,
        "planner": (
            "You are a plan generator for the rtUE controller. Produce ONE JSON "
            "array of actions. Each action is an object with keys "
            "'id','type','desc','endpoint','rf'. endpoint ∈ "
            "{start,stop,logs,list,health}. For a start action, 'type' is the "
            "component type (e.g. 'ssb_spoofer') and 'rf' is 'b200' or 'zmq' or "
            "'none'. Return the full JSON array inside a ```json fenced block."
        ),
        "executor": (
            "Generate exactly the component configuration the controller "
            "expects for the requested endpoint."
        ),
        "ssb_spoofer": ssb_spoofer_prompt,
        "user_prompt": USER_PROMPT_TEMPLATE.format(
            tx_gain_db=FIXED_TX_GAIN_DB,
            burst_ms=BURST_LENGTH_MS,
            values=sweeps,
        ),
    }


def write_llm_config(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(build_llm_config(), sort_keys=False, indent=2),
        "utf-8",
    )
    return output_path


def _backup_spec(spec_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = spec_path.with_suffix(spec_path.suffix + f".bak_{stamp}")
    shutil.copy2(spec_path, backup)
    return backup


def inject_run_spec(
    spec_path: Path,
    entry: dict[str, Any] | None = None,
    apply: bool = False,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Insert the llm_worker run_spec entry into spec.yaml.

    Returns a dict with the diff/result. If ``apply`` is False, no file is
    modified and the operator instructions are returned instead.
    """
    entry = entry or LLM_RUN_SPEC_ENTRY
    spec = yaml.safe_load(spec_path.read_text("utf-8"))
    run_spec = [x for x in spec.get("run_spec", []) if x.get("name") != entry["name"]]
    run_spec.append(entry)
    spec["run_spec"] = run_spec

    if not apply:
        return {
            "applied": False,
            "spec_path": str(spec_path),
            "proposed_run_spec": entry,
            "instructions": (
                "Run:  sudo docker compose up -d   (or: docker compose up -d)\n"
                "The controller reads spec.yaml at startup, so restart the "
                "controller container to pick up the new run_spec entry:\n"
                "  sudo docker compose up -d --force-recreate controller\n"
                "Alternatively edit spec.yaml manually and re-run compose."
            ),
        }

    backup = _backup_spec(spec_path)
    with spec_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(spec, fh, sort_keys=False, indent=2)
    return {
        "applied": True,
        "backup": str(backup),
        "spec_path": str(spec_path),
        "run_spec": entry,
    }