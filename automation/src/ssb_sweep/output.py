"""Output directory management: raw logs, parsed metrics CSV/JSON, per-step dirs."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

METRICS_FIELDS = [
    "step",
    "run_id",
    "burst_interval_us",
    "periodicity_ms",
    "tx_gain_db",
    "burst_length_ms",
    "pss_sss_correlation_peak_ratio",
    "pbch_block_error_rate",
    "coreset0_blind_decode_failure_rate",
    "sib1_decode_timeout_count",
    "attach_denial_pct",
    "attach_denied_observed",
    "attach_attempts_observed",
    "time_to_camp_ms",
    "cell_barred_detected",
    "mib_crc_err",
    "coreset0_out_of_bounds",
]


class OutputDir:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create(cls, base: Path) -> "OutputDir":
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return cls(base / stamp)

    def step_dir(self, run_id: str) -> Path:
        d = self.root / f"step_{run_id}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_raw_log(self, run_id: str, text: str) -> Path:
        p = self.step_dir(run_id) / "raw.log"
        p.write_text(text, "utf-8")
        return p

    def write_step_config(self, run_id: str, config_yaml: str) -> Path:
        p = self.step_dir(run_id) / "config.yaml"
        p.write_text(config_yaml, "utf-8")
        return p

    def write_step_metrics(self, run_id: str, metrics: dict[str, Any]) -> Path:
        p = self.step_dir(run_id) / "metrics.json"
        p.write_text(json.dumps(metrics, indent=2), "utf-8")
        return p

    def write_metrics_table(self, rows: Iterable[dict[str, Any]]) -> tuple[Path, Path]:
        rows = list(rows)
        csv_path = self.root / "metrics.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=METRICS_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        json_path = self.root / "metrics.json"
        json_path.write_text(json.dumps(rows, indent=2), "utf-8")
        return csv_path, json_path

    def write_summary(self, text: str) -> Path:
        p = self.root / "SUMMARY.md"
        p.write_text(text, "utf-8")
        return p

    def write_mcp_debug(self, text: str) -> Path:
        p = self.root / "mcp_server_stderr.log"
        p.write_text(text, "utf-8")
        return p