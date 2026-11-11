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
ATTACKER_COMPLETED_RE = re.compile(
    r"Completed .*\.pcap \| Injection", re.IGNORECASE
)

# srsRAN ru_emulator KPI statistics table rows (printed to stdout every second):
# | HH:MM:SS | ID | RX_TOTAL | RX_ON_TIME | RX_EARLY | RX_LATE | RX_SEQ_ERR(a/b/c/d) |
#   RX_ON_TIME_C | RX_EARLY_C | RX_LATE_C | RX_SEQ_ERR_C | RX_ON_TIME_C_U | RX_EARLY_C_U |
#   RX_LATE_C_U | RX_SEQ_ERR_C_U | RX_SEQ_ERR_PRACH(a/b) | RX_CORRUPT | RX_ERR_DROP | TX_TOTAL |
# All values are per-second rates.
RU_KPI_ROW_RE = re.compile(r"^\|\s*\d{2}:\d{2}:\d{2}\s*\|")
RU_CRASH_RE = re.compile(
    r"Assertion `.*' failed|Segmentation fault|RU emulator app stopped"
)
RU_WAKE_LATE_RE = re.compile(r"timing worker woke up late")
DU_OFH_DROP_RE = re.compile(r"dropped received Open Fronthaul", re.IGNORECASE)
DU_NOT_UPLINK_RE = re.compile(r"is not an uplink message", re.IGNORECASE)
DU_EAXC_DROP_RE = re.compile(r"is not configured in reception", re.IGNORECASE)

RU_KPI_FIELDS = [
    "ru_rx_total",
    "ru_rx_on_time",
    "ru_rx_early",
    "ru_rx_late",
    "ru_rx_seq_err",
    "ru_rx_on_time_c",
    "ru_rx_early_c",
    "ru_rx_late_c",
    "ru_rx_seq_err_c",
    "ru_rx_corrupt",
    "ru_rx_err_drop",
    "ru_tx_total",
]


def _int_cell(cell: str) -> int | None:
    try:
        return int(cell)
    except (TypeError, ValueError):
        return None


def _sum_slash_cell(cell: str) -> int | None:
    """Sum slashed counter cells like RX_SEQ_ERR 'a/b/c/d'."""
    try:
        return sum(int(part) for part in cell.split("/") if part)
    except (TypeError, ValueError):
        return None


def _parse_ru_last_kpi_row(log_text: str) -> dict[str, int | None] | None:
    kpi_lines = [ln for ln in log_text.splitlines() if RU_KPI_ROW_RE.match(ln)]
    if not kpi_lines:
        return None
    cells = [c.strip() for c in kpi_lines[-1].split("|")]
    if len(cells) < 20:
        return None
    return {
        "ru_rx_total": _int_cell(cells[3]),
        "ru_rx_on_time": _int_cell(cells[4]),
        "ru_rx_early": _int_cell(cells[5]),
        "ru_rx_late": _int_cell(cells[6]),
        "ru_rx_seq_err": _sum_slash_cell(cells[7]),
        "ru_rx_on_time_c": _int_cell(cells[8]),
        "ru_rx_early_c": _int_cell(cells[9]),
        "ru_rx_late_c": _int_cell(cells[10]),
        "ru_rx_seq_err_c": _sum_slash_cell(cells[11]),
        "ru_rx_corrupt": _int_cell(cells[17]),
        "ru_rx_err_drop": _int_cell(cells[18]),
        "ru_tx_total": _int_cell(cells[19]),
    }


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

    # Real victim impact from the srsRAN ru_emulator KPI table / gnb DU logs.
    ru_last_kpi = _parse_ru_last_kpi_row(log_text)
    ru_kpi_rows = sum(1 for ln in log_text.splitlines() if RU_KPI_ROW_RE.match(ln))
    crash_line = next(
        (ln.strip() for ln in log_text.splitlines() if RU_CRASH_RE.search(ln)), None
    )

    result: dict[str, Any] = {
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
        # Victim testbed (ru_emulator KPI table, last row = per-second rates)
        "ru_kpi_rows": ru_kpi_rows,
        "ru_crashed": crash_line is not None,
        "ru_crash_reason": crash_line[:200] if crash_line else None,
        "ru_wake_late_events": len(RU_WAKE_LATE_RE.findall(log_text)),
        # Victim testbed (gnb DU / gnb_emulator OFH reception drops)
        "du_ofh_drop_msgs": len(DU_OFH_DROP_RE.findall(log_text)),
        "du_not_uplink_msgs": len(DU_NOT_UPLINK_RE.findall(log_text)),
        "du_eaxc_drop_msgs": len(DU_EAXC_DROP_RE.findall(log_text)),
        # Attacker replay completions (one per pcap injection point)
        "attacker_replays_completed": len(ATTACKER_COMPLETED_RE.findall(log_text)),
    }
    if ru_last_kpi:
        result.update(ru_last_kpi)
    else:
        result.update({field: None for field in RU_KPI_FIELDS})
    result["parse_note"] = (
        "ru_* fields are per-second rates from the last ru_emulator KPI table row; "
        "ru_crashed/ru_crash_reason capture the slot_point assertion crash caused by "
        "replayed eCPRI C-plane packets with bogus slot fields; du_* counts are gnb "
        "DU OFH reception drops; attacker_replays_completed counts finished pcap "
        "injections. Legacy instrumented-log fields stay None when unavailable."
    )
    return result


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
    "ru_rx_total",
    "ru_rx_on_time",
    "ru_rx_early",
    "ru_rx_late",
    "ru_rx_seq_err",
    "ru_rx_on_time_c",
    "ru_rx_early_c",
    "ru_rx_late_c",
    "ru_rx_seq_err_c",
    "ru_rx_corrupt",
    "ru_rx_err_drop",
    "ru_tx_total",
    "ru_kpi_rows",
    "ru_crashed",
    "ru_crash_reason",
    "ru_wake_late_events",
    "du_ofh_drop_msgs",
    "du_not_uplink_msgs",
    "du_eaxc_drop_msgs",
    "attacker_replays_completed",
    "error",
]