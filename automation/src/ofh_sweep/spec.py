"""OFH DoS attacker sweep definition.

Sweeps tcpreplay_topspeed (0 vs. 1) and packet pacing rates
across 100 Mbps, 500 Mbps, 1 Gbps, 5 Gbps, and 10 Gbps for both
DU and RU injection_points.

Expected metrics per step:
  Transport:   eCPRI frame loss %, switch buffer queue drops
  Sync:        IEEE 1588 PTP phase error (ns), slave clock out-of-lock duration
  Radio:       baseband processing deadline miss rate (ru.log, gnb_emu.log),
               over-the-air frame drop rate
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_BASE_CONFIG = REPO_ROOT / "configs" / "ofh" / "ofh.toml"

COMPONENT_TYPE = "ofh"
COMPONENT_REPO = "oran-testing/dos-attacker"
WORKER_THREAD = "ofh_attacker"

TOPSPEED_VALUES = [0, 1]

PCAP_RATES_MBPS = [100, 500, 1000, 5000, 10000]

INJECTION_POINTS = ["DU", "RU"]


@dataclass
class SweepStep:
    index: int
    topspeed: int
    mbps: int
    injection_point: str
    run_id: str
    config: dict[str, Any]
    config_toml: str


def load_base_config(path: Path | str = DEFAULT_BASE_CONFIG) -> dict[str, Any]:
    import toml

    base = Path(path)
    if not base.exists():
        raise FileNotFoundError(f"Base config not found: {base}")
    with base.open("r", encoding="utf-8") as fh:
        cfg = toml.load(fh)
    if not isinstance(cfg, dict):
        raise ValueError(f"Base config {base} did not parse to a mapping")
    return cfg


def build_step_config(
    base_cfg: dict[str, Any],
    step_index: int,
    topspeed: int,
    mbps: int,
    injection_point: str,
) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)

    run_id = f"ofh_sweep_{step_index:04d}_ts{topspeed}_{mbps}mbps_{injection_point}"

    cfg["id"] = run_id
    cfg["tcpreplay_topspeed"] = topspeed
    cfg["tcpreplay_mbps"] = mbps
    cfg["injection_points"] = [injection_point]
    cfg["pcap_list"] = []
    cfg["du"] = "lo"
    cfg["ru"] = "lo"

    return cfg


def generate_steps(base_cfg: dict[str, Any]) -> list[SweepStep]:
    import toml

    steps: list[SweepStep] = []
    idx = 0
    for topspeed in TOPSPEED_VALUES:
        for mbps in PCAP_RATES_MBPS:
            for ip in INJECTION_POINTS:
                cfg = build_step_config(base_cfg, idx, topspeed, mbps, ip)
                run_id = cfg["id"]
                config_data = {k: v for k, v in cfg.items() if k != "id"}
                config_toml = toml.dumps(config_data)
                steps.append(
                    SweepStep(
                        index=idx,
                        topspeed=topspeed,
                        mbps=mbps,
                        injection_point=ip,
                        run_id=run_id,
                        config=cfg,
                        config_toml=config_toml,
                    )
                )
                idx += 1
    return steps