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

    model = AutoModelForCausalLM.from_pretrained(
        Config.options.get("model", ""),
        torch_dtype=torch.bfloat16,
        device_map="auto"
    )

    tokenizer = AutoTokenizer.from_pretrained(Config.options.get("model", ""))

    prompt = "make me a poem about a wizard"
    outputs = model.generate(**inputs, max_new_tokens=100)
    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    logging.debug(generated)

    while True:
        logging.debug("Finished...")
        time.sleep(1)
