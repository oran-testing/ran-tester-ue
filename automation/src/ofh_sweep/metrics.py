"""Log parsing for OFH DoS attacker sweep metrics.

Expected metrics per sweep step:
  Transport:   eCPRI frame loss %, switch buffer queue drops
  Sync:        IEEE 1588 PTP phase error (ns), slave clock out-of-lock duration
  Radio:       baseband processing deadline miss rate (ru.log, gnb_emu.log),
               over-the-air frame drop rate

These require instrumented logs from the OFH attacker, ru_emulator, and
gnb_emulator. All are recorded as None when unavailable from logs.
"""

from __future__ import annotations

import re
from typing import Any

ECPRI_LOSS_RE = re.compile(r"ecpri.*frame.*loss[ :]*([0-9.]+)%?", re.IGNORECASE)
SWITCH_DROP_RE = re.compile(r"switch.*buffer.*(?:drop|discard)[ :]*([0-9]+)", re.IGNORECASE)
PTP_PHASE_ERROR_RE = re.compile(r"ptp.*phase.*error[ :]*([0-9.]+)", re.IGNORECASE)
PTP_OUT_OF_LOCK_RE = re.compile(r"(?:ptp|slave).*(?:out.?of.?lock|unlocked)[ :]*([0-9.]+)", re.IGNORECASE)
DEADLINE_MISS_RE = re.compile(r"(?:baseband|bb).*(?:deadline|miss)[ :]*([0-9.]+)", re.IGNORECASE)
OTA_DROP_RE = re.compile(r"(?:ota|over.?the.?air).*(?:frame|drop|loss)[ :]*([0-9.]+)", re.IGNORECASE)


def parse_metrics(run_id: str, log_text: str) -> dict[str, Any]:
    ecpri_match = ECPRI_LOSS_RE.search(log_text)
    switch_match = SWITCH_DROP_RE.search(log_text)
    ptp_phase_match = PTP_PHASE_ERROR_RE.search(log_text)
    ptp_lock_match = PTP_OUT_OF_LOCK_RE.search(log_text)
    deadline_match = DEADLINE_MISS_RE.search(log_text)
    ota_match = OTA_DROP_RE.search(log_text)

    return {
        "run_id": run_id,
        "ecpri_frame_loss_pct": float(ecpri_match.group(1)) if ecpri_match else None,
        "switch_buffer_queue_drops": int(switch_match.group(1)) if switch_match else None,
        "ptp_phase_error_ns": float(ptp_phase_match.group(1)) if ptp_phase_match else None,
        "ptp_out_of_lock_duration_s": float(ptp_lock_match.group(1)) if ptp_lock_match else None,
        "bb_deadline_miss_rate": float(deadline_match.group(1)) if deadline_match else None,
        "ota_frame_drop_rate": float(ota_match.group(1)) if ota_match else None,
        "parse_note": (
            "eCPRI loss, switch drops, PTP phase/out-of-lock, baseband deadline miss, "
            "and OTA frame drop require instrumented logs (ru.log, gnb_emu.log, "
            "attacker results). Values recorded as None when unavailable."
        ),
    }


METRICS_FIELDS = [
    "run_index",
    "topspeed",
    "mbps",
    "injection_point",
    "ecpri_frame_loss_pct",
    "switch_buffer_queue_drops",
    "ptp_phase_error_ns",
    "ptp_out_of_lock_duration_s",
    "bb_deadline_miss_rate",
    "ota_frame_drop_rate",
    "error",
]