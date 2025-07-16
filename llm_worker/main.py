import torch
from transformers import (
    AutoTokenizer, GenerationConfig,
    AutoModelForCausalLM
)
import yaml
import logging
import time
import os
import sys
from typing import List, Dict, Union, Optional, Any
import argparse
import pathlib

import requests

from validator import ResponseValidator


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
        logging.error("The LLM worker must be run as root.")
        sys.exit(1)

    if not torch.cuda.is_available():
        logging.error("Pass GPU into container!!")
        sys.exit(1)

    configure()

    control_ip = os.getenv("CONTROL_IP")
    if not control_ip:
        logging.error("variable CONTROL_IP is not set, exiting...")
        sys.exit(1)
    logging.debug(f"DOCKER_CONTROLLER_API_IP: {control_ip}")

    model_str = Config.options.get("model", None)
    if not model_str:
        logging.error("Model not specified")
        sys.exit(1)

    logging.info("="*20 + " LOADING BASE MODEL (HIGH PRECISION) " + "="*20)
    logging.info(f"Using model: {model_str}")

    model = AutoModelForCausalLM.from_pretrained(
        model_str,
        torch_dtype=torch.bfloat16,
        device_map="auto"
    )

    tokenizer = AutoTokenizer.from_pretrained(model_str)

    logging.info("="*20 + " MODEL LOADED " + "="*20)

    # TODO: explain using base prompt (from config)
    base_prompt = Config.options.get("base_prompt", None)
    if not base_prompt:
        raise RuntimeError(f"base prompt not provided in {Config.filename}")

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

    # TODO: class that verifies configuration and gets other info (endpoint, data to send, what component etc)

    validator = ResponseValidator(response_str[0])
    logging.debug("Response from model:", response_str[0])

    logging.debug(response_str)

    while True:
        # TODO: loop over the following steps
        # 1. get a message from the model
        # 2. verify the information and config (if fails go back to 1)
        # 3. send the message to controller endpoint
        # 4. prompt model again with message error or success


        try:
            logging.info("Processing LLM response...")
            logging.info("Validating configuration...")

            validated_data = validator.process_response()

            endpoint_type = validated_data.get("type")  # 'jammer' or 'sniffer'
            request_json = validated_data
            logging.info(f"Validated data: {validated_data}")

        except Exception as e:
            logging.error(f"Validation failed: {e}")
            logging.error(f"Validation errors: {validator.errors}")
            
            error_details = "; ".join(validator.errors) if validator.errors else str(e)
            next_prompt = base_prompt + f"Previous configuration was invalid: {error_details}. Please provide a corrected RF system configuration for: {current_task}"

        logging.info("Generating next response...")
        inputs = tokenizer(next_prompt, return_tensors="pt", padding=True, truncation=True).to(model.device)
        output_tokens = model.generate(**inputs, generation_config=generation_config)
        response_str = tokenizer.batch_decode(output_tokens, skip_special_tokens=True)
        
        validator = ResponseValidator(response_str[0])
        
        time.sleep(1)
    
