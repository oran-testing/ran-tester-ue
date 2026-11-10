"""Log parsing for OFH DoS attacker sweep metrics.

Expected metrics per sweep step:
  Transport:   eCPRI frame loss %, switch buffer queue drops
  Sync:        IEEE 1588 PTP phase error (ns), slave clock out-of-lock duration
  Radio:       baseband processing deadline miss rate (ru.log, gnb_emu.log),
               over-the-air frame drop rate

All are recorded as None when unavailable from logs.

Debug logs from ru_emulator and gNB containers are collected separately
via :func:`docker_collect_debug_logs` which runs ``docker logs`` and
``docker cp`` against known container names.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

ECPRI_LOSS_RE = re.compile(r"ecpri.*frame.*loss[ :]*([0-9.]+)%?", re.IGNORECASE)
SWITCH_DROP_RE = re.compile(r"switch.*buffer.*(?:drop|discard)[ :]*([0-9]+)", re.IGNORECASE)
PTP_PHASE_ERROR_RE = re.compile(r"ptp.*phase.*error[ :]*([0-9.]+)", re.IGNORECASE)
PTP_OUT_OF_LOCK_RE = re.compile(r"(?:ptp|slave).*(?:out.?of.?lock|unlocked)[ :]*([0-9.]+)", re.IGNORECASE)
DEADLINE_MISS_RE = re.compile(r"(?:baseband|bb).*(?:deadline|miss)[ :]*([0-9.]+)", re.IGNORECASE)
OTA_DROP_RE = re.compile(r"(?:ota|over.?the.?air).*(?:frame|drop|loss)[ :]*([0-9.]+)", re.IGNORECASE)

# OCUDU / ru_emulator specific patterns
RU_ECPRI_STATS_RE = re.compile(
    r"ecpri.*(?:stats|count|packet).*(?:rx|recv)[ :]*([0-9]+)", re.IGNORECASE
)
RU_PTP_OFFSET_RE = re.compile(
    r"(?:ptp|clock).*(?:offset|error|deviation)[ :]*([0-9.]+)\s*(?:ns|nano)", re.IGNORECASE
)
GNB_DEADLINE_MISS_RE = re.compile(
    r"(?:slot|tti|frame).*(?:miss|deadline|overrun)[ :]*([0-9.]+)", re.IGNORECASE
)
GNB_UPLINK_BLER_RE = re.compile(
    r"(?:ul|uplink).*(?:bler|block.*error)[ :]*([0-9.]+)%?", re.IGNORECASE
)

# Attacker output patterns
ATTACKER_ECPRI_LOSS_RE = re.compile(
    r"(?:ecpri|frame).*drop[ :]*([0-9.]+)", re.IGNORECASE
)
ATTACKER_BW_RE = re.compile(
    r"(?:throughput|bw|bandwidth)[ :]*([0-9.]+)\s*(?:mbps|gbps)", re.IGNORECASE
)
ATTACKER_PKT_LOSS_RE = re.compile(
    r"(?:packet|pkt).*(?:loss|drop)[ :]*([0-9.]+)%?", re.IGNORECASE
)


def parse_metrics(run_id: str, log_text: str) -> dict[str, Any]:
    ecpri_match = ECPRI_LOSS_RE.search(log_text)
    switch_match = SWITCH_DROP_RE.search(log_text)
    ptp_phase_match = PTP_PHASE_ERROR_RE.search(log_text)
    ptp_lock_match = PTP_OUT_OF_LOCK_RE.search(log_text)
    deadline_match = DEADLINE_MISS_RE.search(log_text)
    ota_match = OTA_DROP_RE.search(log_text)

    # RU-specific
    ru_ecpri_match = RU_ECPRI_STATS_RE.search(log_text)
    ru_ptp_match = RU_PTP_OFFSET_RE.search(log_text)

    # gNB-specific
    gnb_deadline_match = GNB_DEADLINE_MISS_RE.search(log_text)
    gnb_bler_match = GNB_UPLINK_BLER_RE.search(log_text)

    # Attacker-specific
    attacker_ecpri_match = ATTACKER_ECPRI_LOSS_RE.search(log_text)
    attacker_bw_match = ATTACKER_BW_RE.search(log_text)
    attacker_pkt_match = ATTACKER_PKT_LOSS_RE.search(log_text)

    return {
        "run_id": run_id,
        "ecpri_frame_loss_pct": float(ecpri_match.group(1)) if ecpri_match else None,
        "switch_buffer_queue_drops": int(switch_match.group(1)) if switch_match else None,
        "ptp_phase_error_ns": float(ptp_phase_match.group(1)) if ptp_phase_match else None,
        "ptp_out_of_lock_duration_s": float(ptp_lock_match.group(1)) if ptp_lock_match else None,
        "bb_deadline_miss_rate": float(deadline_match.group(1)) if deadline_match else None,
        "ota_frame_drop_rate": float(ota_match.group(1)) if ota_match else None,
        # RU-emulator specific
        "ru_ecpri_packets_rx": int(ru_ecpri_match.group(1)) if ru_ecpri_match else None,
        "ru_ptp_offset_ns": float(ru_ptp_match.group(1)) if ru_ptp_match else None,
        # gNB specific
        "gnb_deadline_miss_rate": float(gnb_deadline_match.group(1)) if gnb_deadline_match else None,
        "gnb_ul_bler_pct": float(gnb_bler_match.group(1)) if gnb_bler_match else None,
        # Attacker output
        "attacker_ecpri_drop_rate": float(attacker_ecpri_match.group(1)) if attacker_ecpri_match else None,
        "attacker_throughput_mbps": float(attacker_bw_match.group(1)) if attacker_bw_match else None,
        "attacker_packet_loss_pct": float(attacker_pkt_match.group(1)) if attacker_pkt_match else None,
        "parse_note": (
            "eCPRI loss, switch drops, PTP phase/out-of-lock, baseband deadline miss, "
            "and OTA frame drop require instrumented logs (ru.log, gnb_emu.log, "
            "attacker results). Values recorded as None when unavailable. "
            "RU-emulator and gNB-specific fields parsed from OCUDU container logs. "
            "Attacker output fields parsed from dos-attacker container stdout."
        ),
    }


def docker_collect_debug_logs(
    output_dir: Path,
    ru_names: list[str] | None = None,
    gnb_names: list[str] | None = None,
) -> dict[str, Path]:
    """Collect debug logs from ru_emulator and gNB Docker containers.

    Uses ``docker logs`` and ``docker exec`` to fetch logs from known
    OCUDU containers. Returns a dict mapping labels to file paths.
    Errors are non-fatal — collects whatever is available.
    """
    ru_names = ru_names or ["ru_emulator", "ocudu-ru", "ru-emulator"]
    gnb_names = gnb_names or ["gnb_emulator", "ocudu-gnb", "gnb-emulator"]

    output_dir.mkdir(parents=True, exist_ok=True)
    collected: dict[str, Path] = {}

    for label, names in [("ru_emulator", ru_names), ("gNB", gnb_names)]:
        container_name = None
        for name in names:
            try:
                result = subprocess.run(
                    ["docker", "inspect", name],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    container_name = name
                    break
            except Exception:
                continue

        if not container_name:
            continue

        # docker logs
        try:
            logs = subprocess.run(
                ["docker", "logs", "--tail", "500", container_name],
                capture_output=True, text=True, timeout=30,
            )
            log_text = logs.stdout + logs.stderr
            if log_text:
                path = output_dir / f"{label}_docker_logs.txt"
                path.write_text(log_text, "utf-8")
                collected[f"{label}_docker_logs"] = path
        except Exception:
            pass

        # Try to cat known log files from inside the container
        for logfile in ["ru.log", "gnb_emu.log", "debug.log", "app.log", "/var/log/ru.log"]:
            try:
                result = subprocess.run(
                    ["docker", "exec", container_name, "cat", logfile],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode == 0 and result.stdout:
                    safe_name = logfile.replace("/", "_")
                    path = output_dir / f"{label}_{safe_name}"
                    path.write_text(result.stdout, "utf-8")
                    collected[f"{label}_{safe_name}"] = path
            except Exception:
                pass

        # Try to copy log directories
        for remote_dir in ["/var/log/", "/tmp/", "/app/logs/"]:
            try:
                result = subprocess.run(
                    ["docker", "cp", f"{container_name}:{remote_dir}", str(output_dir / f"{label}_logs_{remote_dir.replace('/', '_')}")],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    pass
            except Exception:
                pass

    return collected


METRICS_FIELDS = [
    "run_index",
    "run_id",
    "topspeed",
    "mbps",
    "injection_point",
    "ecpri_frame_loss_pct",
    "switch_buffer_queue_drops",
    "ptp_phase_error_ns",
    "ptp_out_of_lock_duration_s",
    "bb_deadline_miss_rate",
    "ota_frame_drop_rate",
    "ru_ecpri_packets_rx",
    "ru_ptp_offset_ns",
    "gnb_deadline_miss_rate",
    "gnb_ul_bler_pct",
    "attacker_ecpri_drop_rate",
    "attacker_throughput_mbps",
    "attacker_packet_loss_pct",
    "error",
]