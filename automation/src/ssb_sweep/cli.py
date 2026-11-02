"""CLI entry point for the SSB spoofer sweep automation.

Usage examples::

    # Run the sweep by talking directly to the controller REST API (no MCP).
    python -m ssb_sweep.cli --mode config

    # Run the sweep through the ran-tester-ue MCP server (docker compose run).
    python -m ssb_sweep.cli --mode mcp

    # Generate an llm_worker config (and optionally inject spec.yaml run_spec)
    # that will run the sweep via the LLM worker.
    python -m ssb_sweep.cli --mode llm --apply-spec
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from ssb_sweep.controller_client import ControllerClient
from ssb_sweep.llm_backend import LLM_RUN_SPEC_ENTRY, inject_run_spec, write_llm_config
from ssb_sweep.mcp_backend import McpBackend
from ssb_sweep.metrics import metrics_example, parse_metrics
from ssb_sweep.output import OutputDir
from ssb_sweep.spec import (
    COMPONENT_REPO,
    COMPONENT_TYPE,
    DEFAULT_BASE_CONFIG,
    build_steps,
    load_base_config,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MCP_DEBUG_FILE = "mcp_server_stderr.log"


def _post_to_controller(client: ControllerClient, cfg: dict, rf: dict) -> dict:
    res = client.start(COMPONENT_TYPE, cfg, rf, COMPONENT_REPO)
    if not res.get("ok"):
        raise RuntimeError(f"start failed: {res.get('error')}")
    return res


def run_config_mode(args: argparse.Namespace, out: OutputDir, client: ControllerClient, rf: dict):
    rows = []
    for step in build_steps(load_base_config(args.base_config)):
        out.write_step_config(step.run_id, step.config_yaml)
        res = _post_to_controller(client, step.config, rf)
        (out.step_dir(step.run_id) / "start.txt").write_text(
            "start response:\n" + str(res.get("data")) + "\n", encoding="utf-8"
        )
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

        row = metrics_example(step.index, step.run_id, step.burst_interval_us, step.periodicity_ms)
        for key, val in parse_metrics(step.run_id, logs).items():
            if key in row:
                row[key] = val
        out.write_step_metrics(step.run_id, row)
        rows.append(row)

        if not args.no_stop:
            client.stop(step.run_id)

    csv_path, json_path = out.write_metrics_table(rows)
    summary = [
        f"SSB spoofer sweep ({args.mode} mode)",
        f"steps: {len(rows)}",
        f"metrics: {csv_path}",
        f"metrics json: {json_path}",
        "note: PSS/SSS ratio, PBCH BLER, CORESET0 failure/SIB1 timeout, and",
        "time-to-camp require instrumented receiver data; recorded as None.",
    ]
    out.write_summary("\n".join(summary))


def run_mcp_mode(args: argparse.Namespace, out: OutputDir, rf: dict):
    dbg = out.root / MCP_DEBUG_FILE
    backend = McpBackend(project_dir=PROJECT_ROOT, stderr_log=dbg, use_sudo=args.sudo)

    rows = []
    for step in build_steps(load_base_config(args.base_config)):
        out.write_step_config(step.run_id, step.config_yaml)
        start_text = backend.start(step.config, rf)
        (out.step_dir(step.run_id) / "start.txt").write_text(start_text, encoding="utf-8")
        time.sleep(args.settle)

        logs = backend.logs(step.run_id)
        out.write_raw_log(step.run_id, logs)

        row = metrics_example(step.index, step.run_id, step.burst_interval_us, step.periodicity_ms)
        for key, val in parse_metrics(step.run_id, logs).items():
            if key in row:
                row[key] = val
        out.write_step_metrics(step.run_id, row)
        rows.append(row)

        if not args.no_stop:
            backend.stop(step.run_id)

    csv_path, json_path = out.write_metrics_table(rows)
    summary = [
        f"SSB spoofer sweep ({args.mode} mode via MCP)",
        f"steps: {len(rows)}",
        f"metrics: {csv_path}",
        f"metrics json: {json_path}",
        f"mcp server stderr: {out.root / MCP_DEBUG_FILE}",
    ]
    out.write_summary("\n".join(summary))


def run_llm_mode(args: argparse.Namespace, out: OutputDir):
    repo_root = PROJECT_ROOT
    cfg_path = repo_root / "configs" / "llm_worker" / "ssb_spoofer_sweep.yaml"
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
    lines += ["", "Note: the remote ghcr.io/oran-testing/llm_worker image is prebuilt;",
              "it may predate SSB spoofer support. Rebuild locally with:",
              "    docker build -f dockerfiles/Dockerfile.llm_worker -t ghcr.io/oran-testing/llm_worker ."]
    out.write_summary("\n".join(lines))
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ssb-spoofer-sweep",
        description="Run the SSB spoofer burst-interval sweep (L1/L2/L3 metrics).",
    )
    parser.add_argument("--mode", choices=["config", "mcp", "llm"], default="config",
                        help="Run strategy: direct controller API (config), MCP server (mcp), or llm_worker (llm)")
    parser.add_argument("--base-config", type=Path, default=DEFAULT_BASE_CONFIG,
                        help="Base YAML to mutate (default: configs/ssb_spoofer/srs_band3.yaml)")
    parser.add_argument("--controller-url", default="http://localhost:1343",
                        help="Controller base URL (config mode; default http://localhost:1343)")
    parser.add_argument("--token", default="default_changeme",
                        help="Controller Bearer token (default: default_changeme)")
    parser.add_argument("--rf-type", choices=["b200", "zmq", "none"], default="b200",
                        help="rf_config.type for the component (default b200)")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "output",
                        help="Output directory (a timestamped subdir is created inside)")
    parser.add_argument("--no-stop", action="store_true",
                        help="Do not stop components after each step (leave running)")
    parser.add_argument("--settle", type=float, default=5.0,
                        help="Seconds to wait after start before fetching logs (default 5.0)")
    parser.add_argument("--apply-spec", action="store_true",
                        help="llm mode: insert llm_worker run_spec into spec.yaml and set up")
    parser.add_argument("--sudo", action="store_true", default=True,
                        help="Use sudo for docker compose run (default true)")
    parser.add_argument("--no-sudo", dest="sudo", action="store_false",
                        help="Do not use sudo for docker compose run")
    args = parser.parse_args(argv)

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