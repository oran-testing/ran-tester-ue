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
    logging.info("="*20 + " LOADING BASE MODEL (HIGH PRECISION) " + "="*20)
    logging.info(f"Using model: {model_str}")
    model = AutoModelForCausalLM.from_pretrained(
        model_str,
        torch_dtype=torch.bfloat16,
        device_map="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained(model_str)

    logging.info("="*20 + " MODEL LOADED " + "="*20)
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
    logging.info("Response from model:", response_str[0])

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
            else:
                logging.error(f"Error: {response.status_code} - {response.text}")

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to commuicate with controller: {e}")



