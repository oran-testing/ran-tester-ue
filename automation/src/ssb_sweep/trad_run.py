"""Traditional run: SSB spoofer sweep + victim rtue via controller API.

Sweeps attack.burst_interval_us over [19000, 9000, 4000, 2000] us with
burst_length_ms=1, 25 runs per value (100 total), recording L1/L2/L3 metrics.

Requires three B210 USRPs with distinct serials and a host-side gNB (srsRAN).

Usage:
    uv run python3 -m ssb_sweep.trad_run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from ssb_sweep.controller_client import ControllerClient
from ssb_sweep.metrics import parse_metrics

REPO_ROOT = Path(__file__).resolve().parents[3]

SSB_CONFIG_PATH = REPO_ROOT / "configs" / "ssb_spoofer" / "srs_band3.yaml"
RTUE_CONFIG_PATH = REPO_ROOT / "configs" / "srsran" / "ue_uhd.conf"

OCUDU_DIR = Path.home() / "ocudu" / "docker"
OCUDU_GNB_CONFIG_SRC = Path.home() / "ocudu" / "configs" / "gnb_rf_b210_fdd_srsUE.yml"

SWEEP_VALUES_US = [19000, 9000, 4000, 2000]

USRP_RELEASE_DELAY = 5.0
START_MAX_RETRIES = 3
CONTAINER_NAME_PREFIXES = ("trad_ssb_", "trad_ue_", "srsgnb_trad")

GNB_SERIAL = "32BBA59"
SPOOFER_SERIAL = "318898A"
UE_SERIAL = "32C74B3"

METRICS_CSV_FIELDS = [
    "run_index", "burst_interval_us", "periodicity_ms",
    "tx_gain_db", "burst_length_ms",
    "pss_sss_correlation_peak_ratio", "pbch_block_error_rate",
    "coreset0_blind_decode_failure_rate", "sib1_decode_timeout_count",
    "attach_denial_pct", "attach_denied_observed", "attach_attempts_observed",
    "time_to_camp_ms", "cell_barred_detected", "mib_crc_err",
    "coreset0_out_of_bounds", "error",
]


@dataclass
class RunSpec:
    index: int
    burst_interval_us: int
    periodicity_ms: int
    spoofer_id: str
    rtue_id: str
    spoofer_cfg: dict
    rtue_cfg: dict


def load_ssb_config(path: Path = SSB_CONFIG_PATH) -> dict:
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"SSB config {path} did not parse to a mapping")
    for section in ("rf", "ssb", "attack", "operation"):
        if section not in cfg:
            raise ValueError(f"SSB config {path} missing section '{section}'")
    return cfg


def _coerce(val: str):
    """Parse a .conf value string into the proper Python type."""
    v = val.strip()
    if v.lower() in ("true", "yes", "on"):
        return True
    if v.lower() in ("false", "no", "off"):
        return False
    if v.isdigit() or (v.startswith("-") and v[1:].isdigit()):
        return int(v)
    try:
        f = float(v)
        if f == int(f) and "e" not in v.lower():
            return int(f)
        return f
    except ValueError:
        return v


def load_rtue_flat(path: Path = RTUE_CONFIG_PATH) -> dict:
    import configparser
    cp = configparser.ConfigParser()
    cp.optionxform = str
    cp.read(str(path))
    flat = {}
    for sec in cp.sections():
        for k, v in cp[sec].items():
            flat[f"{sec}_{k}"] = _coerce(v)

    force_int_fields = {
        "rf_freq_offset", "rf_nof_antennas", "rf_time_adv_nsamples",
        "rat_eutra_dl_earfcn", "rat_eutra_nof_carriers",
        "rat_nr_nof_carriers", "rat_nr_max_nof_prb",
        "log_all_hex_limit", "log_file_max_size",
        "rrc_release", "rrc_ue_category",
        "general_metrics_influxdb_port",
    }
    for key in force_int_fields:
        if key in flat:
            flat[key] = int(flat[key])

    if "rf_srate" in flat:
        flat["rf_srate"] = int(float(flat["rf_srate"]))

    return flat


def write_gnb_config(gnb_serial: str = GNB_SERIAL) -> Path:
    with OCUDU_GNB_CONFIG_SRC.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["ru_sdr"]["device_args"] = f"type=b200,serial={gnb_serial},num_recv_frames=64,num_send_frames=64"
    out = Path("/tmp/gnb_trad_config.yml")
    with out.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, indent=2)
    return out


def stop_gnb() -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(OCUDU_DIR / "docker-compose.yml"),
         "down", "--remove-orphans"],
        capture_output=True, timeout=60,
    )


def start_gnb(gnb_config_path: Path, gnb_cmd: str = "") -> None:
    if gnb_cmd:
        stop_gnb()
        time.sleep(2.0)
        cmd = gnb_cmd.split()
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  gNB started via: {gnb_cmd}")
        return
    stop_gnb()
    time.sleep(2.0)
    env = os.environ.copy()
    env["GNB_CONFIG_PATH"] = str(gnb_config_path)
    subprocess.run(
        ["docker", "compose", "-f", str(OCUDU_DIR / "docker-compose.yml"), "up", "-d"],
        env=env, capture_output=True, timeout=180,
    )
    print(f"  ocudu core+gnb started (config: {gnb_config_path})")


def wait_for_gnb(timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(
            ["docker", "logs", "ocudu_gnb"],
            capture_output=True, text=True, timeout=15,
        )
        combined = r.stdout + r.stderr
        if "SCTP" in combined or "Started AMF-Connector" in combined:
            return True
        time.sleep(2.0)
    return False


def build_run_spec(run_index: int, burst_interval_us: int, burst_length_ms: int = 1) -> RunSpec:
    periodicity_ms = burst_length_ms + (burst_interval_us // 1000)
    spoofer_id = f"trad_ssb_{run_index:04d}_{burst_interval_us}us"
    rtue_id = f"trad_ue_{run_index:04d}_{burst_interval_us}us"

    spoofer_cfg = load_ssb_config()
    spoofer_cfg["id"] = spoofer_id
    spoofer_cfg["rf"]["device_args"] = f"type=b200,serial={SPOOFER_SERIAL}"
    attack = spoofer_cfg["attack"]
    attack["modify_cell_barred"] = True
    attack["cell_barred_value"] = True
    attack["modify_coreset0_idx"] = True
    attack["modify_ss0_idx"] = True
    attack["burst_interval_us"] = burst_interval_us
    attack["burst_length_ms"] = burst_length_ms
    attack["max_bursts"] = 0
    attack["continuous_tx"] = True
    spoofer_cfg["rf"]["tx_gain_db"] = 60.0
    spoofer_cfg["operation"]["log_file"] = f"{spoofer_id}.log"
    spoofer_cfg["operation"]["scan_duration_sec"] = 30.0

    rtue_cfg = load_rtue_flat()
    rtue_cfg["id"] = rtue_id
    rtue_cfg["rf_srate"] = 23.04e6
    rtue_cfg["rf_tx_gain"] = 70
    rtue_cfg["rf_rx_gain"] = 40
    rtue_cfg["rf_device_args"] = f"type=b200,serial={UE_SERIAL}"
    rtue_cfg["rat_nr_bands"] = 3
    rtue_cfg["rat_nr_nof_prb"] = 106
    rtue_cfg["usim_imsi"] = "001010123456789"
    rtue_cfg["usim_imei"] = "353490069873319"
    rtue_cfg["usim_opc"] = "63BFA50EE6523365FF14C1F45F88737D"
    rtue_cfg["usim_k"] = "00112233445566778899aabbccddeeff"
    rtue_cfg["nas_apn"] = "srsapn"

    return RunSpec(
        index=run_index,
        burst_interval_us=burst_interval_us,
        periodicity_ms=periodicity_ms,
        spoofer_id=spoofer_id,
        rtue_id=rtue_id,
        spoofer_cfg=spoofer_cfg,
        rtue_cfg=rtue_cfg,
    )


def generate_sweep(total_runs: int = 100) -> list[RunSpec]:
    per_value = total_runs // len(SWEEP_VALUES_US)
    specs = []
    idx = 0
    for burst_us in SWEEP_VALUES_US:
        for _ in range(per_value):
            specs.append(build_run_spec(idx, burst_us))
            idx += 1
    remaining = total_runs - idx
    if remaining > 0:
        for _ in range(remaining):
            burst_us = SWEEP_VALUES_US[-1]
            specs.append(build_run_spec(idx, burst_us))
            idx += 1
    return specs


def poll_logs(
    client: ControllerClient,
    run_id: str,
    component_type: str,
    settle: float = 30.0,
    max_wait: float = 60.0,
) -> str:
    time.sleep(settle)
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            resp = client.logs(run_id, component_type)
            if resp.get("ok"):
                entries = resp["data"].get("logs", [])
                if entries:
                    return "\n".join(
                        f"[{e.get('time')}] {e.get('message')}" for e in entries
                    )
        except Exception:
            pass
        time.sleep(2.0)
    return ""


def kill_old_containers() -> None:
    out = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=15,
    )
    for name in out.stdout.strip().splitlines():
        if any(name.startswith(p) for p in CONTAINER_NAME_PREFIXES):
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=10)
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)


def wait_for_usrp(max_attempts: int = 5, delay: float = 2.0) -> bool:
    for i in range(max_attempts):
        try:
            r = subprocess.run(
                ["uhd_find_devices", "--args", "type=b200"],
                capture_output=True, text=True, timeout=30,
            )
            if "-- UHD Device" in r.stdout:
                return True
        except FileNotFoundError:
            return True
        except Exception:
            pass
        if i < max_attempts - 1:
            time.sleep(delay)
    return False


def stop_component(client: ControllerClient, cid: str, label: str) -> None:
    try:
        client.stop(cid)
        print(f"  stopped {label}")
    except Exception as e:
        print(f"  WARN: {label} stop: {e}")


def start_component_with_retry(
    client: ControllerClient,
    component_type: str,
    config: dict,
    rf: dict,
    component_repo: str | None,
    label: str,
) -> dict:
    for attempt in range(1, START_MAX_RETRIES + 1):
        try:
            resp = client.start(component_type, config, rf, component_repo)
            if resp.get("ok"):
                return resp
            err = resp.get("error", "")
            print(f"  {label} attempt {attempt}/{START_MAX_RETRIES} failed: {err[:120]}")
        except Exception as e:
            print(f"  {label} attempt {attempt}/{START_MAX_RETRIES} error: {e}")
        if attempt < START_MAX_RETRIES:
            print(f"  waiting {USRP_RELEASE_DELAY}s for USRP to release...")
            kill_old_containers()
            time.sleep(USRP_RELEASE_DELAY)
            if not wait_for_usrp():
                print(f"  WARN: USRP not found before retry {attempt}")
    raise RuntimeError(f"{label} failed after {START_MAX_RETRIES} attempts")


def start_gnb(gnb_config_path: Path, gnb_cmd: str = "") -> None:
    subprocess.run(["pkill", "-f", "gnb.*gnb_trad"], capture_output=True, timeout=10)
    time.sleep(1.0)
    if gnb_cmd:
        cmd = gnb_cmd.split()
        logfile = open("/tmp/gnb_trad.log", "w")
        subprocess.Popen(cmd, stdout=logfile, stderr=subprocess.STDOUT)
        print(f"  gNB started via: {gnb_cmd}")
    else:
        logfile = open("/tmp/gnb_trad.log", "w")
        subprocess.Popen(
            ["sudo", "gnb", "-c", str(gnb_config_path)],
            stdout=logfile, stderr=subprocess.STDOUT,
        )
        print(f"  gNB process started (config: {gnb_config_path})")


def wait_for_gnb(timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            text = Path("/tmp/gnb_trad.log").read_text("utf-8")
            if "Started AMF-Connector" in text or "SCTP" in text:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def run_once(
    client: ControllerClient,
    spec: RunSpec,
    rf_type: str,
    settle: float,
    no_stop: bool,
    gnb_config_path: Path | None,
    gnb_cmd: str = "",
) -> dict:
    rf = {"type": rf_type}

    result = {
        "run_index": spec.index,
        "burst_interval_us": spec.burst_interval_us,
        "periodicity_ms": spec.periodicity_ms,
        "spoofer_id": spec.spoofer_id,
        "rtue_id": spec.rtue_id,
        "error": None,
    }

    print(f"\n--- Run {spec.index:04d}: burst_interval={spec.burst_interval_us}us "
          f"(period={spec.periodicity_ms}ms) ---")

    kill_old_containers()
    time.sleep(1.0)

    if gnb_config_path is not None:
        print("  restarting gNB...")
        try:
            start_gnb(gnb_config_path, gnb_cmd)
            if not wait_for_gnb():
                print("  WARN: gNB may not be ready")
        except Exception as e:
            result["error"] = f"gnb: {e}"
            print(f"  ERROR: {result['error']}")
            return result

    try:
        spr = start_component_with_retry(
            client, "ssb_spoofer", spec.spoofer_cfg, rf.copy(),
            "oran-testing/ssb-spoofer", "spoofer",
        )
        print(f"  {spec.spoofer_id} started")
    except Exception as e:
        result["error"] = f"spoofer: {e}"
        print(f"  ERROR: {result['error']}")
        return result

    try:
        rtr = start_component_with_retry(
            client, "rtue", spec.rtue_cfg, rf.copy(),
            "oran-testing/rtue", "rtue",
        )
        print(f"  {spec.rtue_id} started")
    except Exception as e:
        result["error"] = f"rtue: {e}"
        print(f"  ERROR: {result['error']}")
        return result

    print(f"  waiting {settle}s...")
    spoofer_logs = poll_logs(client, spec.spoofer_id, "ssb_spoofer", settle)
    rtue_logs = poll_logs(client, spec.rtue_id, "rtue", settle)
    result["spoofer_logs"] = spoofer_logs
    result["rtue_logs"] = rtue_logs

    spoofer_metrics = parse_metrics(spec.spoofer_id, spoofer_logs) if spoofer_logs else {}
    rtue_metrics = parse_metrics(spec.rtue_id, rtue_logs) if rtue_logs else {}
    result["spoofer_metrics"] = spoofer_metrics
    result["rtue_metrics"] = rtue_metrics
    print(f"  logs collected (spoofer: {len(spoofer_logs)} chars, rtue: {len(rtue_logs)} chars)")

    if not no_stop:
        stop_component(client, spec.spoofer_id, "spoofer")
        stop_component(client, spec.rtue_id, "rtue")
        time.sleep(USRP_RELEASE_DELAY)
        if gnb_config_path is not None:
            stop_gnb()

    return result


def combine_metrics_row(result: dict) -> dict:
    sm = result.get("spoofer_metrics") or {}
    rm = result.get("rtue_metrics") or {}
    combined = sm.copy()
    combined.update(rm)
    return {
        "run_index": result["run_index"],
        "burst_interval_us": result["burst_interval_us"],
        "periodicity_ms": result["periodicity_ms"],
        "tx_gain_db": 60.0,
        "burst_length_ms": 1,
        "pss_sss_correlation_peak_ratio": combined.get("pss_sss_correlation_peak_ratio"),
        "pbch_block_error_rate": combined.get("pbch_block_error_rate"),
        "coreset0_blind_decode_failure_rate": combined.get("coreset0_blind_decode_failure_rate"),
        "sib1_decode_timeout_count": combined.get("sib1_decode_timeout_count"),
        "attach_denial_pct": combined.get("attach_denial_pct"),
        "attach_denied_observed": combined.get("attach_denied_observed") or 0,
        "attach_attempts_observed": combined.get("attach_attempts_observed") or 0,
        "time_to_camp_ms": combined.get("time_to_camp_ms"),
        "cell_barred_detected": combined.get("cell_barred_detected") or 0,
        "mib_crc_err": combined.get("mib_crc_err") or 0,
        "coreset0_out_of_bounds": combined.get("coreset0_out_of_bounds") or 0,
        "error": result.get("error"),
    }


def write_metrics_csv(rows: list[dict], path: Path) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=METRICS_CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return path


def main(argv: list[str] | None = None) -> int:
    global GNB_SERIAL, SPOOFER_SERIAL, UE_SERIAL

    parser = argparse.ArgumentParser(
        prog="trad-run",
        description="SSB spoofer sweep + victim rtue: 100 runs over 4 burst intervals.",
    )
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output", type=Path,
                        default=REPO_ROOT / "output" / "trad" / "run_0-100")
    parser.add_argument("--controller-url", default="http://localhost:1343")
    parser.add_argument("--token", default="default_changeme")
    parser.add_argument("--rf-type", choices=["b200", "zmq", "none"], default="b200")
    parser.add_argument("--settle", type=float, default=30.0)
    parser.add_argument("--no-stop", action="store_true")
    parser.add_argument("--no-gnb", action="store_true",
                        help="Skip gNB restart (run it manually)")
    parser.add_argument("--gnb-cmd", default="",
                        help="Command to start/restart gNB at each run (e.g. 'sudo gnb -c /path/config.yaml')")
    parser.add_argument("--start-from", type=int, default=0)
    parser.add_argument("--gnb-serial", default=GNB_SERIAL)
    parser.add_argument("--spoofer-serial", default=SPOOFER_SERIAL)
    parser.add_argument("--ue-serial", default=UE_SERIAL)
    args = parser.parse_args(argv)

    # Update serials from CLI args
    GNB_SERIAL = args.gnb_serial
    SPOOFER_SERIAL = args.spoofer_serial
    UE_SERIAL = args.ue_serial

    gnb_config_path = None
    gnb_cmd = args.gnb_cmd
    if not args.no_gnb:
        gnb_config_path = write_gnb_config(GNB_SERIAL)
        if gnb_cmd:
            print(f"  gNB management via custom command: {gnb_cmd}")

    out_dir = args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    client = ControllerClient(base_url=args.controller_url, token=args.token, timeout=60.0)
    all_specs = generate_sweep(args.count)
    all_results: list[dict] = []

    for spec in all_specs[args.start_from:]:
        result = run_once(client, spec, args.rf_type, args.settle, args.no_stop, gnb_config_path, gnb_cmd)
        all_results.append(result)

        step_dir = out_dir / f"run_{spec.index:04d}_{spec.burst_interval_us}us"
        step_dir.mkdir(parents=True, exist_ok=True)

        with (step_dir / "ssb_config.yaml").open("w") as f:
            yaml.safe_dump(spec.spoofer_cfg, f, sort_keys=False, indent=2)
        with (step_dir / "rtue_config.json").open("w") as f:
            json.dump(spec.rtue_cfg, f, indent=2)

        for key, label in [("spoofer_logs", "spoofer_raw.log"),
                           ("rtue_logs", "rtue_raw.log")]:
            text = result.get(key) or "(no logs collected)"
            (step_dir / label).write_text(text, "utf-8")

        for key, label in [("spoofer_metrics", "spoofer_metrics.json"),
                           ("rtue_metrics", "rtue_metrics.json")]:
            data = result.get(key) or {}
            with (step_dir / label).open("w") as f:
                json.dump(data, f, indent=2)

        with (step_dir / "result.json").open("w") as f:
            json.dump(result, f, indent=2)

        print(f"  -> {step_dir}")
        if result.get("error"):
            print(f"  WARN: {result['error']}")

    csv_path = write_metrics_csv(
        [combine_metrics_row(r) for r in all_results],
        out_dir / "metrics.csv",
    )
    with (out_dir / "metrics.json").open("w") as f:
        json.dump([combine_metrics_row(r) for r in all_results], f, indent=2)

    with (out_dir / "aggregate_results.json").open("w") as f:
        json.dump(all_results, f, indent=2)

    errors = sum(1 for r in all_results if r.get("error"))
    summary = [
        f"SSB spoofer sweep + victim rtue: {len(all_results)} runs",
        f"Sweep values (burst_interval_us): {SWEEP_VALUES_US}",
        f"Runs per value: {len(all_results) // len(SWEEP_VALUES_US)}",
        f"Output: {out_dir}",
        f"RF type: {args.rf_type}",
        f"Settle: {args.settle}s",
        f"Serials: gNB={GNB_SERIAL} spoofer={SPOOFER_SERIAL} ue={UE_SERIAL}",
        f"Errors: {errors}/{len(all_results)}",
        "",
        "L1 metrics: PSS/SSS correlation peak ratio, PBCH BLER",
        "L2 metrics: CORESET0 blind decode failure rate, SIB1 timeout count",
        "L3 metrics: attach denial %, time-to-camp (ms), failure signatures",
        "  (CELL_BARRED_DETECTED, MIB_CRC_ERR, CORESET0_OUT_OF_BOUNDS)",
        "",
        "Note: PSS/SSS ratio, PBCH BLER, CORESET0 failure rate, SIB1 timeout,",
        "and time-to-camp require instrumented receiver data; recorded as null",
        "when unavailable from logs.",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(summary) + "\n", "utf-8")

    print(f"\n{'='*60}")
    print(f"Completed {len(all_results)} runs")
    print(f"Metrics CSV: {csv_path}")
    print(f"Output: {out_dir}")
    print(f"Errors: {errors}/{len(all_results)}")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())