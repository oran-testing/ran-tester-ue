"""
TODO:
- make planner class
- make validator class
- make validator for planner
- allow another LLM to be used for the planner
- add analyzer
"""

import torch
import yaml
import json
import logging
import os
import sys
import argparse
import pathlib

from config import Config

from rtue_validator import RTUEValidator
from sniffer_validator import SnifferValidator
from jammer_validator import JammerValidator



def configure():
    if os.geteuid() != 0:
        raise RuntimeError("The LLM worker must be run as root.")
    if not torch.cuda.is_available():
        raise RuntimeError("No available GPU in the LLM container")
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

    parser = argparse.ArgumentParser(
        description="RAN tester UE process controller")
    parser.add_argument(
        "--config", type=str, required=True,
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
    if not os.path.exists(args.config):
        raise RuntimeError(f"Config path {args.config} does not exist")

    with open(str(args.config), 'r') as file:
        Config.options = yaml.safe_load(file)

    return control_ip, control_port, control_token



if __name__ == '__main__':
    api_args = configure()

    Config.model_str = Config.options.get("model", None)
    if not Config.model_str:
        raise RuntimeError("Model not specified")

    logging.debug(f"Starting LLM Worker with model: {Config.model_str}")

    executor = Executor()
    planner = Planner()

    api = ApiInterface(*api_args)
    kb = KnowledgeAugmentor()




