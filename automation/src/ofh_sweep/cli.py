"""CLI entry point for the OFH DoS attacker sweep automation.

Enables three modes — config, mcp, and llm — identical in structure to the
SSB spoofer sweep, plus a ``collect`` mode for fetching ru_emulator and gNB
debug logs from Docker.

Usage examples::

    # Run the sweep by talking directly to the controller REST API (no MCP).
    python -m ofh_sweep.cli --mode config

    # Run the sweep through the ran-tester-ue MCP server (docker compose run).
    python -m ofh_sweep.cli --mode mcp

    # Generate an llm_worker config (and optionally inject spec.yaml run_spec).
    python -m ofh_sweep.cli --mode llm --apply-spec

    # Collect ru_emulator and gNB debug logs after a sweep.
    python -m ofh_sweep.cli --mode collect --output /tmp/ofh_logs
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from ofh_sweep.controller_client import ControllerClient
from ofh_sweep.llm_backend import LLM_RUN_SPEC_ENTRY, inject_run_spec, write_llm_config
from ofh_sweep.mcp_backend import McpBackend
from ofh_sweep.metrics import METRICS_FIELDS, parse_metrics
from ofh_sweep.output import OutputDir
from ofh_sweep.spec import (
    COMPONENT_REPO,
    COMPONENT_TYPE,
    DEFAULT_BASE_CONFIG,
    generate_steps,
    load_base_config,
)
from ofh_sweep import testbed

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MCP_DEBUG_FILE = "mcp_server_stderr.log"


def _post_to_controller(client: ControllerClient, cfg: dict, rf: dict) -> dict:
    res = client.start(COMPONENT_TYPE, cfg, rf, COMPONENT_REPO)
    if not res.get("ok"):
        raise RuntimeError(f"start failed: {res.get('error')}")
    return res


def run_config_mode(args: argparse.Namespace, out: OutputDir, client: ControllerClient, rf: dict):
    rows = []
    base_cfg = load_base_config(args.base_config)
    print("Ensuring victim testbed (ru_emulator + gnb_emulator containers)...")
    states = testbed.ensure_testbed()
    print(f"  testbed: {states}")
    for step in generate_steps(base_cfg):
        out.write_step_config(step.run_id, step.config_toml)
        # Restart RU/DU victims fresh so each step starts with clean KPI counters
        testbed.ensure_victim_alive()
        testbed.wait_ru_kpi_rows()
        step_start = time.time()
        try:
            res = _post_to_controller(client, step.config, rf)
            (out.step_dir(step.run_id) / "start.txt").write_text(
                "start response:\n" + str(res.get("data")) + "\n", encoding="utf-8"
            )
        except RuntimeError as e:
            print(f"  ERROR starting {step.run_id}: {e}")
            result_row = {
                "run_index": step.index,
                "topspeed": step.topspeed,
                "mbps": step.mbps,
                "injection_point": step.injection_point,
                "run_id": step.run_id,
                "error": str(e),
            }
            for f in METRICS_FIELDS:
                if f not in result_row:
                    result_row[f] = None
            rows.append(result_row)
            continue

        time.sleep(args.settle)

        logs = ""
        try:
            logs_res = client.logs(step.run_id)
            if logs_res.get("ok"):
                log_lines = [
                    f"[{entry.get('time')}] {entry.get('message')}"
                    for entry in logs_res["data"].get("logs", [])
                ]
                logs = "\n".join(log_lines)
            else:
                logs = f"log fetch error: {logs_res.get('error')}"
        except Exception as exc:  # noqa: BLE001
            logs = f"log fetch error: {exc}"
        out.write_raw_log(step.run_id, logs)

        victim_logs = testbed.collect_victim_logs(out.step_dir(step.run_id), step_start)
        combined_logs = logs + "\n" + victim_logs

        result_row = {"run_index": step.index, "run_id": step.run_id,
                       "topspeed": step.topspeed, "mbps": step.mbps,
                       "injection_point": step.injection_point, "error": None}
        matched = parse_metrics(step.run_id, combined_logs)
        result_row.update(matched)
        out.write_step_metrics(step.run_id, result_row)
        rows.append(result_row)

        if not args.no_stop:
            client.stop(step.run_id)
            print(f"  {step.run_id} stopped")

    csv_path, json_path = out.write_metrics_table(rows)
    summary = [
        f"OFH DoS attacker sweep ({args.mode} mode)",
        f"steps: {len(rows)}",
        f"metrics: {csv_path}",
        f"metrics json: {json_path}",
        "victim testbed: srsRAN ru_emulator (ru.log) and gnb DU (du.log)",
        "containers run on host network lo with VLAN 33; their docker logs",
        "are captured per step alongside the attacker raw.log.",
    ]
    out.write_summary("\n".join(summary))


def run_mcp_mode(args: argparse.Namespace, out: OutputDir, rf: dict):
    dbg = out.root / MCP_DEBUG_FILE
    # docker-compose.yml lives at the repo root, not under automation/
    backend = McpBackend(project_dir=PROJECT_ROOT.parent, stderr_log=dbg, use_sudo=args.sudo)

    rows = []
    base_cfg = load_base_config(args.base_config)
    print("Ensuring victim testbed (ru_emulator + gnb_emulator containers)...")
    states = testbed.ensure_testbed()
    print(f"  testbed: {states}")
    for step in generate_steps(base_cfg):
        out.write_step_config(step.run_id, step.config_toml)
        # Restart RU/DU victims fresh so each step starts with clean KPI counters
        testbed.ensure_victim_alive()
        testbed.wait_ru_kpi_rows()
        step_start = time.time()
        try:
            start_text = backend.start(step.config, rf)
            (out.step_dir(step.run_id) / "start.txt").write_text(start_text, encoding="utf-8")
        except RuntimeError as e:
            print(f"  ERROR starting {step.run_id}: {e}")
            result_row = {
                "run_index": step.index,
                "topspeed": step.topspeed,
                "mbps": step.mbps,
                "injection_point": step.injection_point,
                "run_id": step.run_id,
                "error": str(e),
            }
            for f in METRICS_FIELDS:
                if f not in result_row:
                    result_row[f] = None
            rows.append(result_row)
            continue

        time.sleep(args.settle)

        logs = backend.logs(step.run_id)
        out.write_raw_log(step.run_id, logs)

        victim_logs = testbed.collect_victim_logs(out.step_dir(step.run_id), step_start)
        combined_logs = logs + "\n" + victim_logs

        result_row = {"run_index": step.index, "run_id": step.run_id,
                       "topspeed": step.topspeed, "mbps": step.mbps,
                       "injection_point": step.injection_point, "error": None}
        matched = parse_metrics(step.run_id, combined_logs)
        result_row.update(matched)
        out.write_step_metrics(step.run_id, result_row)
        rows.append(result_row)

        if not args.no_stop:
            backend.stop(step.run_id)
            print(f"  {step.run_id} stopped")

    csv_path, json_path = out.write_metrics_table(rows)
    summary = [
        f"OFH DoS attacker sweep ({args.mode} mode via MCP)",
        f"steps: {len(rows)}",
        f"metrics: {csv_path}",
        f"metrics json: {json_path}",
        f"mcp server stderr: {out.root / MCP_DEBUG_FILE}",
        "victim testbed: srsRAN ru_emulator (ru.log) and gnb DU (du.log)",
        "docker logs captured per step alongside the attacker raw.log.",
    ]
    out.write_summary("\n".join(summary))


def run_llm_mode(args: argparse.Namespace, out: OutputDir):
    repo_root = PROJECT_ROOT.parent  # Go up to ran-tester-ue root
    cfg_path = repo_root / "configs" / "llm" / "ofh_sweep.yaml"
    written = write_llm_config(cfg_path)
    result = inject_run_spec(
        spec_path=repo_root / "spec.yaml",
        entry=LLM_RUN_SPEC_ENTRY,
        apply=args.apply_spec,
        out_dir=repo_root,
    )

    lines = [
        f"LLM config written to: {written}",
        "",
        "To run the sweep through llm_worker, the controller must have a run_spec",
        "entry for the llm_worker (it cannot be started via the /start API or MCP",
        "start_component because it requires results_dir and is not registered in",
        "the controller converters).",
    ]
    if result["applied"]:
        lines += [
            "",
            "Run the following to start the controller with the new run_spec:",
            "    sudo docker compose up -d --force-recreate controller",
            "",
            f"Backup of previous spec.yaml: {result['backup']}",
        ]
    else:
        lines += ["", "Run spec injection was NOT applied (use --apply-spec)."]
        lines += ["", result["instructions"]]
    lines += [
        "",
        "Note: the remote ghcr.io/oran-testing/llm_worker image is prebuilt;",
        "it may predate OFH support. Rebuild locally with:",
        "    docker build -f dockerfiles/Dockerfile.llm_worker \\",
        "        -t ghcr.io/oran-testing/llm_worker .",
        "",
        "Then run the sweep with:",
        "    uv run python3 -m ofh_sweep.cli --mode collect --output <outdir>",
    ]
    out.write_summary("\n".join(lines))
    print("\n".join(lines))


def run_collect_mode(args: argparse.Namespace, out: OutputDir):
    """Collect debug logs from ru_emulator and gNB Docker containers.

    Uses ``docker logs`` and ``docker cp`` to fetch logs from the known
    OCUDU containers (ru_emulator, gnb_emulator / ocudu-gnb).
    Errors are non-fatal — collects whatever is available.
    """
    import subprocess

    ru_names = ["ru_emulator", "ocudu-ru", "ru-emulator"]
    gnb_names = ["gnb_emulator", "ocudu-gnb", "gnb-emulator"]

    collected = out.root / "debug_logs"
    collected.mkdir(parents=True, exist_ok=True)

    for label, names in [("ru_emulator", ru_names), ("gNB", gnb_names)]:
        found = False
        for name in names:
            try:
                result = subprocess.run(
                    ["docker", "inspect", name],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    found = True
                    container_name = name
                    break
            except Exception:
                continue

        if not found:
            print(f"  No running container found for {label} (tried: {names})")
            continue

        # docker logs from the found container
        try:
            logs = subprocess.run(
                ["docker", "logs", "--tail", "500", container_name],
                capture_output=True, text=True, timeout=30,
            )
            log_text = logs.stdout + logs.stderr
            (collected / f"{label}_docker_logs.txt").write_text(
                log_text or f"[No logs for {container_name}]", "utf-8"
            )
            print(f"  Collected docker logs from {container_name} -> debug_logs/{label}_docker_logs.txt")
        except Exception as e:
            print(f"  WARN: docker logs {container_name}: {e}")

        # docker cp of known log files
        remote_paths = [
            f"/var/log/{label.split('_')[0]}/",
            "/tmp/",
            "/app/logs/",
        ]
        for rpath in remote_paths:
            try:
                result = subprocess.run(
                    ["docker", "cp", f"{container_name}:{rpath}", str(collected / f"{label}_files")],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    print(f"  Copied {rpath} from {container_name}")
            except Exception:
                pass

        # docker exec utils to get ru.log / gnb_emu.log if they exist
        for logfile in ["ru.log", "gnb_emu.log", "debug.log", "app.log"]:
            try:
                result = subprocess.run(
                    ["docker", "exec", container_name, "cat", f"/tmp/{logfile}"],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode == 0 and result.stdout:
                    (collected / f"{label}_{logfile}").write_text(result.stdout, "utf-8")
                    print(f"  Collected /tmp/{logfile} from {label}")
            except Exception:
                pass

    # Summary
    files = list(collected.iterdir())
    summary_text = (
        f"Debug log collection ({args.mode} mode)\n"
        f"Output: {collected}\n"
        f"Files collected: {len(files)}\n"
    )
    if files:
        summary_text += "\nFiles:\n" + "\n".join(f"  {f.name}" for f in sorted(files))
    else:
        summary_text += (
            "\nNo logs collected. Ensure ru_emulator and gNB containers are running.\n"
            "Typical container names: ru_emulator, ocudu-ru, gnb_emulator, ocudu-gnb\n"
        )
    (out.root / "SUMMARY.md").write_text(summary_text, "utf-8")
    print(summary_text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ofh-sweep",
        description="OFH DoS attacker sweep: topspeed x mbps x injection_point.",
    )
    parser.add_argument(
        "--mode",
        choices=["config", "mcp", "llm", "collect"],
        default="config",
        help=(
            "Run strategy: direct controller API (config), MCP server (mcp), "
            "llm_worker (llm), or collect debug logs from ru_emulator/gNB (collect)"
        ),
    )
    parser.add_argument(
        "--base-config", type=Path, default=DEFAULT_BASE_CONFIG,
        help="Base TOML to mutate (default: configs/ofh/ofh.toml)",
    )
    parser.add_argument(
        "--controller-url", default="http://localhost:1343",
        help="Controller base URL (config/mcp mode; default http://localhost:1343)",
    )
    parser.add_argument(
        "--token", default="default_changeme",
        help="Controller Bearer token (default: default_changeme)",
    )
    parser.add_argument(
        "--rf-type", choices=["b200", "zmq", "none"], default="none",
        help="rf_config.type for the component (default none; OFH always uses none)",
    )
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "output",
        help="Output directory (a timestamped subdir is created inside)",
    )
    parser.add_argument(
        "--no-stop", action="store_true",
        help="Do not stop components after each step (leave running)",
    )
    parser.add_argument(
        "--settle", type=float, default=15.0,
        help="Seconds to wait after start before fetching logs (default 15.0)",
    )
    parser.add_argument(
        "--apply-spec", action="store_true",
        help="llm mode: insert llm_worker run_spec into spec.yaml and set up",
    )
    parser.add_argument(
        "--sudo", action="store_true", default=True,
        help="Use sudo for docker compose run (default true)",
    )
    parser.add_argument(
        "--no-sudo", dest="sudo", action="store_false",
        help="Do not use sudo for docker compose run",
    )
    args = parser.parse_args(argv)

    if args.mode == "collect":
        out = OutputDir.create(args.output)
        run_collect_mode(args, out)
        return 0

    out = OutputDir.create(args.output)
    rf = {"type": args.rf_type}

    try:
        if args.mode == "config":
            client = ControllerClient(base_url=args.controller_url, token=args.token)
            run_config_mode(args, out, client, rf)
        elif args.mode == "mcp":
            run_mcp_mode(args, out, rf)
        elif args.mode == "llm":
            run_llm_mode(args, out)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\nOutput written to: {out.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())