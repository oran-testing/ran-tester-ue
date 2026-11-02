# AGENTS.md — ran-tester-ue

Notes for agents working in this repo. Covers the controller, the MCP server,
`llm_worker`, configuration/setup, the three B210 USRPs, and how to clear
hardware / kill orphan containers.

> **Secret handling:** `.env` is blocked by CC Safety Net (`secret.basename.env`).
> Do not read it directly. Values below were resolved via `docker compose config`.
> Reference env var names; never paste secret values into this file or commits.

---

## 1. What this project is

NTIA RAN Tester UE (rtUE) — a UE-centric 5G RAN security testing framework.
Declarative YAML specs describe which components run; the controller builds and
launches them as Docker containers. Tested on Ubuntu 24.04 (realtime/lowlatency
kernel recommended).

Top-level layout:

| Path | Purpose |
|------|---------|
| `controller/` | The controller service (Python). Orchestrates everything. |
| `mcp_server/` | MCP server that wraps the controller HTTP API. |
| `llm_worker/` | Copy of the LLM worker used as a Docker build context. |
| `../llm_worker` | The canonical LLM worker git repo. |
| `configs/` | All component configs (rtue, sniffer, jammer, sni5gect, sstorm, ...). |
| `dockerfiles/` | Component images (`Dockerfile.rtue`, `Dockerfile.sstorm`, ...). |
| `docker-compose.yml` | controller + mcp-server + influxdb + grafana. |
| `spec.yaml` | Controller spec: auth, build_spec, run_spec. |
| `scripts/` | Setup, reset, cleanup helpers. |
| `.generated/` | Controller writes generated configs here at start time. |

---

## 2. Controller architecture

Entry point: `controller/src/main.py`.

- Requires root (`os.geteuid() == 0`).
- `configure()` parses `--config` (required) and `--log-level`; colored logging.
- Reads the YAML spec:
  - `external_targets` → registered into `Globals.target_managers` (an
    `ApiInterface` per target).
  - `api_auth` → `Globals.api_auth` (a token is auto-generated if missing).
  - `build_spec` → for each entry, `build()` if `force_rebuild`, else
    `build_if_not_exists()`.
  - `run_spec` → if `autorun` (default True), each entry is started via
    `start_external` (when `target` is set) or `start()`.
- `enable_cli: true` → starts the HTTP server thread (`0.0.0.0:1343`,
  `SystemControlHandler`) then enters `CLIManager.cli_loop()` (blocking).
  If `enable_cli` is false, it starts the server and exits 0 once
  `process_metadata` empties.

### `globals.py`
`Globals` holds class-level state: `process_metadata`, `controller_init_time`,
`thread_manager`, `api_auth`, `target_managers`, `worker_thread_registry`.

### `component_manager.py` — `ComponentManager`
- Configures InfluxDB (local via `DOCKER_INFLUXDB_INIT_HOST/PORT/ORG/ADMIN_TOKEN`,
  or an external Influx dict), creates a `docker.from_env()` client.
- Starts a `worker_thread_monitor` daemon thread (polls every 0.2s):
  - exit_code 0 → removes the entry;
  - nonzero → logs, removes, and if `exit_from_component` calls `os._exit(1)`.
- `build()`: fetches `worker_thread.py` from
  `https://raw.githubusercontent.com/{component}/{branch}/worker_thread.py`
  (`_load_worker_thread_from_url`), default image `ghcr.io/{component}`;
  `pull: true` → `_pull_image`, else git-clone to `/tmp/{repo_name}` and
  `docker buildx build`.
- `build_if_not_exists()`: builds only if the image tag is absent.
- `start(process_config)`: requires `name` + `component`; resolves `config_file`
  (joins `/host` + config_file, walks `/host` for basename, then swaps `/host`
  for `$DOCKER_SYSTEM_DIRECTORY`); handles `depends_on` and `sleep_ms`; looks up
  `Globals.worker_thread_registry[component]` for the worker class (from
  `worker_thread` field or the first class); instantiates with
  `(influxdb_client, docker_client, process_config)`, appends
  `{id,type,config,handle}` to `process_metadata`, calls `.start()`.
- `start_external()`: resolves the target from `Globals.target_managers`, POSTs
  the start request to the external controller, appends metadata.
- `stop()`: `handle.stop()` or an external stop request.
- `_load_worker_thread_from_url`: GETs the URL, writes a temp `.py`, importlib
  loads it, inspects classes (excluding `WorkerThread`/`ComponentManager` and
  foreign modules), registers them under the component path in
  `Globals.worker_thread_registry`.

### `worker_thread.py` — `WorkerThread` (base for every component)
- `RfType` enum: `NONE` / `ZMQ` / `B200`.
- `WorkerThreadConfig` carries `process_config`, `influxdb_client`,
  `docker_client`, `config_file`, `container_id`, `cli_args`, `image_name`,
  `rf_type`, `rf_config`, `container_env`, `container_volumes`,
  `container_networks`, `container_privileged=True`, `device_requests`,
  `host_network`.
- `__init__`: `rf_config = process_config["rf"]` is **required**. Maps
  `b200`/`zmq`/`none`; `zmq` requires `tcp_subnet` + `gateway` (else
  `RuntimeError`); unknown type → `RuntimeError`. `host_network` defaults False.
- `cleanup_old_containers()`: verifies the image exists (raises `RuntimeError`
  mentioning `sudo docker compose --profile components build` or `pull`), then
  force-removes any existing container with the same name. **This is the
  automatic orphan killer for a given component.**
- `setup_volumes()`: mounts `/tmp` rw; for B200 mounts `/dev/bus/usb/` rw and
  host `.uhd_images` (`$DOCKER_SYSTEM_DIRECTORY/.uhd_images`) →
  `/usr/local/share/uhd` ro; requires `usrp_b200_fw.hex` +
  `usrp_b200_fpga.bin` (else `RuntimeError` → run `scripts/system_setup.sh`).
- `setup_env()`: `ARGS` from `cli_args`, Influx vars, `UHD_IMAGES_DIR` for B200.
- `setup_networks()`: always connects `rt_metrics`; for each `api_auth` entry
  whose `pass_to` list contains the container id, connects `rt_control` and sets
  `CONTROL_TOKEN`/`HOST=controller`/`PORT=1343`; for ZMQ connects `rt_zmq`
  (created with `tcp_subnet`/`gateway` if missing).
- `start_container()`: `privileged=True`, `cap_add [SYS_NICE, SYS_PTRACE]`,
  `detach=True`, `device_requests`; `host_network` → `network_mode=host`, else
  connect the listed networks; starts `log_report_thread` and
  `container_watch_thread`.
- `start()` is abstract (each component subclass defines it).
- `stop()`: `docker_container.stop()` + `remove()`, sets `stop_thread`.
- `get_status()`: reloads attrs; returns healthy bool + `exit_code`.
- `send_message()`: writes to Influx bucket `rtusystem`, measurement
  `component_log`, tag `id` + `msg_uuid`, field `stdout_log`; also logs with a
  color derived from `md5(container_id) % 8 + 30`.
- `log_report_thread`: streams `docker_logs` lines to `send_message`, drains
  after exit. `container_watch_thread`: `docker_container.wait()`, sets
  `exit_code`.

### `control_handler.py` — `SystemControlHandler`
- `_get_permissions()`: Bearer token must match an `api_auth` token AND
  `path[1:]` must be in that API's `scopes`; returns `(valid, allowed_components)`.
- Endpoints:
  - `GET /list` → `get_components` (valid token; returns
    `{"running":[{id,type,config_file}]}`).
  - `GET /schemas/{type}` → `get_component_schema` (JSON schema from the
    converter's `REQUIRED_KEYS` + `SCHEMA`).
  - `POST /start` → `start_component` (requires `id,type,config_str,rf`;
    `rf.type` required; type must be in perms; id conflict → 409; writes
    `config_str` to `/host/.generated/{id}.{ext}` where ext = `conf` for
    rtue/sstorm, `toml` for sniffer, else `yaml`; builds
    `{config_file, name:id, component:type, rf, permissions:[]}` and calls
    `thread_manager.start`).
  - `POST /start_from_json` → `start_component_from_json` (requires
    `id,type,config_json,rf`; type must be in `CONFIG_CONVERTERS`;
    `converter.from_json` validates+converts; type in perms; id conflict; same
    `.generated` write; `component = payload.get("component", component_type)`).
  - `POST /stop` → `stop_component` (id; `handle.stop()`, delete metadata).
  - `POST /logs` → `get_component_logs` (id,type; queries Influx `rtusystem`
    `component_log` filtered by id since `controller_init_time`; returns
    `{logs:[{time,message}]}`).
  - `POST /health` → `check_component_health` (id; `handle.get_status()`).

### `config_converters.py`
- `ConfigConverter` base (`from_json`, `validate`).
- `RTUEConfigConverter`: `SECTION_MAP` maps section names to prefixes
  (`ue→ue_`, `rf→rf_`, `rat.eutra→rat_eutra_`, `rat.nr→rat_nr_`, `pcap`, `log`,
  `usim`, `rrc`, `nas`, `gui`, `gw`, `general`, `recon`).
  `REQUIRED_KEYS = [id, rf_srate, rf_tx_gain, rf_rx_gain, rat_nr_bands,
  rat_nr_nof_prb, usim_imsi, nas_apn]`. Validates gains 0-90, srate>0, prb>0,
  `usim_imsi` regex `^[0-9]{15}$`. `from_json()` → configparser INI.
- `SstormConfigConverter(RTUEConfigConverter)`: `REQUIRED_KEYS = ['id']`; SCHEMA
  adds `ue_signal_storm` bool, `ue_signal_storm_cycle_interval_ms` int.
- `SnifferConfigConverter`: `REQUIRED_KEYS = [id, file_path, sample_rate,
  frequency, nid_1, ssb_numerology]`; sample_rate>0, frequency FR1
  410e6-7125e6 or FR2 24.25e9-52.6e9, numerology 0-4, `pdcch_coreset_duration`
  in (1,2,3); `from_json` → TOML `{sniffer:{...}, pdcch:[{...}]}`.
- `Sni5gectConfigConverter`: `REQUIRED_KEYS = ['id']`; yaml.dump minus id.
- `JammerConfigConverter`: `REQUIRED_KEYS = [id, center_frequency, bandwidth,
  amplitude, sampling_freq, tx_gain, device_args]`; tx_gain 0-90, amplitude 0-1,
  bandwidth>0, sampling_freq>=2*bandwidth; yaml.
- `CONFIG_CONVERTERS = {rtue:RTUE, sniffer:Sniffer, sni5gect:Sni5gect,
  jammer:Jammer, ssb_spoofer:Sni5gect, uuagent:RTUE, sstorm:Sstorm}`.

### `api_interface.py`
`ApiInterface(control_ip, control_port, control_token)`; `make_request(endpoint,
payload)` → POST if payload else GET; headers include `Authorization: Bearer`,
`User-Agent: llm_worker/1.0`; `verify=False`; returns `(True, json)` on 200 else
`(False, {error})`.

### `cli_manager.py` — `CLIManager`
Commands: `help`, `exit`/`quit`, `list`/`ls`, `spec`/`sp`, `stop <idx|all>`,
`start <idx|all>`, `restart <idx|all>`. `handle_shutdown` stops all. Operates on
`run_spec` indices and `process_metadata`.

### `ofh_worker_thread.py`
`ofh_attacker(WorkerThread)`: image `ghcr.io/oran-testing/ofh`; mounts
`config_file` → `/attack_env/ofh.toml` ro, `CONFIG_TOML`, Traffic dir ro,
attack_results rw, `/var/tmp` ro; `ATTACKER_DIR=/attack_env`, `HOST_UID/GID`;
`host_network=True`.

---

## 3. Running things via MCP

### Server wiring
- `opencode.json` defines a local MCP server `ran-tester-ue` with command
  `["docker","compose","run","--rm","mcp-server"]`, environment `{}`. Tool names
  are prefixed `ran-tester-ue_`.
- `docker-compose.yml` service `mcp-server` builds `./mcp_server/Dockerfile`,
  container name `mcp-server`, mounts
  `${DOCKER_SYSTEM_DIRECTORY}/configs:/host/configs:ro`, env
  `CONTROLLER_URL=http://controller:1343`,
  `CONTROLLER_TOKEN=${MCP_CONTROLLER_TOKEN}`, `CONFIGS_DIR=/host/configs`,
  `LOG_LEVEL=${MCP_LOG_LEVEL:-INFO}`; network `control`; depends_on controller.
- The controller listens on `1343` (mapped `1343:1343`).
- **Token rule:** `spec.yaml` `api_auth` token MUST match `MCP_CONTROLLER_TOKEN`
  in `.env` or the MCP server gets HTTP 401 on every call. Current value is
  `default_changeme`.

### Tools (`mcp_server/tools.py`)
`get_usage_guide`, `list_components`, `start_component`, `stop_component`,
`get_component_logs` (last 50), `get_component_health`, `get_component_schema`,
`validate_config`, `list_available_configs`.

- `start_component(component_type, config_json, rf_config, component?, id?)`:
  `component_type` ∈ rtue/sniffer/sni5gect/jammer/ssb_spoofer/uuagent/sstorm;
  `rf_config` = `{type: b200|zmq|none}`; `component` is an optional repo
  override (e.g. `cueltschey/sstorm-rectest`); `id` required. It converts
  locally to fail fast, then POSTs `{id,type,config_json,rf[,component]}` to
  `/start_from_json`.
- `component_type` → repo mapping (`converter.py` `COMPONENT_REPOS`):
  rtue→`oran-testing/rtue`, sni5gect→`cueltschey/sni5gect-compact`,
  ssb_spoofer→`oran-testing/ssb-spoofer`, ra_spoof→`oran-testing/ra-spoof`,
  sstorm→`cueltschey/sstorm-rectest`.

### Resources
`component://{id}/status`, `schema://{type}`, `template://{config_name}`,
`log://{id}`.

### Typical workflow
1. `sudo docker compose up -d` (starts controller, mcp-server, influxdb, grafana).
2. Use MCP tools: `list_components` → `validate_config` → `start_component` →
   `get_component_health` / `get_component_logs` → `stop_component`.
3. `start_component` is the **only** supported way to run components here — do
   not run Docker directly.

### Verified live (this environment)
- `curl -H 'Authorization: Bearer default_changeme' http://localhost:1343/list`
  → `{"running":[{"id":"basic_zmq_signal_storm","type":"cueltschey/sstorm-rectest","config_file":"/home/charles/ran-tester-ue/configs/srsran/sstorm.conf"}]}`.
- `GET /schemas/sstorm` → JSON schema, required `["id"]`.
- `ran-tester-ue_get_usage_guide` returns the full guide.
- Running containers: `basic_zmq_signal_storm`, `ran-tester-ue-mcp-server-run-*`,
  `ran-tester-ue-controller-1`, `influxdb:2.7`.
- Networks: `rt_control` (172.20.1.0/24), `rt_metrics` (172.19.1.0/24).

---

## 4. llm_worker and run_spec

`llm_worker` is an LLM-driven planner/executor that turns a natural-language
request into component configs and drives the controller.

### Worker (`worker_thread.py`)
`class llm_worker(WorkerThread)`:
- `__init__` generates `access_token = secrets.token_urlsafe(32)`.
- `start()` requires `process_config['results_dir']` (else `sys.exit(1)`);
  image `ghcr.io/oran-testing/llm_worker`; `cleanup_old_containers()`;
  env `{CONFIG: config_file, RESULTS_DIR: results_dir,
  NVIDIA_VISIBLE_DEVICES: all, NVIDIA_DRIVER_CAPABILITIES: all}`;
  `setup_env()`; `setup_networks()`; mounts `config_file` → `/llm.yaml` ro,
  `$DOCKER_SYSTEM_DIRECTORY/.llm_worker_cache` → `/app/huggingface_cache` rw,
  `/tmp/.rt_results` → `/host/logs/` rw; `setup_volumes()`; appends
  `DeviceRequest(count=-1, capabilities=[['gpu']], driver='nvidia')`;
  `start_container()`.

### Main loop (`main.py`)
- `configure()` requires root, `torch.cuda.is_available()`, `CONTROL_TOKEN` env,
  `RESULTS_DIR` env; `Config.results_dir = /host/logs/{RESULTS_DIR}`; parses
  `--config` (required) + `--log-level`.
- Loads model from `Config.options['model']` (required). Builds `LLMWrapper`,
  `Executor`, `Planner`, `PlanValidator`, `ApiInterface('controller',1343,token)`,
  `KnowledgeAugmentor`.
- `run_plan_loop` → `finalized_plan` (JSON array of actions). For each item with
  `endpoint == 'start'`, picks a validator by type (rtue→`RTUEValidator`,
  sstorm→`SStormValidator`, jammer→`JammerValidator`,
  sniffer→`SnifferValidator`, uu_agent→`UuagentValidator`), runs `run_exec_loop`,
  then sets `rf` = `{type:b200}` or `{type:zmq, tcp_subnet:172.22.0.0/24,
  gateway:172.22.0.1}` and POSTs via `api.make_request`. Finally loops
  `while True: time.sleep(60)` to stay alive.
- `response_validation_loop`: for sniffer/jammer/rtue, up to 25 attempts;
  RL-style candidate selection (K = `LLM_K`, default 10 clamped 1-8) with
  `LLM_TEMPS`/`LLM_TOPPS`; `_compute_reward` rewards valid configs and penalizes
  changed/added keys, forbids changing `device_args`/`type`/`id`, penalizes
  out-of-range freq/srate and B200/B210 violations.
- `run_send_step` sets `rf = {type:b200, images_dir:/usr/share/uhd/images}` and
  retries `/start` up to 10 times with LLM correction on rejection.
- `save_config_to_file` writes `{config_type}_{config_id}.toml` to `/host/configs`.

### Validators
- `SnifferValidator` returns type **`sni5gect`** (not `sniffer`); hardcodes an
  Influx token and `databases/workers/uetracker/downlink_injector/exploit`
  blocks; dotted-key schema; `unflatten()` helper.
- `JammerValidator`: schema `id, center_frequency, bandwidth, amplitude,
  amplitude_width, initial_phase, sampling_freq, num_samples, output_iq_file,
  output_csv_file, write_iq, write_csv, tx_gain, device_args`; bandwidth>0,
  amplitude 0-1, tx_gain 0-90, sampling_freq>=2*bandwidth, FR1/FR2, B200/B210
  limits (≤6e9, no FR2, sampling_freq≤61.44e6, bandwidth≤56e6), num_samples>0.
- `UuagentValidator`: required `id, rf.type, rf.rx_freq, rf.srate, rf.rx_gain,
  rf.tx_gain, rf.num_samples, rf.iq_file`; rf.type uhd|zmq; gains 0-90;
  num_samples 1..10000000; iq_file must start `/output/`; returns type `uu_agent`.
- `SStormValidator`: required `id, rf_srate, rf_tx_gain, rf_rx_gain, rat_nr_bands,
  rat_nr_nof_prb, usim_imsi, nas_apn, ue_signal_storm`; uhd|zmq; gains 0-90;
  if srate near 23.04e6/30.72e6 then prb must be 106; returns type `sstorm`.

### Knowledge base
`knowledge_base/{rtue,jammer,sniffer}.md` → Chroma DB (`vector_db`,
collection `rf_knowledge`, model `all-MiniLM-L6-v2`). `build_vector.py` builds
it; `KnowledgeAugmentor.retrieve_context_for_component` filters by component.
Key facts: rtue gains 40-60/30-50, srate 1.536e7/2.304e7/3.072e7, uhd args
`type=b200`, prb 106 for 20MHz; jammer Nyquist ≥2×bw, tx_gain 0-76, B200/B210
≤6e9/≤61.44e6/≤56e6; sniffer sample_rate ≥2×bw, B210 max 61.44e6,
pdcch_coreset_duration 1/2/3, numerology 0/1/2.

### run_spec entry for llm_worker
There is **no llm_worker service in `docker-compose.yml`**. To run it, add a
`run_spec` entry (or start via MCP with `component: oran-testing/llm_worker`,
`worker_thread: llm_worker`):

```yaml
run_spec:
  - component: oran-testing/llm_worker
    worker_thread: llm_worker
    name: llm_worker
    config_file: configs/llm_worker/working_rtue.yaml
    results_dir: llm_test
    rf:
      type: none
```

Requirements: GPU (NVIDIA toolkit installed), `CONTROL_TOKEN` and `RESULTS_DIR`
env, and a config under `configs/llm_worker/` (model + prompts + user_prompt).
`configs/llm_worker/working_rtue.yaml` asks for one ZMQ rtue plus health/list;
`basic_jam.yaml` uses the KV-object plan format; `test.yaml` uses the JSON-array
action format.

### Build context
`dockerfiles/Dockerfile.llm_worker` builds with context = project root and
`COPY ../llm_worker .`. `ran-tester-ue/llm_worker` is a copy used as build
context; `../llm_worker` is the canonical git repo (has `.git`, `worker_thread.py`,
`README.md`). Several files differ between the two.

---

## 5. Configuration and setup

### `spec.yaml` (controller spec)
- `enable_cli: true`.
- `api_auth`: one entry `mcp-server`, token `default_changeme`, scopes
  (`start_from_json`, `start`, `schemas/{rtue,sniffer,jammer,sni5gect,
  ssb_spoofer,uuagent,sstorm}`, `list`, `status`, `stop`, `logs`, `health`),
  `allowed_components` = [rtue, sniffer, jammer, sni5gect, ssb_spoofer, uuagent,
  sstorm].
- `build_spec`: `cueltschey/sstorm-rectest`, branch `master`, `pull: true`.
- `run_spec`: effectively empty (`autorun: false`); a reference sstorm entry is
  present (component `cueltschey/sstorm-rectest`, worker_thread `sstorm`, name
  `basic_zmq_signal_storm`, config_file `configs/srsran/sstorm.conf`, rf b200).

### `.env` (resolved via `docker compose config`)
`DOCKER_SYSTEM_DIRECTORY=/home/charles/ran-tester-ue`,
`MCP_CONTROLLER_TOKEN=default_changeme`, `MCP_LOG_LEVEL=INFO`,
`DOCKER_INFLUXDB_INIT_ADMIN_TOKEN` (secret — reference by name),
`DOCKER_INFLUXDB_INIT_BUCKET=rtusystem`, `DOCKER_INFLUXDB_INIT_HOST=influxdb`,
`DOCKER_INFLUXDB_INIT_ORG=rtu`, `DOCKER_INFLUXDB_INIT_PORT=8086`,
`DOCKER_INFLUXDB_INIT_USERNAME=admin`, `DOCKER_INFLUXDB_INIT_PASSWORD=admin1234`,
`DOCKER_INFLUXDB_INIT_RETENTION=4d`, `DOCKER_INFLUXDB_INIT_MODE=setup`,
`DOCKER_INFLUXDB_VERSION=2.7`, `DOCKER_CONTROLLER_INIT_CONFIG=spec.yaml`,
`DOCKER_CONTROLLER_API_IP=172.20.1.7`, `DOCKER_CONTROLLER_API_PORT=443`,
`GRAFANA_PORT=3000`, `GF_AUTH_ANONYMOUS_ENABLED=true`.

### docker-compose services
- **controller**: image `ghcr.io/oran-testing/controller`, build context
  `controller`, privileged, mounts `/var/run/docker.sock`, `/tmp:/tmp`,
  `/root/.docker`, `${DOCKER_SYSTEM_DIRECTORY}:/host:rw`, `/usr/share:/usr/share:ro`;
  env `DOCKER_HOST=unix:///var/run/docker.sock`,
  `CONFIG=${DOCKER_CONTROLLER_INIT_CONFIG:-configs/basic_ue_zmq.yaml}`;
  `env_file .env`; networks `metrics` (172.19.1.7) + `control` (172.20.1.7);
  config `controller.yml`; port `1343:1343`; depends_on influxdb.
- **mcp-server**: see §3.
- **influxdb**: `influxdb:${DOCKER_INFLUXDB_VERSION}`, volume
  `influxdb-storage`, `env_file .env`, port `8086:${DOCKER_INFLUXDB_INIT_PORT}`,
  network `metrics` (172.19.1.5).
- **grafana**: `ghcr.io/oran-testing/grafana`, build context `grafana`, volume
  `grafana-storage`, `env_file .env`, port `3300:${GRAFANA_PORT}`, network
  `metrics` (172.19.1.6), depends_on influxdb.
- Networks: `rt_metrics` (172.19.1.0/24), `rt_control` (172.20.1.0/24).
- Volumes: `influxdb-storage`, `grafana-storage`.
- Top-level `configs.controller.yml` file `${DOCKER_CONTROLLER_INIT_CONFIG:-configs/multi_ue_uhd.yaml}`.

### Setup scripts
- `scripts/system_setup.sh [--no-confirm]`: sets `DOCKER_SYSTEM_DIRECTORY=<root>`
  in `.env` via sed; checks `uhd_images_downloader`; runs
  `uhd_images_downloader -i <root>/.uhd_images` (downloads USRP images).
- `scripts/nvidia_toolkit_setup.sh`: requires working `nvidia-smi`; installs
  `nvidia-container-toolkit` + `nvidia-docker2`, restarts docker.
- `scripts/nvidia_driver_setup.sh`: `ubuntu-drivers install --gpgpu`; installs
  matching `nvidia-utils`; needs reboot.

### Quickstart
```
git clone <repo>
./scripts/system_setup.sh
sudo docker compose pull        # or: sudo docker compose build
# edit spec.yaml
sudo docker compose up -d
# Grafana: http://localhost:3300
```

### Notable configs
- `configs/srsran/sstorm.conf`: `[ue] signal_storm=true`; `[rf]
  freq_offset=0, tx_gain=70, rx_gain=40, srate=23.04e6, nof_antennas=1,
  device_name=uhd, device_args='type=b200,clock=external',
  time_adv_nsamples=300`; `[rat.eutra] dl_earfcn=2850, nof_carriers=0`;
  `[rat.nr] bands=3, nof_carriers=1, max_nof_prb=106, nof_prb=106`;
  `[usim] mode=soft, algo=milenage, imsi=001010123456789`;
  `[nas] apn=srsapn`; `[gw] netns=ue1, ip_devname=tun_rtue`;
  `[gui] enable=false`.
- `configs/srsran/ue_uhd.conf`: same but `device_args='type=b200'`, log
  `all_level=info`, plus `[general] metrics_influxdb_*` (url=influxdb, port=8086,
  org=rtu, bucket=rtusystem, period_secs=0.5, ue_data_identifier=ue2_uhd).
- `configs/sni5gect/srsgnb_band3.yaml`: **empty (0 bytes)** despite being
  referenced by `configs/master.yaml` and the README.
- `configs/sni5gect/srsran-n1/n41/n78-20MHz-b210.yaml` and
  `n78-40MHz-b210.yaml`: validated band configs;
  `source_params 'type=b200,master_clock_rate=23.04e6,serial=3218CC4'` (40MHz uses
  46.08e6).
- `configs/jammer/oai_band78_jammer.yaml`: `device_args 'type=b200,serial=32BBA37'`.
- `configs/jammer/srs_band3_jammer.yaml`: `device_args 'type=b200'`.
- `configs/local_rtue.yaml`: `external_targets sni5gect_runner` (token
  `testing_token`, host `192.168.0.10`, port 1343); `run_spec` rtue
  `rtue_uhd_1` config `configs/srsran/ue_uhd.conf` rf b200.
- `configs/sstorm.yaml`: api_auth token `testing_token`; build_spec
  sni5gect-compact (main) + sstorm-rectest (master); run_spec sstorm entry.
- `configs/master.yaml`: `external_targets sni5gect_runner`; run_spec sni5gect
  `sni5gect_uhd_1` config `configs/sni5gect/srsgnb_band3.yaml` rf b200 target
  `sni5gect_runner`.

---

## 6. The three B210 USRPs

- **User states three B210 USRPs are plugged in.** This could not be verified
  from the current sandbox: `lsusb` shows no USRP (no USB passthrough) and
  `uhd_find_devices` is not installed on the host. `/dev/bus/usb` has buses
  `001` and `002`.
- On the host, verify with UHD utilities: `uhd_find_devices`, `uhd_usrp_probe`.
- B200/B210 limits enforced by the framework: max sample rate **61.44 Msps**,
  gain **0-90 dB**, no FR2, bandwidth ≤ 56 MHz, center frequency ≤ 6 GHz.
- B200/B210 containers bind-mount `/dev/bus/usb/` and need UHD images at
  `$DOCKER_SYSTEM_DIRECTORY/.uhd_images` (`usrp_b200_fw.hex`,
  `usrp_b200_fpga.bin`) — installed by `scripts/system_setup.sh`.
- `device_args` examples: `type=b200`, `type=b200,clock=external`,
  `type=b200,serial=3218CC4`, `type=b200,serial=32BBA37`. Distinct serials
  disambiguate multiple USRPs.
- With three USRPs, assign each component a distinct `serial` in `device_args`
  so they don't contend for the same device.

---

## 7. Clearing USRPs and killing orphan containers

### Freeing a USRP
A USRP is "held" by whichever container bind-mounts `/dev/bus/usb/`
(rtue/sstorm/jammer/sniffer/uuagent). Free it by stopping/removing that
container:

```
# via MCP
ran-tester-ue_stop_component(id="<component id>")

# or directly
docker ps -a
docker stop <container>
docker rm <container>
```

Verify the device is free with `uhd_find_devices` / `uhd_usrp_probe`.

### Scripts
- `scripts/rtu_reset.sh` (root): finds containers named `rtue`, or with ancestor
  `rtu/jammer`, `rtu/uuagent`; `docker kill` + `docker rm`. This is the closest
  thing to a UE/jammer/uuagent reset.
- `scripts/purge_docker.sh` (root, confirms): `docker stop`/`rm` all containers,
  `rmi` all images, `volume rm` all, `system prune -a --volumes -f`,
  `builder prune -a -f`, `network prune -f`. **Full wipe.**
- `scripts/cleanup_virtual.sh` / `setup_virtual.sh` / `ip_route.sh`: manage the
  `vru0<->vgnb0` veth pair (192.168.1.1/24, 192.168.1.2/24, MTU 9000) for virtual
  gNB/RU testing; `ip_route.sh` adds route `10.53.0.0/16` and runs `iperf3` in
  rtue containers.
- `scripts/clear_influxdb.sh` (root): sources `../.env`; deletes Influx data from
  7 days ago to now from bucket `DOCKER_INFLUXDB_INIT_BUCKET` via
  `docker exec -it <influxdb:2.7 container> influx delete ...`.
- `scripts/backup_data.sh <since> <outfile>` (root): sources `.env`;
  `docker exec influx query` to `/tmp/host/<outfile>`.
- `scripts/push_prach_cfg.sh` (root): writes `prach_cfg` line protocol to Influx.
- No dedicated USRP reset script exists.

### Automatic orphan handling
- `WorkerThread.cleanup_old_containers()` force-removes any existing container
  with the same name before starting a new one — so re-running a component id
  clears its predecessor automatically.
- The controller's `worker_thread_monitor` removes entries when a container
  exits; on a nonzero exit it may `os._exit(1)`.

### Manual orphan sweep
```
docker ps -a --format '{{.ID}}\t{{.Names}}\t{{.Status}}'
docker stop $(docker ps -aq)      # stop all
docker rm $(docker ps -aq)        # remove all
docker container prune -f         # remove stopped
docker network prune -f           # remove unused networks
```

---

## 8. Gotchas / rules

- Token mismatch between `spec.yaml` and `MCP_CONTROLLER_TOKEN` → HTTP 401 on
  every MCP call.
- Never guess ARFCN/band combos; use the validated band configs in `configs/`
  (bands 3, 41, 78, n1).
- Never modify `.env`, `opencode.json`, `docker-compose.yml`, or `spec.yaml`
  unless the user asks.
- Always validate before starting; always use the MCP server, never Docker
  directly.
- `configs/sni5gect/srsgnb_band3.yaml` is empty — do not use it as-is.
- The controller requires root and Docker socket access.
- Do not embed the Influx admin token; reference `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN`.

---

## 9. Automation (`automation/`) — SSB spoofer sweep

`automation/` is a **uv-managed** Python 3.11+ project that runs security tests
automatically. The first test sweeps **oran-testing/ssb-spoofer** through
`attack.burst_interval_us` values. See `automation/README.md` (full docs) and
`automation/src/ssb_sweep/`.

### Layout
- `automation/pyproject.toml` — PEP 621 `[project]` with
  `dependencies = ["requests>=2.31.0", "PyYAML>=6.0", "mcp>=1.0.0,<2.0.0"]`
  (dependencies MUST be an array under `[project]`, not `[dependencies]`); build
  system `uv_build`; console script `ssb-spoofer-sweep = ssb_sweep.cli:main`.
  Package lives under `src/ssb_sweep/` (uv_build infers module from project name).
- `src/ssb_sweep/spec.py` — `SWEEP_STEPS_US = [(19000,'20ms'),(9000,'10ms'),
  (4000,'5ms'),(2000,'3ms')]`, `COMPONENT_TYPE='ssb_spoofer'`,
  `COMPONENT_REPO='oran-testing/ssb-spoofer'`, `WORKER_THREAD='ssb_spoofer'`,
  `FIXED_TX_GAIN_DB=60.0`, `BURST_LENGTH_MS=1`,
  `DEFAULT_BASE_CONFIG = REPO_ROOT/configs/ssb_spoofer/srs_band3.yaml`
  (`REPO_ROOT = Path(__file__).resolve().parents[3]`). `build_steps()` builds
  `SweepStep` dataclasses; component ids are `ssb_spoofer_sweep_<idx>_<us>us`.
- `src/ssb_sweep/controller_client.py` — direct HTTP backend
  (`ControllerClient(base_url, token='default_changeme')`, Bearer auth,
  `start()` → POST `/start_from_json` with
  `{id,type,config_json,rf,component?}`; `list_components`/`stop`/`health`).
- `src/ssb_sweep/mcp_backend.py` — `McpBackend(project_dir, use_sudo=True)`
  spawns `[sudo] docker compose run --rm mcp-server` and drives it via the MCP
  stdio SDK (`StdioServerParameters` + `stdio_client` + `ClientSession`). Tool
  args mirror `mcp_server/tools.py`: `start(config,rf)` →
  `{component_type, config_json, rf_config, component}`; `stop(run_id)` →
  `{component_id}`; `logs(run_id)` → `{component_id, component_type}`.
- `src/ssb_sweep/llm_backend.py` — `build_llm_config()` produces the llm_worker
  YAML (model default `deepseek-ai/DeepSeek-Coder-6.7B-Instruct`,
  `results_dir: ssb_spoofer_sweep_logs`, planners/executors/`ssb_spoofer`
  prompt block, `user_prompt` embedding the sweep);
  `write_llm_config(path)`; `inject_run_spec(spec_path, apply=...)` appends a
  run_spec entry (dedup by name) and, if `apply`, backs up to
  `spec.yaml.bak_<ts>` and writes; else returns operator instructions.
- `src/ssb_sweep/metrics.py` — `FAILURE_SIGNATURES =
  ('CELL_BARRED_DETECTED','MIB_CRC_ERR','CORESET0_OUT_OF_BOUNDS')`; regex
  counters + `parse_metrics()` (attach_denial_pct computed from
  attach-denied ÷ attach-attempts; L1/L2/L3 fields like
  `pss_sss_correlation_peak_ratio`, `pbch_block_error_rate`,
  `coreset0_blind_decode_failure_rate`, `sib1_decode_timeout_count`,
  `time_to_camp_ms` are `None` placeholders needing instrumented data).
- `src/ssb_sweep/output.py` — `output/<YYYYmmdd_HHMMSS>/` with per-step dirs
  `step_<idx>_<us>us_<ms>ms/` (`config.yaml`, `start.txt`, `raw.log`,
  `metrics.json`), plus `metrics.csv`/`metrics.json` table and `summary.jsonl`.
- `src/ssb_sweep/cli.py` — argparse entry `main(argv)`,
  `PROJECT_ROOT = Path(__file__).resolve().parents[2]`; prog name
  `ssb-spoofer-sweep`.

### CLI
```
uv sync                                   # in automation/
uv run python3 -m ssb_sweep.cli --help
uv run python3 -m ssb_sweep.cli --mode config   # direct HTTP
uv run python3 -m ssb_sweep.cli --mode mcp      # via MCP stdio client
uv run python3 -m ssb_sweep.cli --mode llm --apply-spec
```
Args: `--mode {config,mcp,llm}` (default config), `--base-config`,
`--controller-url` (default `http://localhost:1343`), `--token` (default
`default_changeme`), `--rf-type {b200,zmq,none}` (default b200), `--output`,
`--no-stop`, `--apply-spec`, `--sudo`/`--no-sudo`.

### Sweep semantics
`attack.burst_interval_us` ∈ [19000, 9000, 4000, 2000] with
`burst_length_ms = 1` → effective periodicities 20/10/5/3 ms
(= burst_length_ms + burst_interval_us/1000). Fixed per step:
`rf.tx_gain_db = 60.0`, `attack.modify_cell_barred = true`,
`attack.modify_coreset0_idx = true`, `attack.modify_ss0_idx = true`.

### llm_worker changes for ssb_spoofer
- `llm_worker/ssb_spoofer_validator.py` (created in **both** the `ran-tester-ue`
  copy and the parent `../llm_worker`): `SSBSpooferValidator(Validator)`, own
  `_extract_json` override (base class `_extract_json` is new-style/no-arg and
  subclass overriding is required), validates `rf`/`ssb`/`attack`/`operation`
  sections + B210 limits (`srate_hz ≤ 61.44e6`, gains 0-90, `freq_hz ≤ 6e9`),
  converts to YAML (dumps config minus `id`), returns
  `{'id', 'type':'ssb_spoofer', 'config_str'}`.
- `main.py` (both copies): added
  `from ssb_spoofer_validator import SSBSpooferValidator` and
  `elif component_type == "ssb_spoofer": current_validator = SSBSpooferValidator()`
  in the `__main__` start dispatch.
- **The runtime image `ghcr.io/oran-testing/llm_worker` is prebuilt and predates
  this.** Rebuild locally for llm mode:
  `docker build -f dockerfiles/Dockerfile.llm_worker -t ghcr.io/oran-testing/llm_worker .`
- Static llm config template: `configs/llm_worker/ssb_spoofer_sweep.yaml`
  (must stay in sync with `llm_backend.build_llm_config()`).

### Known constraint
The **live controller's `build_spec` only registers `cueltschey/sstorm-rectest`**,
so an `ssb_spoofer` start currently fails until the controller spec also
registers `oran-testing/ssb-spoofer` (see `configs/ssb-spoofer.yaml` for a
reference with a full ssb-spoofer + victim-UE run_spec). Do not point a live
ssb_spoofer start at this controller until that is configured.
