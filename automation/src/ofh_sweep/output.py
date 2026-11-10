"""Output directory management for OFH DoS attacker sweep.

Per-step directories, raw logs, parsed metrics CSV/JSON, summary.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from ofh_sweep.metrics import METRICS_FIELDS

METRICS_CSV_FIELDS = METRICS_FIELDS + ["baseline"]


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

    def write_step_config(self, run_id: str, config_toml: str) -> Path:
        p = self.step_dir(run_id) / "config.toml"
        p.write_text(config_toml, "utf-8")
        return p

    def write_step_metrics(self, run_id: str, metrics: dict[str, Any]) -> Path:
        p = self.step_dir(run_id) / "metrics.json"
        p.write_text(json.dumps(metrics, indent=2), "utf-8")
        return p

    def write_metrics_table(self, rows: Iterable[dict[str, Any]]) -> tuple[Path, Path]:
        rows = list(rows)
        csv_path = self.root / "metrics.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=METRICS_CSV_FIELDS, extrasaction="ignore")
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