import torch from transformers import (
    AutoTokenizer, GenerationConfig,
    AutoModelForCausalLM
)
import urllib3
import yaml
import json
import logging
import time
import os
import sys
from typing import List, Dict, Union, Optional, Any
import argparse
import pathlib

import requests

#from validator import ResponseValidator


class Config:
    filename : str = ""
    options : Optional[Dict[str,Any]] = None
    log_level : int = logging.DEBUG

def configure() -> None:
    """
    Reads in CLI arguments
    Parses YAML config
    Configures logging
    """
    parser = argparse.ArgumentParser(
        description="RAN tester UE process controller")
    parser.add_argument(
        "--config", type=pathlib.Path, required=True,
        help="Path of YAML config for the llm worker")
    parser.add_argument("--log-level",
                    default="DEBUG",
                    help="Set the logging level. Options: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    args = parser.parse_args()
    Config.log_level = getattr(logging, args.log_level.upper(), 1)

    if not isinstance(Config.log_level, int):
        raise ValueError(f"Invalid log level: {args.log_level}")

    logging.basicConfig(level=Config.log_level,
                    format='%(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

    Config.filename = args.config
    with open(str(args.config), 'r') as file:
        Config.options = yaml.safe_load(file)

def list_processes(control_url, auth_header):
    current_endpoint = "/list"
    headers = {
        "Authorization": auth_header,
        "Accept": "application/json",
        "User-Agent": "llm_worker/1.0",
    }

    try:
        response = requests.get(
            url=f"{control_url}{current_endpoint}",
            headers=headers,
            verify=False
        )
        if response.status_code == 200:
            data = response.json()
            logging.debug(json.dumps(data, indent=2))
            return True, data
        else:
            logging.error(f"Error: {response.status_code} - {response.text}")
            return False, {"error": response.text}

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to commuicate with controller: {e}")
        return False, {"error":str(e)}

    return False, {"error":"how did you get here?"}

def start_process(control_url, auth_header, json_payload):
    current_endpoint = "/start"
    headers = {
        "Authorization": auth_header,
        "Accept": "application/json",
        "User-Agent": "llm_worker/1.0",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url=f"{control_url}{current_endpoint}",
            headers=headers,
            json=json_payload,
            verify=False
        )
        if response.status_code == 200:
            data = response.json()
            logging.debug(json.dumps(data, indent=2))
            return True, data
        else:
            logging.error(f"Error: {response.status_code} - {response.text}")
            return False, {"error": response.text}

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to commuicate with controller: {e}")
        return False, {"error":str(e)}

    return False, {"error":"how did you get here?"}





if __name__ == '__main__':

    if os.geteuid() != 0:
        raise RuntimeError("The LLM worker must be run as root.")

    if not torch.cuda.is_available():
        raise RuntimeError("GPU is not passed into container!!!")

    control_ip = os.getenv("CONTROL_IP")
    if not control_ip:
        raise RuntimeError("CONTROL_IP is not set in environment")

    control_token = os.getenv("CONTROL_TOKEN")
    if not control_token:
        raise RuntimeError("CONTROL_TOKEN is not set in environment")

    control_port = os.getenv("CONTROL_PORT")
    if not control_port:
        raise RuntimeError("CONTROL_PORT is not set in environment")

    try:
        control_port = int(control_port)
    except RuntimeError:
        raise RuntimeError("control port is not an integer")

    configure()

    model_str = Config.options.get("model", None)
    if not model_str:
        logging.error("Model not specified")
        sys.exit(1)

    base_prompt = Config.options.get("base_prompt", None)
    if not base_prompt:
        raise RuntimeError(f"base prompt not provided in {Config.filename}")


    # Configure and test model
    logging.debug("="*20 + " LOADING BASE MODEL (HIGH PRECISION) " + "="*20)
    logging.debug(f"Using model: {model_str}")
    model = AutoModelForCausalLM.from_pretrained(
        model_str,
        torch_dtype=torch.bfloat16,
        device_map="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained(model_str)

    logging.debug("="*20 + " MODEL LOADED " + "="*20)
    generation_config = GenerationConfig(
        max_new_tokens=250,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=True
    )
    logging.debug("="*20 + " EXECUTING PROMPT " + "="*20)

    current_task = "Jam the network at 1.5 GHz"
    prompts = base_prompt + current_task
    inputs = tokenizer(prompts, return_tensors="pt", padding=True, truncation=True).to(model.device)
    output_tokens = model.generate(**inputs, generation_config=generation_config)
    response_str = tokenizer.batch_decode(output_tokens, skip_special_tokens=True)
    logging.info(f"Response from model: {response_str}")

    # Setup control API info
    control_url = f"https://{control_ip}:{control_port}"
    auth_header = f"Bearer {control_token}"

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


    while True:
        # TODO: loop over the following steps
        # 1. get a message from the model
        # 2. verify the information and config (if fails go back to 1)
        # 3. send the message to controller endpoint
        # 4. prompt model again with message error or success

        list_processes(control_url, auth_header)
        time.sleep(1)
        json_payload = {
            "id": "rtue_uhd_1",
            "type": "rtue",
            "config_str": """
[rf]
freq_offset = 0
tx_gain = 50
rx_gain = 40
srate = 23.04e6
nof_antennas = 1

device_name = uhd
device_args = clock=internal
time_adv_nsamples = 300

[rat.eutra]
dl_earfcn = 2850
nof_carriers = 0

[rat.nr]
bands = 3
nof_carriers = 1
max_nof_prb = 106
nof_prb = 106

[pcap]
enable = none
mac_filename = /tmp/ue_mac.pcap
mac_nr_filename = /tmp/ue_mac_nr.pcap
nas_filename = /tmp/ue_nas.pcap

[log]
all_level = info
phy_lib_level = none
all_hex_limit = 32
filename = /tmp/ue.log
file_max_size = -1

[usim]
mode = soft
algo = milenage
opc  = 63BFA50EE6523365FF14C1F45F88737D
k    = 00112233445566778899aabbccddeeff
imsi = 001010123456780
imei = 353490069873319

[rrc]
release = 15
ue_category = 4

[nas]
apn = srsapn
apn_protocol = ipv4

[gw]
#netns = ue1
#ip_devname = tun_srsue
#ip_netmask = 255.255.255.0

[gui]
enable = false
            """,
            "rf": {
                "type": "b200",
                "images_dir": "/usr/share/uhd/images/",
            }
        }
        start_process(control_url, auth_header, json_payload)
        list_processes(control_url, auth_header)
        time.sleep(1)

        json_payload = {
            "id": "jammer_uhd_1",
            "type": "jammer",
            "config_str": """
amplitude: 0.7
amplitude_width: 0.05
center_frequency: 1.842e9
bandwidth: 80e6
initial_phase: 0
sampling_freq: 40e6
num_samples: 20000
output_iq_file: "output.fc32"
output_csv_file: "output.csv"
write_iq: false
write_csv: true
device_args: "type=b200"
tx_gain: 70
            """,
            "rf": {
                "type": "b200",
                "images_dir": "/usr/share/uhd/images/",
            }
        }

        start_process(control_url, auth_header, json_payload)
        list_processes(control_url, auth_header)
        time.sleep(1)

        json_payload = {
            "id": "sniffer_uhd_1",
            "type": "sniffer",
            "config_str": """
[sniffer]
file_path = "/home/oran-testbed/5g-sniffer/iq_1842MHz_pdcch_traffic.fc32"
sample_rate = 23040000
frequency = 1842500000
nid_1 = 1
ssb_numerology = 0
#rf_args = "type=b200,master_clock_rate=23.04e6"


[[pdcch]]
coreset_id = 1
subcarrier_offset = 426
num_prbs = 30
numerology = 0
dci_sizes_list = [41]
scrambling_id_start = 1
scrambling_id_end = 10
rnti_start = 17921
rnti_end = 17930
interleaving_pattern = "non-interleaved"
coreset_duration = 1
AL_corr_thresholds = [1, 0.5, 0.5, 1, 1]
num_candidates_per_AL = [0, 4, 4, 0, 0]
            """,
            "rf": {
                "type": "b200",
                "images_dir": "/usr/share/uhd/images/",
            }
        }


        start_process(control_url, auth_header, json_payload)
        list_processes(control_url, auth_header)
        time.sleep(10000)








