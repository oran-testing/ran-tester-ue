import torch
from transformers import (
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

def verify_env():
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

    return control_ip, control_port, control_token

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
            logging.info(json.dumps(data, indent=2))
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

def stop_process(control_url, auth_header, process_id):
    current_endpoint = "/stop"
    headers = {
        "Authorization": auth_header,
        "Accept": "application/json",
        "User-Agent": "llm_worker/1.0",
        "Content-Type": "application/json",
    }

    json_payload = {
        "id": process_id
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

def get_process_logs(control_url, auth_header, json_payload):
    current_endpoint = "/logs"
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
            logging.info(json.dumps(data, indent=2))
            return True, data
        else:
            logging.error(f"Error: {response.status_code} - {response.text}")
            return False, {"error": response.text}

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to commuicate with controller: {e}")
        return False, {"error":str(e)}

    return False, {"error":"how did you get here?"}





if __name__ == '__main__':

    control_ip, control_port, control_token = verify_env()

    configure()

    model_str = Config.options.get("model", None)
    if not model_str:
        logging.error("Model not specified")
        sys.exit(1)


    # Setup control API info
    control_url = f"https://{control_ip}:{control_port}"
    auth_header = f"Bearer {control_token}"
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Configure and test model
    logging.debug(f"using model: {model_str}")
    model = AutoModelForCausalLM.from_pretrained(
        model_str,
        torch_dtype=torch.bfloat16,
        device_map="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained(model_str)
    generation_config = GenerationConfig(
        max_new_tokens=250,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=True
    )

    base_prompt = Config.options.get("base_prompt", None)
    if not base_prompt:
        raise RuntimeError(f"base prompt not provided in {Config.filename}")

    jammer_prompt = Config.options.get("jammer_prompt", None)
    if not jammer_prompt:
        raise RuntimeError(f"jammer prompt not provided in {Config.filename}")

    sniffer_prompt = Config.options.get("sniffer_prompt", None)
    if not sniffer_prompt:
        raise RuntimeError(f"sniffer prompt not provided in {Config.filename}")

    rtue_prompt = Config.options.get("rtue_prompt", None)
    if not rtue_prompt:
        raise RuntimeError(f"rtue prompt not provided in {Config.filename}")

    user_prompt = Config.options.get("user_prompt", None)
    if not user_prompt:
        raise RuntimeError(f"user prompt not provided in {Config.filename}")


    while True:
        # TODO: loop over the following steps
        # 1. get a message from the model
        # 2. verify the information and config (if fails go back to 1)
        # 3. send the message to controller endpoint
        # 4. prompt model again with message error or success
        time.sleep(1)
        all_prompt = base_prompt + jammer_prompt + sniffer_prompt + rtue_prompt + user_prompt
        prompts = [all_prompt]
        inputs = tokenizer(prompts, return_tensors="pt", padding=True, truncation=True).to(model.device)
        output_tokens = model.generate(**inputs, generation_config=generation_config)
        response_str = tokenizer.batch_decode(output_tokens, skip_special_tokens=True)
        logging.info(response_str[-1])

