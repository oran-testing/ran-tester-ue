# ran-tester automation — SSB spoofer sweep

`automation/` is a `uv`-managed Python 3.11+ project that runs RAN security tests
automatically. The first test drives **oran-testing/ssb-spoofer** through a sweep
of `attack.burst_interval_us` values, using one of three backends.

## Quick start

```sh
cd automation
uv sync                 # create .venv and install deps (requests, PyYAML, mcp)
uv run python3 -m ssb_sweep.cli --help
```

The console script is also available after `uv sync`:

```sh
uv run ssb-spoofer-sweep --mode config
# or build a wheel:  uv build
```

## Modes

| Mode | How components are started | Needs |
|------|---------------------------|-------|
| `config` (default) | Direct HTTP POST to the controller `/start_from_json` API | Controller running, `--token` |
| `mcp` | Spawns the MCP server (`docker compose run --rm mcp-server`) and drives it via the MCP stdio SDK | Docker daemon, controller running, `sudo` (or `--no-sudo`) |
| `llm` | Generates an llm_worker config + run_spec entry; prints/apply instructions and monitors `/list` | GPU + NVIDIA toolkit + rebuilt `ghcr.io/oran-testing/llm_worker` image |

Run an entire sweep:

```sh
uv run python3 -m ssb_sweep.cli --mode config
uv run python3 -m ssb_sweep.cli --mode mcp
uv run python3 -m ssb_sweep.cli --mode llm --apply-spec
```

## CLI arguments

```
--mode {config,mcp,llm}          run strategy (default: config)
--base-config PATH               base ssb_spoofer YAML (default:
                                 configs/ssb_spoofer/srs_band3.yaml)
--controller-url URL             controller base (default: http://localhost:1343)
--token TOKEN                    controller Bearer token (default: default_changeme)
--rf-type {b200,zmq,none}        RF type sent in rf_config (default: b200)
--output DIR                     output root (default: <repo>/output)
--no-stop                        leave components running after each step
--apply-spec                     (llm mode) apply run_spec entry to spec.yaml
                                (backs up spec.yaml first)
--sudo / --no-sudo               (mcp mode) prefix docker with sudo (default: sudo)
```

## Sweep spec

Sweeps `attack.burst_interval_us` over `[19000, 9000, 4000, 2000]` with
`attack.burst_length_ms = 1`, effective periodicities **20 / 10 / 5 / 3 ms**
(periodicity = burst_length_ms + burst_interval_us/1000).

Fixed per step: `rf.tx_gain_db = 60.0`, `attack.modify_cell_barred = true`,
`attack.modify_coreset0_idx = true`, `attack.modify_ss0_idx = true`.

Component ids: `ssb_spoofer_sweep_1_19000us`, ..., `ssb_spoofer_sweep_4_2000us`.

## Output layout

```
output/<YYYYmmdd_HHMMSS>/
  step_1_19000us_20ms/
    config.yaml          # mutated per-step config used to start
    start.txt            # start API/MCP response
    raw.log              # controller logs for the run
    metrics.json         # parsed metrics for this step
  ...
  metrics.csv            # one row per step (all metric fields)
  metrics.json
  summary.jsonl          # per-step summary lines
```

For `llm` mode the llm_worker config is written to
`configs/llm_worker/ssb_spoofer_sweep.yaml` and the run_spec entry + instructions
are printed (applied only with `--apply-spec`, which backs up `spec.yaml` first).

## Metrics

`ssb_sweep/metrics.py` derives these from component logs:

- **Log-counted (reliable):** `CELL_BARRED_DETECTED`, `MIB_CRC_ERR`,
  `CORESET0_OUT_OF_BOUNDS` (signature counts), plus attach attempt / denied
  counts used to compute `attach_denial_pct`.
- **Placeholders (`null`):** L1 `pss_sss_peak_ratio`, `pbch_block_error_rate`;
  L2 `coreset0_blind_decode_failure_rate`, `sib1_decode_timeout_count`;
  L3 `time_to_camp_ms`. These need instrumented gNB/UE data (e.g. rtue metrics
  in InfluxDB) and are recorded in the CSV as `None` with a `parse_note`.

## Prerequisite notes

- **Controller build_spec:** the live controller currently registers only
  `cueltschey/sstorm-rectest`. Starting an `ssb_spoofer` component fails until
  the controller's `build_spec` also registers `oran-testing/ssb-spoofer`
  (see `configs/ssb-spoofer.yaml`, which has the full ssb-spoofer + victim-UE
  run_spec).
- **llm mode image:** `ghcr.io/oran-testing/llm_worker` is prebuilt and predates
  ssb-spoofer support. Rebuild locally to enable it:

  ```sh
  docker build -f dockerfiles/Dockerfile.llm_worker -t ghcr.io/oran-testing/llm_worker .
  ```

- **MCP mode:** the spawned `mcp-server` container talks to `controller` on the
  compose `control` network, so the controller must be up (`sudo docker compose up -d`).