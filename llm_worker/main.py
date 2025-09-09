"""
TODO:
- add analyzer
"""

import torch
import yaml
import logging
import os
import sys
import argparse

from config import Config

from rtue_validator import RTUEValidator
from sniffer_validator import SnifferValidator
from jammer_validator import JammerValidator
from plan_validator import PlanValidator

from executor import Executor
from planner import Planner
from api_interface import ApiInterface
from knowledge_augmentor import KnowledgeAugmentor



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

    logging.info(f"Starting LLM Worker with model: {Config.model_str}")
    executor = Executor()
    planner = Planner()
    plan_validator = PlanValidator()

    api = ApiInterface(*api_args)
    kb = KnowledgeAugmentor()

    is_successful, current_plan = planner.generate_plan()
    is_valid_plan, result = plan_validator.validate(current_plan)
    plan_attempt = 1

    while (not is_valid_plan or not is_successful) and plan_attempt <= 10:
        logging.error(f"Invalid plan (attempt {plan_attempt}) with errors: {result}")

        is_successful, current_plan = planner.generate_plan()
        if not is_successful:
            logging.error(f"Encountered errors in plan generation: {current_plan}")
            continue

        is_valid_plan, result = plan_validator.validate(current_plan)
        plan_attempt += 1

    if plan_attempt > 10:
        logging.critical("Failed to create valid plan")
        sys.exit(0)

    logging.info(f"PLAN COMPLETE: {current_plan}")


