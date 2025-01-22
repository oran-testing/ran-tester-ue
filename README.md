# NTIA Software Tester UE

The software tester UE is an open source security and reliability testing tool for wireless RANs.

---

This solution takes a UE based approach to RAN testing, by providing an easy to use, and well documented platform. The implementation is entirely cross platform with minimal dependencies. The system implements many attacks from recent literature, based on the 3GPP standard, taking into account the many possible avenues of exploitation.

---

See the our comprehensive [documentation ](https://docs.rantesterue.org) for more info on our attacks and metrics.

## Quickstart Guide

First, clone the core repository and it's submodules:

```bash
git clone https://github.com/oran-testing/soft-t-ue && git submodule update --init --recursive
```

Then build the necessary containers:

```bash
cd docker && docker compose build
```

The environment is defined in the controller config (soft-t-ue/docker/controller/configs):

```yaml
processes: # REQUIRED: a list of all processes to start
  - type: "srsue" # REQUIRED: the name of the subprocess class
    config_file: "configs/zmq/ue_zmq_docker.conf" # OPTIONAL: the path to a config file in the subprocess container
    args: "--rrc.sdu_fuzzed_bits 1 --rrc.fuzz_target_message 'rrcSetupRequest'" # OPTIONAL: arguments to pass to the subprocess container

  - type: "jammer"
    config_file: "configs/basic_jammer.yaml"

influxdb: # OPTIONAL: (but recommended for metrics collection) config for InfluxDB
influxdb_host: ${DOCKER_INFLUXDB_INIT_HOST} # REQUIRED: The IP or HOSTNAME of InfluxDB container
influxdb_port: ${DOCKER_INFLUXDB_INIT_PORT} # REQUIRED: The port of the InfluxDB service
influxdb_org: ${DOCKER_INFLUXDB_INIT_ORG} # REQUIRED: The org of the InfluxDB service
influxdb_token: ${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN} # REQUIRED: The admin token of the InfluxDB service

data_backup: # OPTIONAL: configure automatic data backups
backup_every: 1000 # REQUIRED: Backup data interval in seconds
backup_dir: test # OPTIONAL: directory to output data
backup_since: -1d # OPTIONAL: backup starting from
```

NOTE: The config used by the controller is defined in soft-t-ue/docker/.env as DOCKER_CONTROLLER_INIT_CONFIG

The following will run a jammer and UE with the requested environment, writing all data to influxdb and displaying metrics in realtime with grafana:

```bash
docker compose up influxdb grafana controller
```

The grafana dashboard can be found at `http://localhost:3300`
