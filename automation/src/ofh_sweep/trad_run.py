"""Traditional run: OFH DoS attacker sweep via controller API.

Sweeps tcpreplay_topspeed (0 vs. 1) and packet pacing rates across
100 Mbps, 500 Mbps, 1 Gbps, 5 Gbps, and 10 Gbps for both DU and RU
injection_points -- 20 runs total + 1 baseline per point = 22 runs.

Requires host network mode and `lo` device for ru_emulator and attacker.

Metrics recorded:
  Transport:   eCPRI frame loss %, switch buffer queue drops
  Sync:        IEEE 1588 PTP phase error (ns), slave clock out-of-lock duration
  Radio:       baseband processing deadline miss rate (ru.log, gnb_emu.log),
               over-the-air frame drop rate

Usage:
    uv run python3 -m ofh_sweep.trad_run
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import toml

from ofh_sweep.metrics import METRICS_FIELDS, parse_metrics

REPO_ROOT = Path(__file__).resolve().parents[3]
OFH_CONFIG_PATH = REPO_ROOT / "configs" / "ofh" / "ofh.toml"

SWEEP_TOPSPEED = [0, 1]
SWEEP_MBPS = [100, 500, 1000, 5000, 10000]
SWEEP_POINTS = ["DU", "RU"]

CONTAINER_NAME_PREFIX = "ofh_attacker_"
CONTROLLER_URL = "http://localhost:1343"
CONTROLLER_TOKEN = "default_changeme"


@dataclass
class RunSpec:
    index: int
    topspeed: int
    mbps: int
    injection_point: str
    run_id: str
    config: dict[str, Any]


def load_ofh_config(path: Path = OFH_CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        cfg = toml.load(f)
    return cfg


def build_run_spec(
    base_cfg: dict[str, Any],
    index: int,
    topspeed: int,
    mbps: int,
    injection_point: str,
    baseline: bool = False,
) -> RunSpec:
    import copy
    cfg = copy.deepcopy(base_cfg)

    if baseline:
        run_id = f"ofh_sweep_{index:04d}_baseline"
        cfg["id"] = run_id
        cfg["tcpreplay_topspeed"] = 0
        cfg["tcpreplay_mbps"] = 100
        cfg["injection_points"] = [injection_point]
        cfg["pcap_list"] = []
        cfg["duration_seconds"] = 10
        cfg["du"] = "lo"
        cfg["ru"] = "lo"
        return RunSpec(index=index, topspeed=0, mbps=100,
                       injection_point=injection_point, run_id=run_id, config=cfg)

    run_id = f"ofh_sweep_{index:04d}_ts{topspeed}_{mbps}mbps_{injection_point}"

    cfg["id"] = run_id
    cfg["tcpreplay_topspeed"] = topspeed
    cfg["tcpreplay_mbps"] = mbps
    cfg["injection_points"] = [injection_point]
    cfg["du"] = "lo"
    cfg["ru"] = "lo"

    return RunSpec(index=index, topspeed=topspeed, mbps=mbps,
                   injection_point=injection_point, run_id=run_id, config=cfg)


def generate_sweep(base_cfg: dict[str, Any]) -> list[RunSpec]:
    specs: list[RunSpec] = []
    idx = 0
    for point in SWEEP_POINTS:
        specs.append(build_run_spec(base_cfg, idx, 0, 0, point, baseline=True))
        idx += 1
        for topspeed in SWEEP_TOPSPEED:
            for mbps in SWEEP_MBPS:
                specs.append(build_run_spec(base_cfg, idx, topspeed, mbps, point))
                idx += 1
    return specs


def kill_old_containers() -> None:
    out = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=15,
    )
    for name in out.stdout.strip().splitlines():
        if name.startswith(CONTAINER_NAME_PREFIX):
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=10)
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)


def start_component(
    controller_url: str,
    token: str,
    component_type: str,
    config: dict[str, Any],
    rf: dict[str, str],
    component_repo: str | None = None,
    image_name: str | None = None,
) -> dict:
    import requests
    payload: dict = {
        "id": config["id"],
        "type": component_type,
        "config_json": config,
        "rf": rf,
    }
    if component_repo:
        payload["component"] = component_repo
    if image_name:
        payload["image_name"] = image_name

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "User-Agent": "ran-tester-automation/1.0"})
    resp = session.post(f"{controller_url}/start_from_json", json=payload, verify=False, timeout=90)
    if resp.status_code >= 400:
        return {"ok": False, "error": resp.text, "status_code": resp.status_code}
    return {"ok": True, "data": resp.json()}


def stop_component(controller_url: str, token: str, component_id: str) -> dict:
    import requests
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "User-Agent": "ran-tester-automation/1.0"})
    resp = session.post(f"{controller_url}/stop", json={"id": component_id}, verify=False, timeout=30)
    if resp.status_code >= 400:
        return {"ok": False, "error": resp.text, "status_code": resp.status_code}
    return {"ok": True, "data": resp.json()}


def poll_logs(
    controller_url: str,
    token: str,
    run_id: str,
    component_type: str,
    settle: float = 15.0,
    max_wait: float = 30.0,
) -> str:
    import requests
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "User-Agent": "ran-tester-automation/1.0"})

    time.sleep(settle)
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            resp = session.post(f"{controller_url}/logs", json={"id": run_id, "type": component_type},
                                verify=False, timeout=30)
            data = resp.json()
            entries = data.get("logs", [])
            if entries:
                return "\n".join(f"[{e.get('time')}] {e.get('message')}" for e in entries)
        except Exception:
            pass
        time.sleep(2.0)
    return ""


def run_step(
    spec: RunSpec,
    controller_url: str,
    token: str,
    settle: float,
    no_stop: bool,
    output_dir: Path,
) -> dict[str, Any]:
    rf = {"type": "none"}
    is_baseline = "baseline" in spec.run_id

    result: dict[str, Any] = {
        "run_index": spec.index,
        "topspeed": spec.topspeed,
        "mbps": spec.mbps,
        "injection_point": spec.injection_point,
        "run_id": spec.run_id,
        "baseline": is_baseline,
        "error": None,
    }

    label = f"{'baseline' if is_baseline else 'sweep'} {spec.run_id}"
    print(f"\n--- Run {spec.index:04d}: {label} ---")

    kill_old_containers()
    time.sleep(1.0)

    try:
        resp = start_component(
            controller_url, token,
            "ofh", spec.config, rf.copy(),
            "oran-testing/dos-attacker",
            "ghcr.io/oran-testing/dos-attacker",
        )
        if not resp.get("ok"):
            result["error"] = f"start: {resp.get('error')}"
            print(f"  ERROR: {result['error']}")
            return result
        print(f"  {spec.run_id} started")
    except Exception as e:
        result["error"] = f"start exception: {e}"
        print(f"  ERROR: {result['error']}")
        return result

    print(f"  waiting {settle}s...")
    logs = poll_logs(controller_url, token, spec.run_id, "ofh", settle)

    if logs:
        metrics = parse_metrics(spec.run_id, logs)
        result.update(metrics)
        print(f"  logs collected ({len(logs)} chars)")
        for k, v in metrics.items():
            if v is not None and k != "run_id" and k != "parse_note":
                print(f"    {k}: {v}")
    else:
        print("  no logs collected")

    step_dir = output_dir / f"run_{spec.index:04d}_{'baseline' if is_baseline else f'ts{spec.topspeed}_{spec.mbps}mbps_{spec.injection_point}'}"
    step_dir.mkdir(parents=True, exist_ok=True)
    with (step_dir / "config.toml").open("w") as f:
        config_data = {k: v for k, v in spec.config.items() if k != "id"}
        toml.dump(config_data, f)
    with (step_dir / "config.json").open("w") as f:
        json.dump(spec.config, f, indent=2)
    if logs:
        (step_dir / "raw.log").write_text(logs, "utf-8")
    with (step_dir / "result.json").open("w") as f:
        json.dump({k: v for k, v in result.items() if k != "run_id"}, f, indent=2)

    if not no_stop:
        try:
            stop_component(controller_url, token, spec.run_id)
            print(f"  {spec.run_id} stopped")
        except Exception as e:
            print(f"  WARN: stop: {e}")
        time.sleep(2.0)

    print(f"  -> {step_dir}")
    return result


def write_metrics_csv(rows: list[dict[str, Any]], path: Path) -> Path:
    fieldnames = METRICS_FIELDS + ["baseline"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ofh-sweep",
        description="OFH DoS attacker sweep: topspeed x mbps x injection_point.",
    )
    parser.add_argument("--output", type=Path,
                        default=REPO_ROOT / "output" / "ofh" / "sweep_0")
    parser.add_argument("--controller-url", default=CONTROLLER_URL)
    parser.add_argument("--token", default=CONTROLLER_TOKEN)
    parser.add_argument("--settle", type=float, default=15.0,
                        help="Seconds to wait for attacker to run and produce logs")
    parser.add_argument("--no-stop", action="store_true",
                        help="Leave containers running after each step")
    args = parser.parse_args(argv)

    out_dir = args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    base_cfg = load_ofh_config()
    specs = generate_sweep(base_cfg)
    results: list[dict[str, Any]] = []

    print(f"OFH DoS attacker sweep: {len(specs)} runs "
          f"({len(SWEEP_POINTS)} baselines + {len(specs) - len(SWEEP_POINTS)} sweep)")
    print(f"Topspeed values: {SWEEP_TOPSPEED}")
    print(f"Pacing rates (Mbps): {SWEEP_MBPS}")
    print(f"Injection points: {SWEEP_POINTS}")
    print(f"Output: {out_dir}")
    print()

    for spec in specs:
        result = run_step(spec, args.controller_url, args.token, args.settle, args.no_stop, out_dir)
        results.append(result)
        if result.get("error"):
            print(f"  WARN: {result['error']}")

    csv_path = write_metrics_csv(results, out_dir / "metrics.csv")
    with (out_dir / "metrics.json").open("w") as f:
        json.dump(results, f, indent=2)

    summary = [
        "OFH DoS attacker sweep",
        f"Total runs: {len(results)}",
        f"  Baselines: {len(SWEEP_POINTS)} (one per injection point)",
        f"  Sweep: {len(results) - len(SWEEP_POINTS)}",
        f"Topspeed values: {SWEEP_TOPSPEED}",
        f"Pacing rates (Mbps): {SWEEP_MBPS}",
        f"Injection points: {SWEEP_POINTS}",
        f"Output: {out_dir}",
        f"Metrics: {csv_path}",
        "",
        "Transport layer:",
        "  eCPRI frame loss %",
        "  Switch buffer queue drops",
        "",
        "Synchronization layer:",
        "  IEEE 1588 PTP phase error (ns)",
        "  Slave clock out-of-lock duration (s)",
        "",
        "Radio / service layer:",
        "  Baseband processing deadline miss rate (ru.log, gnb_emu.log)",
        "  Over-the-air frame drop rate",
        "",
        "Note: all metrics require instrumented logs (OFH attacker results,",
        "ru.log, gnb_emu.log). Values recorded as None when unavailable.",
        "",
        "Network setup:",
        "  host network mode (network_mode: host)",
        "  lo device for ru_emulator and attacker",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(summary) + "\n", "utf-8")

    errors = sum(1 for r in results if r.get("error"))
    print(f"\n{'='*60}")
    print(f"Completed {len(results)} runs")
    print(f"Metrics CSV: {csv_path}")
    print(f"Output: {out_dir}")
    print(f"Errors: {errors}/{len(results)}")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
