# NTIA RAN Tester UE

This project is a security testing tool based on modifications and attacks from the User Equipment, designed to test 5G and open radio access networks (RANs) via the Uu air interface between the UE and the network. While enabling various types of testing, the primary focus of this software is on RAN security testing.  

---

This RAN tester UE (rtUE) is fully software-based and compatible with widely available, commercial off-the-shelf (COTS) software radio hardware. Standardized 3GPP or O-RAN tests, as well as custom test procedures, can be implemented and executed at minimal cost and at different stages of RAN development and integration. This system facilitates testing across multiple commercial and open-source RAN implementations with minimal technical overhead. Additionally, many attacks on the RAN can be executed automatically by the system.

---

See the our comprehensive [documentation ](https://docs.rantesterue.org) for more info on our attacks and metrics.

## Quickstart Guide

First, clone the core repository and it's submodules:

```bash
git clone https://github.com/oran-testing/ran-tester-ue && cd ran-tester-ue && git submodule update --init --recursive
```

Then pull the necessary containers from our registry:

```bash
cd ran-tester-ue/docker
sudo docker compose pull
```

Alternatively, you can build the images yourself:

```bash
sudo docker compose build
```

The environment is defined in the controller config (`ran-tester-ue/docker/controller/configs`):

This configuration tells the controller which services to run, and in what order. This allows for fully automated tests with many componenets.
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

The config used by the controller is defined in `ran-tester-ue/docker/.env` as DOCKER_CONTROLLER_INIT_CONFIG. Change this value to use a different configuration.


The following will run a jammer and UE with the requested environment, writing all data to influxdb and displaying metrics in realtime with grafana:

```bash
sudo docker compose up influxdb grafana controller
```

The grafana dashboard can be found at `http://localhost:3300`
