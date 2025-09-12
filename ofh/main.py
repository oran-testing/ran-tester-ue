import os
import subprocess
from pathlib import Path
from shutil import which
import glob
import time

try:
    import tomllib
except Exception:
    import tomli as tomllib

def hdr(title):
    print(title)

def show_env(keys):
    for k in keys:
        print(f"{k}={os.environ.get(k)!r}")

def ls_dir(p, max_items=10):
    p = Path(p)
    if not p.exists():
        print(f"{p} does not exist")
        return 0
    if not p.is_dir():
        print(f"{p} exists but is not a directory")
        return 0
    items = list(p.iterdir())
    print(f"{p} exists ({len(items)} items). Showing up to {max_items}:")
    for x in items[:max_items]:
        print(f"  - {x.name}/" if x.is_dir() else f"  - {x.name}")
    if len(items) > max_items:
        print(f"  … ({len(items)-max_items} more)")
    return len(items)

def check_tools():
    for t in ["tcpreplay", "python3", "bash"]:
        path = which(t)
        if path:
            print(f"Tool: {t} -> {path}")
        else:
            print(f"Tool missing from PATH: {t}")

def run_attacker_with_trace(env_vars):
    hdr("Run attacker (with bash -x tracing)")
    cmd = ["bash", "-lc", "set -x; ./auto_attacker.sh"]
    result = subprocess.run(cmd, env=env_vars, text=True)
    print(f"[auto_attacker.sh] exited with code {result.returncode}")
    return result.returncode

def require(cfg, key):
    if key not in cfg:
        raise SystemExit(f"Config missing required key: {key}")
    return cfg[key]

def load_config():
    cfg_path = os.environ.get("CONFIG_TOML", "/attack_env/ofh.toml")
    print(f"Loading config: {cfg_path}")
    with open(cfg_path, "rb") as f:
        cfg = tomllib.load(f)
    return cfg

def normalize_path(base_dir, p):
    pp = Path(p)
    if pp.is_absolute():
        return str(pp)
    return str(Path(base_dir) / pp)

def build_attack_list(pcap_dir, pcap_list_cfg):
    if pcap_list_cfg and isinstance(pcap_list_cfg, list) and len(pcap_list_cfg) > 0:
        print(f"[DEBUG] ATTACK_LIST taken from config list with {len(pcap_list_cfg)} entries")
        return [str(x) for x in pcap_list_cfg]
    paths = sorted(Path(pcap_dir).glob("*.pcap"))
    print(f"[DEBUG] ATTACK_LIST derived from pcap_dir={pcap_dir} count={len(paths)}")
    return [p.name for p in paths]

def run_pipeline():
    hdr("Config and mounts sanity checks")

    cfg = load_config()

    attacker_dir = require(cfg, "attacker_dir")
    pcap_dir_cfg = require(cfg, "pcap_dir")
    results_dir_cfg = require(cfg, "results_dir")
    du_if = require(cfg, "du")
    ru_if = require(cfg, "ru")
    inj_list = require(cfg, "injection_points")
    duration = int(require(cfg, "duration_seconds"))
    topspeed = int(require(cfg, "tcpreplay_topspeed"))
    loopcount = int(require(cfg, "tcpreplay_loop"))
    keep_history = str(require(cfg, "keep_history"))
    pcap_list_cfg = cfg.get("pcap_list", [])

    ATTACKER_DIR = attacker_dir
    pcap_dir = normalize_path(ATTACKER_DIR, pcap_dir_cfg)
    results_dir = normalize_path(ATTACKER_DIR, results_dir_cfg)

    attack_list = build_attack_list(pcap_dir, pcap_list_cfg)
    if len(attack_list) == 0:
        raise SystemExit(f"No .pcap files found under {pcap_dir} and pcap_list is empty")

    os.environ["ATTACKER_DIR"] = ATTACKER_DIR
    os.environ["TRAFFIC_DIR"] = pcap_dir
    os.environ["RESULTS_DIR"] = results_dir
    os.environ["INTERFACE_DU"] = du_if
    os.environ["INTERFACE_RU"] = ru_if
    if not inj_list or not isinstance(inj_list, list) or len(inj_list) == 0:
        raise SystemExit("injection_points must be a non-empty list in config")
    os.environ["INJECTION_POINTS"] = ",".join(inj_list)
    os.environ["ATTACK_LIST"] = ",".join(attack_list)
    os.environ["DURATION_SECONDS"] = str(duration)
    os.environ["TCPREPLAY_TOPSPEED"] = str(topspeed)
    os.environ["TCPREPLAY_LOOP"] = str(loopcount)
    os.environ["KEEP_HISTORY"] = keep_history

    show_env([
        "ATTACKER_DIR","TRAFFIC_DIR","RESULTS_DIR",
        "INTERFACE_DU","INTERFACE_RU","INJECTION_POINTS",
        "ATTACK_LIST","DURATION_SECONDS","TCPREPLAY_TOPSPEED","TCPREPLAY_LOOP","KEEP_HISTORY"
    ])

    print("\nWorking directory")
    print(f"PWD: {Path.cwd()}")

    print("\nCheck required tools")
    check_tools()

    print("\nCheck repo/work dir")
    ls_dir(ATTACKER_DIR)

    print("\nCheck Traffic dir")
    ls_dir(pcap_dir)
    pcaps = list(Path(pcap_dir).glob("*.pcap"))
    print(f"Found {len(pcaps)} *.pcap under {pcap_dir}")
    for p in pcaps[:10]:
        print(f"  - {p}")

    print("\nResults directory sanity")
    Path(results_dir).mkdir(parents=True, exist_ok=True)
    ls_dir(Path(results_dir).parent if Path(results_dir).parent != Path('.') else Path.cwd())

    env_vars = os.environ.copy()
    rc = run_attacker_with_trace(env_vars)
    if rc != 0:
        print("Attacker failed")
        return

if __name__ == "__main__":
    run_pipeline()
