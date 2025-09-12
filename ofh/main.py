import os
import subprocess
from pathlib import Path
from shutil import which
import glob
import sys

try:
    import tomllib
except Exception:
    import tomli as tomllib

def hdr(title):
    print(title, flush=True)

def show_env(keys):
    for k in keys:
        print(f"{k}={os.environ.get(k)!r}", flush=True)

def ls_dir(p, max_items=10):
    p = Path(p)
    if not p.exists():
        print(f"{p} does not exist", flush=True)
        return 0
    if not p.is_dir():
        print(f"{p} exists but is not a directory", flush=True)
        return 0
    items = list(p.iterdir())
    print(f"{p} exists ({len(items)} items). Showing up to {max_items}:", flush=True)
    for x in items[:max_items]:
        print(f"  - {x.name}/" if x.is_dir() else f"  - {x.name}", flush=True)
    if len(items) > max_items:
        print(f"  … ({len(items)-max_items} more)", flush=True)
    return len(items)

def check_tools():
    for t in ["tcpreplay", "python3", "bash"]:
        path = which(t)
        if path:
            print(f"Tool: {t} -> {path}", flush=True)
        else:
            print(f"Tool missing from PATH: {t}", flush=True)

def run_attacker_with_trace(env_vars):
    hdr("Run attacker (with bash -x tracing)")
    cmd = ["bash", "-lc", "set -x; ./auto_attacker.sh"]
    result = subprocess.run(cmd, env=env_vars, text=True)
    print(f"[auto_attacker.sh] exited with code {result.returncode}", flush=True)
    return result.returncode

def require(cfg, key):
    if key not in cfg:
        raise SystemExit(f"Config missing required key: {key}")
    return cfg[key]

def load_config():
    cfg_path = os.environ.get("CONFIG_TOML", "/attack_env/ofh.toml")
    print(f"Loading config: {cfg_path}", flush=True)
    with open(cfg_path, "rb") as f:
        cfg = tomllib.load(f)
    return cfg

def normalize_path(base_dir, p):
    pp = Path(p)
    return str(pp) if pp.is_absolute() else str(Path(base_dir) / pp)

def build_attack_list(pcap_dir, pcap_list_cfg):
    if pcap_list_cfg and isinstance(pcap_list_cfg, list) and len(pcap_list_cfg) > 0:
        print(f"[DEBUG] ATTACK_LIST taken from config list with {len(pcap_list_cfg)} entries", flush=True)
        return [str(x) for x in pcap_list_cfg]
    paths = sorted(Path(pcap_dir).glob("*.pcap"))
    print(f"[DEBUG] ATTACK_LIST derived from pcap_dir={pcap_dir} count={len(paths)}", flush=True)
    return [p.name for p in paths]

def collect_result(log_dir="/var/tmp/ru_logs", files=("ru_emulator.log", "gnb.log")):
    """Dump entire log files to stdout so controller ships them to Influx."""
    print("Results from recent attack:", flush=True)
    for fname in files:
        path = os.path.join(log_dir, fname)
        if os.path.exists(path):
            print(f"--- {fname} ---", flush=True)
            # Stream out the whole file
            with open(path, "r", errors="replace") as f:
                for line in f:
                    print(f"[RU] {line.rstrip()}", flush=True)
        else:
            print(f"[WARN] {fname} not found in {log_dir}", flush=True)

def clear_dir(dir_path="/var/tmp/ru_logs", patterns=("*.log",), keep_last_n=0):

    try:
        all_files = []
        for pat in patterns:
            all_files.extend(glob.glob(os.path.join(dir_path, pat)))
        if keep_last_n > 0:
            all_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            to_delete = all_files[keep_last_n:]
        else:
            to_delete = all_files
        for f in to_delete:
            try:
                os.remove(f)
                print(f"[CLEAN] removed {f}", flush=True)
            except Exception as e:
                print(f"[CLEAN][WARN] could not remove {f}: {e}", flush=True)
    except FileNotFoundError:
        pass

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

    print("\nWorking directory", flush=True)
    print(f"PWD: {Path.cwd()}", flush=True)

    print("\nCheck required tools", flush=True)
    check_tools()

    print("\nCheck repo/work dir", flush=True)
    ls_dir(ATTACKER_DIR)

    print("\nCheck Traffic dir", flush=True)
    ls_dir(pcap_dir)
    pcaps = list(Path(pcap_dir).glob("*.pcap"))
    print(f"Found {len(pcaps)} *.pcap under {pcap_dir}", flush=True)
    for p in pcaps[:10]:
        print(f"  - {p}", flush=True)

    print("\nResults directory sanity", flush=True)
    Path(results_dir).mkdir(parents=True, exist_ok=True)
    ls_dir(Path(results_dir).parent if Path(results_dir).parent != Path('.') else Path.cwd())

    env_vars = os.environ.copy()
    rc = run_attacker_with_trace(env_vars)

    if rc != 0:
        print("Attacker failed", flush=True)
        return

    ru_dir = os.getenv("RU_LOG_DIR", "/var/tmp/ru_logs")
    collect_result(log_dir=ru_dir, files=("ru_emulator.log", "gnb.log"))

    # clear_dir(dir_path=ru_dir, patterns=("*.log",), keep_last_n=0)

if __name__ == "__main__":
    run_pipeline()
