# NTIA RAN Tester UE

This project is a security testing tool based on modifications and attacks from the User Equipment, designed to test 5G and open radio access networks (RANs) via the Uu air interface between the UE and the network. While enabling various types of testing, the primary focus of this software is on RAN security testing.  

---

This RAN tester UE (rtUE) is fully software-based and compatible with widely available, commercial off-the-shelf (COTS) software radio hardware. Standardized 3GPP or O-RAN tests, as well as custom test procedures, can be implemented and executed at minimal cost and at different stages of RAN development and integration. This system facilitates testing across multiple commercial and open-source RAN implementations with minimal technical overhead. Additionally, many attacks on the RAN can be executed automatically by the system.

---

See the our comprehensive [documentation ](https://docs.rantesterue.org) for more info on our attacks and metrics.

## Quickstart Guide

***First, clone the core repository and it's submodules.***

Option A: SSH URL (Recommended if you have SSH set up)

```bash
git clone --recurse-submodules git@github.com:oran-testing/ran-tester-ue.git
```

Option B: HTTPS

```bash
git clone --recurse-submodules https://github.com/oran-testing/ran-tester-ue.git
```

***Navigate to the directory and run the system setup script:***
```bash
cd ran-tester-ue
sudo ./scripts/system_setup.sh
```

***Now, pull the necessary containers from our registry:***

```bash
sudo docker compose --profile components pull  # Pulls all attack components
sudo docker compose --profile system pull      # Pulls Grafana, InfluxDB, and Controller
```

Alternatively, you can build the images yourself:

```bash
sudo docker compose --profile components build  # Builds all attack components
sudo docker compose --profile system build      # Builds Grafana, InfluxDB, and Controller
```

The environment is defined in the controller config (`ran-tester-ue/configs`):

This configuration tells the controller which services to run, and in what order. This allows for fully automated tests with many components.
```yaml
processes:                                                # List of all processes to start
- type: "rtue"
    id: "rtue_uhd_1"
    config_file: "configs/uhd/ue_uhd.conf"                # Path to the configuration file for the rtUE
    rf:
        type: "b200"                                      # Type of RF device (= USRP B210)
        images_dir: "/usr/share/uhd/images/"              # Directory for RF images

- type: "sniffer"
    id: "dci_sniffer_1"
    config_file: "../5g-sniffer/MSU-Private5G184205.toml" # Path to the configuration file for the sniffer
    rf:
        type: "b200"
        images_dir: "/usr/share/uhd/images/"
```

The config used by the controller is defined in `ran-tester-ue/.env` as ```DOCKER_CONTROLLER_INIT_CONFIG```. Change this value to use a different configuration.


The following will run a sniffer and UE with the requested environment, writing all data to influxdb and displaying metrics in realtime with grafana:

```bash
sudo docker compose --profile system up
```

The Grafana dashboard can be accessed at [http://localhost:3300](http://localhost:3300).


## Nvidia Setup
Run the following command to setup docker to use the nvidia gpu
```bash
sudo ./scripts/nvidia_toolkit_setup.sh
```
