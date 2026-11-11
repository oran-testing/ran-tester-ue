"""Victim testbed for the OFH DoS sweep.

Runs a srsRAN Project gnb (DU) + ru_emulator (RU) pair over Open Fronthaul on
the loopback interface (`lo`), plus a minimal open5gs AMF so the gnb survives
(NG Setup completes instead of the CU-CP exiting when AMF is unreachable).

Configs are derived from the repo's configs/ru_emulator/{emu_lo.yaml,gnb_lo.yaml}
with only the log sinks redirected to stdout so per-step `docker logs --since`
captures them into each sweep step directory (ru.log / du.log).
"""
from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]  # /home/charles/ran-tester-ue
AUTOMATION_DIR = REPO_ROOT / "automation"
TESTBED_DIR = AUTOMATION_DIR / ".testbed"

TESTBED_IMAGE = "rtue-ofh-testbed:latest"
AMF_IMAGE = "rtue-open5gs-amf:latest"
NRF_CONTAINER = "nrf_emulator"
AMF_CONTAINER = "amf_emulator"
RU_CONTAINER = "ru_emulator"
DU_CONTAINER = "gnb_emulator"

RU_CONFIG_SRC = REPO_ROOT / "configs" / "ru_emulator" / "emu_lo.yaml"
DU_CONFIG_SRC = REPO_ROOT / "configs" / "ru_emulator" / "gnb_lo.yaml"

# stdbuf -oL forces line buffering: ru_emulator's fmt::print KPI rows otherwise
# sit in a 4KB stdio buffer (~23 rows) and only flush in bursts.
RU_COMMAND = ["stdbuf", "-oL", "ru_emulator", "-c", "/config.yml"]
DU_COMMAND = ["gnb", "-c", "/config.yml"]
NRF_COMMAND = ["open5gs-nrfd", "-c", "/nrf.yml"]
AMF_COMMAND = ["open5gs-amfd", "-c", "/amf.yml"]

# KPI data row, e.g. "| 17:44:31 |  0  |    15360    | ... |"
RU_KPI_ROW_RE = re.compile(r"(?m)^\|\s*\d{2}:\d{2}:\d{2}\s*\|")

BUILD_LOG = TESTBED_DIR / "image_build.log"
AMF_BUILD_LOG = TESTBED_DIR / "amf_image_build.log"

# Minimal open5gs AMF matching gnb_lo.yaml: ngap 127.0.1.100:38412, plmn 001/01, tac 7.
# open5gs 2.8 requires an NRF (or SCP) for NF registration, so a companion NRF runs
# from the same image.
NRF_CONFIG = """\
logger:
  file:
    path: /tmp/nrf.log

nrf:
  sbi:
    server:
      - address: 127.0.0.10
        port: 7777
"""

AMF_CONFIG = """\
logger:
  file:
    path: /tmp/amf.log

amf:
  sbi:
    server:
      - address: 127.0.0.5
        port: 7777
    client:
      nrf:
        - uri: http://127.0.0.10:7777
  ngap:
    server:
      - address: 127.0.1.100
  guami:
    - plmn_id:
        mcc: 001
        mnc: 01
      amf_id:
        region: 2
        set: 1
  tai:
    - plmn_id:
        mcc: 001
        mnc: 01
      tac: 7
  plmn_support:
    - plmn_id:
        mcc: 001
        mnc: 01
      s_nssai:
        - sst: 1
  security:
    integrity_order: [NIA2, NIA1, NIA0]
    ciphering_order: [NEA0, NEA1, NEA2]
  network_name:
    full: Open5GS
  amf_name: open5gs-amf0
  time:
    t3512:
      value: 540
"""


def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def image_exists(image: str) -> bool:
    return _run(["docker", "image", "inspect", image]).returncode == 0


def build_image(image: str, dockerfile: str, log_file: Path, timeout: int = 2400) -> None:
    TESTBED_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "build", "-f", dockerfile, "-t", image, str(AUTOMATION_DIR)]
    with log_file.open("w") as f:
        proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError(f"docker build {image} timed out; see {log_file}")
    if rc != 0:
        tail = "\n".join(log_file.read_text().splitlines()[-50:])
        raise RuntimeError(f"docker build {image} failed (rc={rc}); see {log_file}\n{tail}")


def _adapt_config(text: str, replacements: list[tuple[str, str]]) -> str:
    for old, new in replacements:
        if old not in text:
            raise RuntimeError(f"pattern {old!r} not found in victim config source")
        text = text.replace(old, new)
    return text


def write_configs() -> dict[str, Path]:
    TESTBED_DIR.mkdir(parents=True, exist_ok=True)
    ru_src = RU_CONFIG_SRC.read_text()
    du_src = DU_CONFIG_SRC.read_text()

    ru_text = _adapt_config(
        ru_src,
        [
            ("filename: /tmp/ru_emu.log", "filename: stdout"),
            ("level: warning", "level: info"),
        ],
    )
    du_text = _adapt_config(
        du_src,
        [
            ("filename: /tmp/gnb.log", "filename: stdout"),
            ("all_level: warning", "all_level: info"),
        ],
    )

    paths = {
        "ru": TESTBED_DIR / "ru.yml",
        "du": TESTBED_DIR / "du.yml",
        "amf": TESTBED_DIR / "amf.yml",
        "nrf": TESTBED_DIR / "nrf.yml",
    }
    paths["ru"].write_text(ru_text)
    paths["du"].write_text(du_text)
    paths["amf"].write_text(AMF_CONFIG)
    paths["nrf"].write_text(NRF_CONFIG)
    return paths


def _container_state(name: str) -> str:
    res = _run(["docker", "inspect", "-f", "{{.State.Status}}", name])
    return res.stdout.strip() if res.returncode == 0 else "missing"


def _container_logs(name: str, tail: int = 50) -> str:
    res = _run(["docker", "logs", "--tail", str(tail), name])
    return (res.stdout + res.stderr).strip()


def _ensure_container(name: str, image: str, command: list[str], config_mount: tuple[str, str]) -> None:
    state = _container_state(name)
    if state == "running":
        return
    if state != "missing":
        _run(["docker", "rm", "-f", name])
    src, dst = config_mount
    cmd = [
        "docker", "run", "-d", "--name", name,
        "--network", "host", "--privileged",
        "-v", f"{src}:{dst}:ro",
        image, *command,
    ]
    res = _run(cmd)
    if res.returncode != 0:
        raise RuntimeError(f"failed to start {name}: {res.stderr.strip()}")
    time.sleep(3)
    if _container_state(name) != "running":
        raise RuntimeError(
            f"{name} is not running after start; last logs:\n{_container_logs(name)}"
        )


def ensure_testbed() -> dict[str, str]:
    """Build images (if needed), write configs, and start AMF + RU + DU."""
    if not image_exists(TESTBED_IMAGE):
        build_image(TESTBED_IMAGE, str(AUTOMATION_DIR / "docker" / "Dockerfile.ofh_testbed"), BUILD_LOG)
    if not image_exists(AMF_IMAGE):
        build_image(AMF_IMAGE, str(AUTOMATION_DIR / "docker" / "Dockerfile.open5gs_amf"), AMF_BUILD_LOG)
    paths = write_configs()

    # NRF first (AMF needs it for NF registration), then AMF so gnb NG Setup succeeds.
    _ensure_container(NRF_CONTAINER, AMF_IMAGE, NRF_COMMAND, (str(paths["nrf"]), "/nrf.yml"))
    time.sleep(1)
    _ensure_container(AMF_CONTAINER, AMF_IMAGE, AMF_COMMAND, (str(paths["amf"]), "/amf.yml"))
    time.sleep(2)
    _ensure_container(RU_CONTAINER, TESTBED_IMAGE, RU_COMMAND, (str(paths["ru"]), "/config.yml"))
    _ensure_container(DU_CONTAINER, TESTBED_IMAGE, DU_COMMAND, (str(paths["du"]), "/config.yml"))
    time.sleep(5)
    return {name: _container_state(name) for name in (NRF_CONTAINER, AMF_CONTAINER, RU_CONTAINER, DU_CONTAINER)}


def _restart_container(name: str, image: str, command: list[str], config_mount: tuple[str, str]) -> None:
    _run(["docker", "rm", "-f", name])
    src, dst = config_mount
    cmd = [
        "docker", "run", "-d", "--name", name,
        "--network", "host", "--privileged",
        "-v", f"{src}:{dst}:ro",
        image, *command,
    ]
    res = _run(cmd)
    if res.returncode != 0:
        raise RuntimeError(f"failed to start {name}: {res.stderr.strip()}")


def ensure_victim_alive(always_restart_ru: bool = True) -> dict[str, str]:
    """Refresh victims before a sweep step.

    The RU emulator is always restarted so each step starts from fresh KPI
    counters (the attack crashes it via a slot_point assertion); DU/AMF/NRF
    are restarted only if they exited.
    """
    paths = write_configs()
    _ensure_container(NRF_CONTAINER, AMF_IMAGE, NRF_COMMAND, (str(paths["nrf"]), "/nrf.yml"))
    _ensure_container(AMF_CONTAINER, AMF_IMAGE, AMF_COMMAND, (str(paths["amf"]), "/amf.yml"))
    _ensure_container(DU_CONTAINER, TESTBED_IMAGE, DU_COMMAND, (str(paths["du"]), "/config.yml"))
    states = {
        NRF_CONTAINER: _container_state(NRF_CONTAINER),
        AMF_CONTAINER: _container_state(AMF_CONTAINER),
        DU_CONTAINER: _container_state(DU_CONTAINER),
    }

    if always_restart_ru:
        _restart_container(RU_CONTAINER, TESTBED_IMAGE, RU_COMMAND, (str(paths["ru"]), "/config.yml"))
        time.sleep(2)
        if _container_state(RU_CONTAINER) != "running":
            raise RuntimeError(
                f"{RU_CONTAINER} is not running after restart; last logs:\n"
                f"{_container_logs(RU_CONTAINER)}"
            )
        states[RU_CONTAINER] = "restarted"
    else:
        _ensure_container(RU_CONTAINER, TESTBED_IMAGE, RU_COMMAND, (str(paths["ru"]), "/config.yml"))
        states[RU_CONTAINER] = _container_state(RU_CONTAINER)
    return states


def wait_ru_kpi_rows(timeout: float = 45.0, poll: float = 2.0) -> bool:
    """Block until the RU prints its first KPI row (after its ~20s test-data warmup)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = _run(["docker", "logs", RU_CONTAINER])
        if RU_KPI_ROW_RE.search(res.stdout + res.stderr):
            time.sleep(4)  # gather a few baseline rows before the attack starts
            return True
        time.sleep(poll)
    return False


def collect_victim_logs(step_dir: Path, since: float) -> str:
    """Capture RU/DU/AMF logs since `since` (unix ts) into step_dir; return combined text."""
    step_dir.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []

    for name, fname in ((RU_CONTAINER, "ru.log"), (DU_CONTAINER, "du.log")):
        res = _run(["docker", "logs", "--since", str(int(since)), name])
        text = (res.stdout + res.stderr) if res.returncode == 0 else ""
        (step_dir / fname).write_text(text)
        if text:
            parts.append(f"===== {name} =====\n{text}")

    # open5gs logs to a file inside its container.
    res = _run(["docker", "exec", AMF_CONTAINER, "cat", "/tmp/amf.log"])
    amf_text = res.stdout if res.returncode == 0 else ""
    (step_dir / "amf.log").write_text(amf_text)
    if amf_text:
        parts.append(f"===== {AMF_CONTAINER} =====\n{amf_text}")

    return "\n".join(parts)


def stop_testbed() -> None:
    for name in (DU_CONTAINER, RU_CONTAINER, AMF_CONTAINER, NRF_CONTAINER):
        _run(["docker", "rm", "-f", name])


if __name__ == "__main__":
    import json

    print(json.dumps(ensure_testbed(), indent=2))
