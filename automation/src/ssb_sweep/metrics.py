"""Log parsing to L1 / L2 / L3 metrics for the SSB spoofer attack.

The results paragraph asks to record, per sweep step:

  Layer 1: PSS/SSS correlation peak ratio (spoofer vs gNB), PBCH block error rate
  Layer 2: CORESET0 blind decode failure rate, SIB1 decode timeout count
  Layer 3: percentage of legitimate UE attach attempts denied (out of 50),
           time-to-camp latency (ms), and failure signatures
           (CELL_BARRED_DETECTED, MIB_CRC_ERR, CORESET0_OUT_OF_BOUNDS)

Several of these (PSS/SSS ratio, PBCH BLER, CORESET0 decode failure rate, SIB1
timeout count) require instrumented receiver/UE data that the spoofer logs do
not contain. Where the metric is not parseable from available logs it is
recorded as ``None`` with ``source="unavailable"`` and a note below.

Signatures that ARE textually parseable from UE/controller logs:
  CELL_BARRED_DETECTED, MIB_CRC_ERR, CORESET0_OUT_OF_BOUNDS (counted).
"""

from __future__ import annotations

import re
from typing import Any

FAILURE_SIGNATURES = ("CELL_BARRED_DETECTED", "MIB_CRC_ERR", "CORESET0_OUT_OF_BOUNDS")
FAILURE_RE = re.compile(
    r"|".join(re.escape(sig) for sig in FAILURE_SIGNATURES)
)

# Attempts context: the L3 attach-denial % is defined out of 50 attempts.
DENIED_ATTACH_RE = re.compile(r"(?:attach|registration|camping).*?(denied|reject|fail)", re.IGNORECASE)
ATTACH_RE = re.compile(r"(?:attach|registration).{0,60}(?:attempt|request|success|denied|reject|fail)", re.IGNORECASE)


def count_failure_signatures(log_text: str) -> dict[str, int]:
    counts = {sig: 0 for sig in FAILURE_SIGNATURES}
    for match in FAILURE_RE.finditer(log_text):
        counts[match.group(0)] += 1
    return counts


def parse_metrics(run_id: str, log_text: str) -> dict[str, Any]:
    sig = count_failure_signatures(log_text)

    # Attach denial % (only meaningful if the logs quantify attempts; falls back
    # to None with a documented placeholder since we have no UE-side tally).
    denied = len(DENIED_ATTACH_RE.findall(log_text))
    attempts = len(ATTACH_RE.findall(log_text))
    attach_denial_pct = round(100.0 * denied / attempts, 2) if attempts else None

    return {
        "run_id": run_id,
        # Layer 1
        "pss_sss_correlation_peak_ratio": None,      # needs instrumented spoofer/gnb
        "pbch_block_error_rate": None,               # needs UE decoder stats
        # Layer 2
        "coreset0_blind_decode_failure_rate": None,  # needs UE decoder stats
        "sib1_decode_timeout_count": None,           # needs UE RRC stats
        # Layer 3
        "attach_denial_pct": attach_denial_pct,
        "attach_denied_observed": denied,
        "attach_attempts_observed": attempts,
        "time_to_camp_ms": None,                     # needs UE timing instrumentation
        "cell_barred_detected": sig["CELL_BARRED_DETECTED"],
        "mib_crc_err": sig["MIB_CRC_ERR"],
        "coreset0_out_of_bounds": sig["CORESET0_OUT_OF_BOUNDS"],
        "signature_counts": sig,
        "parse_note": (
            "PSS/SSS ratio, PBCH BLER, CORESET0 decode failure rate, SIB1 timeout, "
            "and time-to-camp require instrumented receiver/UE data not present in "
            "automation-captured logs; attach-denial % and signatures are best-effort "
            "regex tallies over available logs."
        ),
    }


def metrics_example(step_index: int, run_id: str, burst_interval_us: int, periodicity_ms: int) -> dict[str, Any]:
    """Stub row used to bootstrap the CSV header + a documented empty row."""
    return {
        "step": step_index,
        "run_id": run_id,
        "burst_interval_us": burst_interval_us,
        "periodicity_ms": periodicity_ms,
        "tx_gain_db": 60.0,
        "burst_length_ms": 1,
        "pss_sss_correlation_peak_ratio": None,
        "pbch_block_error_rate": None,
        "coreset0_blind_decode_failure_rate": None,
        "sib1_decode_timeout_count": None,
        "attach_denial_pct": None,
        "attach_denied_observed": 0,
        "attach_attempts_observed": 0,
        "time_to_camp_ms": None,
        "cell_barred_detected": 0,
        "mib_crc_err": 0,
        "coreset0_out_of_bounds": 0,
    }