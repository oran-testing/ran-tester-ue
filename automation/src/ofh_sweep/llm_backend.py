"""LLM backend: generate an llm_worker config for the OFH DoS attacker sweep.

The llm_worker runs *only* via a ``run_spec`` entry in ``spec.yaml`` because it
requires ``results_dir`` in its process_config (its ``start()`` exits unless it
is present), and it is not registered in the controller's ``CONFIG_CONVERTERS``
nor in the MCP ``start_component`` component enum. So this backend:

  1. Writes ``configs/llm/ofh_sweep.yaml`` whose everyday ``user_prompt``
     encodes the sweep.
  2. If ``--apply-spec`` is given, backs up ``spec.yaml``, inserts a
     ``run_spec`` entry for ``oran-testing/llm_worker``, then prints the
     ``docker compose up -d`` instruction.
  3. Otherwise, prints the exact steps the operator should take.

The LLM is expected to emit a JSON array plan with one ``start`` action per
sweep step (type ``ofh``), which the llm_worker's plan loop posts to the
controller.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ofh_sweep.spec import (
    DEFAULT_BASE_CONFIG,
    INJECTION_POINTS,
    PCAP_RATES_MBPS,
    TOPSPEED_VALUES,
)

LLM_RUN_SPEC_ENTRY = {
    "component": "oran-testing/llm_worker",
    "worker_thread": "llm_worker",
    "name": "llm_worker",
    "config_file": "configs/llm/ofh_sweep.yaml",
    "results_dir": "ofh_sweep_logs",
    "rf": {"type": "none"},
}

USER_PROMPT_TEMPLATE = (
    "Run an OFH DoS attacker sweep against the gNB and RU. For each step, start "
    "an ofh component and then check its health and fetch logs. "
    "Sweep tcpreplay_topspeed over {{{topspeed_values}}}, "
    "tcpreplay_mbps over {{{mbps_values}}} Mbps, and "
    "injection_points over {{{injection_points}}}. "
    "That is {total_steps} total steps. "
    "Name each component id like 'ofh_sweep_0000_ts0_100mbps_DU', "
    "'ofh_sweep_0001_ts0_100mbps_RU', and so on. "
    "Use rf type 'none' for all components since OFH operates on host network."
)


def build_llm_config() -> dict[str, Any]:
    base = yaml.safe_load(DEFAULT_BASE_CONFIG.read_text("utf-8"))
    total_steps = len(TOPSPEED_VALUES) * len(PCAP_RATES_MBPS) * len(INJECTION_POINTS)

    ts_str = ", ".join(str(v) for v in TOPSPEED_VALUES)
    mbps_str = ", ".join(str(v) for v in PCAP_RATES_MBPS)
    ip_str = ", ".join(INJECTION_POINTS)

    ofh_prompt = f"""
You are configuring an OFH DoS attacker. Return a JSON object with an "id" plus
flat keys matching the TOML schema.

Schema (all at top level):
  injection_points: list of strings, one of: "DU", "RU"  (e.g. ["DU"])
  pcap_dir: str (default "Traffic/")
  pcap_list: list (usually [])
  du: str, network interface for DU injection (e.g. "lo" or "enp5s0f1")
  ru: str, network interface for RU injection (e.g. "lo" or "enp8s0f0np0")
  attacker_dir: str (default "/attack_env")
  results_dir: str (default "./attack_results")
  duration_seconds: int/float, >0 (how long to run)
  tcpreplay_topspeed: int, 0 or 1 (0=paced, 1=maximum speed)
  tcpreplay_mbps: int/float, >0 (pacing rate in Mbps)
  tcpreplay_loop: int (0 = infinite loop)
  keep_history: str ("0" = don't keep history)

Validation rules:
  - injection_points must be a non-empty list with items "DU" or "RU"
  - tcpreplay_topspeed must be 0 or 1
  - tcpreplay_mbps must be > 0
  - duration_seconds must be > 0

Example valid config:
  {{
    "id": "ofh_sweep_0000_ts0_100mbps_DU",
    "injection_points": ["DU"],
    "pcap_dir": "Traffic/",
    "pcap_list": [],
    "du": "lo",
    "ru": "lo",
    "attacker_dir": "/attack_env",
    "results_dir": "./attack_results",
    "duration_seconds": 10,
    "tcpreplay_topspeed": 0,
    "tcpreplay_mbps": 100,
    "tcpreplay_loop": 0,
    "keep_history": "0"
  }}

Return ONLY valid JSON in a ```json fenced block. Do not include the top-level
"id" twice; the id belongs at top level.""".lstrip()

    return {
        "model": "deepseek-ai/DeepSeek-Coder-6.7B-Instruct",
        "results_dir": "ofh_sweep_logs",
        "nof_plan_attempts": 10,
        "planner": (
            "You are a plan generator for the rtUE controller. Produce ONE JSON "
            "array of actions. Each action is an object with keys "
            "'id','type','desc','endpoint','rf'. endpoint ∈ "
            "{start,stop,logs,list,health}. For a start action, 'type' is the "
            "component type (e.g. 'ofh') and 'rf' is 'none'. "
            "Do NOT use 'b200' or 'zmq' for OFH components; the attacker uses "
            "host network mode with no RF hardware. "
            "Return the full JSON array inside a ```json fenced block."
        ),
        "executor": (
            "Generate exactly the component configuration the controller "
            "expects for the requested endpoint."
        ),
        "ofh": ofh_prompt,
        "user_prompt": USER_PROMPT_TEMPLATE.format(
            topspeed_values=ts_str,
            mbps_values=mbps_str,
            injection_points=ip_str,
            total_steps=total_steps,
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