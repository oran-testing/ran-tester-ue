"""SSB spoofer sweep definition.

The attack under test comes from the RAN Tester UE results paragraph:

  "For the SSB spoofer (configs/ssb_spoofer/srs_band3.yaml), the parameter to
  sweep is attack.burst_interval_us from 19000 down to 2000 us (producing
  effective periodicities of 20 ms, 10 ms, 5 ms, and 3 ms with burst_length_ms
  = 1), tested under attack.modify_cell_barred = true,
  attack.modify_coreset0_idx = true, and attack.modify_ss0_idx = true at fixed
  rf.tx_gain_db = 60.0 against the 70 dB gNB signal."

EFFECTIVE_PERIODICITY = burst_length_ms + (burst_interval_us / 1000)
=> burst_interval_us 19000 -> 20 ms
=> burst_interval_us  9000 -> 10 ms
=> burst_interval_us  4000 ->  5 ms
=> burst_interval_us  2000 ->  3 ms
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_BASE_CONFIG = (
    REPO_ROOT / "configs" / "ssb_spoofer" / "srs_band3.yaml"
)

# burst_interval_us values, ordered from most to least aggressive.
SWEEP_STEPS_US: list[tuple[int, str]] = [
    (19000, "20ms"),
    (9000, "10ms"),
    (4000, "5ms"),
    (2000, "3ms"),
]

COMPONENT_TYPE = "ssb_spoofer"
COMPONENT_REPO = "oran-testing/ssb-spoofer"
WORKER_THREAD = "ssb_spoofer"

# Fixed attack/test parameters per the results paragraph.
FIXED_TX_GAIN_DB = 60.0
BURST_LENGTH_MS = 1


def effective_periodicity_ms(burst_interval_us: int) -> int:
    return BURST_LENGTH_MS + (burst_interval_us // 1000)


@dataclass
class SweepStep:
    index: int
    burst_interval_us: int
    periodicity_ms: int
    run_id: str
    config: dict[str, Any]
    config_yaml: str


def load_base_config(path: Path | str = DEFAULT_BASE_CONFIG) -> dict[str, Any]:
    import yaml

    base = Path(path)
    if not base.exists():
        raise FileNotFoundError(f"Base config not found: {base}")
    with base.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise ValueError(f"Base config {base} did not parse to a mapping")
    for section in ("rf", "ssb", "attack", "operation"):
        if section not in cfg:
            raise ValueError(f"Base config {base} is missing required section '{section}'")
    return cfg


def build_step_config(base_cfg: dict[str, Any], step_index: int, burst_interval_us: int) -> dict[str, Any]:
    """Return a mutated copy of the base config for one sweep step."""
    cfg = copy.deepcopy(base_cfg)

    run_id = f"ssb_spoofer_sweep_{step_index}_{burst_interval_us}us"

    # Ensure the id lives at top level (controller converter drops it on write).
    cfg["id"] = run_id

    # Fixed attack flags from the results paragraph.
    attack = cfg["attack"]
    attack["modify_cell_barred"] = True
    attack["cell_barred_value"] = True
    attack["modify_coreset0_idx"] = True
    attack["modify_ss0_idx"] = True
    attack["burst_interval_us"] = burst_interval_us
    attack["burst_length_ms"] = BURST_LENGTH_MS

    # Fixed transmit gain.
    cfg["rf"]["tx_gain_db"] = FIXED_TX_GAIN_DB

    # Per-step operation identity.
    operation = cfg["operation"]
    operation["log_file"] = f"{run_id}.log"

    return cfg


def make_run_id(step_index: int, burst_interval_us: int) -> str:
    return f"ssb_spoofer_sweep_{step_index}_{burst_interval_us}us"


def build_steps(base_cfg: dict[str, Any]) -> list[SweepStep]:
    import yaml

    steps: list[SweepStep] = []
    for idx, (burst_us, _label) in enumerate(SWEEP_STEPS_US):
        cfg = build_step_config(base_cfg, idx + 1, burst_us)
        run_id = cfg["id"]
        steps.append(
            SweepStep(
                index=idx + 1,
                burst_interval_us=burst_us,
                periodicity_ms=effective_periodicity_ms(burst_us),
                run_id=run_id,
                config=cfg,
                config_yaml=yaml.safe_dump(cfg, sort_keys=False, indent=2),
            )
        )
    return steps