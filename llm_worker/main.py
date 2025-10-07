import time
import json
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
from uu_agent_validator import UuagentValidator

from llm_wrapper import LLMWrapper
from executor import Executor
from planner import Planner
from api_interface import ApiInterface
from knowledge_augmentor import KnowledgeAugmentor

from experiment_logger import ExperimentLogger 


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

    results_dir = os.getenv("RESULTS_DIR")
    if not results_dir:
        raise RuntimeError("RESULTS_DIR is not set in environment")

    Config.results_dir = os.path.join(f"/host/logs/", results_dir)
    os.makedirs(Config.results_dir, exist_ok=True)

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

def run_plan_loop(planner, plan_validator, logger=None, trial_id=None):  # <-- signature extended
    is_successful, is_valid_plan = False, False
    plan_attempt = 0

    errors = []
    while (not is_valid_plan or not is_successful) and plan_attempt <= Config.options.get("nof_plan_attempts", 10):
        raw_plan = ""
        plan_attempt += 1
        if errors:
            is_successful, raw_plan = planner.generate_plan(errors=errors)
        else:
            is_successful, raw_plan = planner.generate_plan()

        # Logger: log raw planner output
        if logger and trial_id:
            logger.log_planner_attempt(
                trial_id=trial_id,
                attempt=plan_attempt,
                input_errors=(errors or []),
                raw_output=raw_plan,
                is_successful=is_successful,
                is_valid=None,
                validator_errors=None
            )

        if not is_successful:
            logging.error(f"Encountered errors in plan generation: {raw_plan}")
            continue

        is_valid_plan, val_res = plan_validator.validate(raw_plan)

        # Logger: log planner validation result
        if logger and trial_id:
            logger.log_planner_attempt(
                trial_id=trial_id,
                attempt=plan_attempt,
                input_errors=(errors or []),
                raw_output=raw_plan,
                is_successful=True,
                is_valid=is_valid_plan,
                validator_errors=(None if is_valid_plan else val_res)
            )

        if not is_valid_plan:
            errors = val_res
            logging.info(f"PLANNER OUTPUT: {raw_plan}")
            logging.error(f"Encountered errors in plan validation: {val_res}")
            continue

        with open(os.path.join(Config.results_dir, "plan.json"), "w") as f:
            json.dump(val_res, f, indent=4)

        # Logger: log planner final success
        if logger and trial_id:
            logger.log_phase_final(trial_id, "planner", True, parsed_json=val_res)

        return val_res

    logging.critical("Failed to create valid plan")

    # Logger: log planner final failure (keeps original exit code 0)
    if logger and trial_id:
        logger.log_phase_final(trial_id, "planner", False, parsed_json=None, note="max attempts reached")

    sys.exit(0)

def run_exec_loop(executor, current_validator, plan_item, logger=None, trial_id=None):  # logger
    is_successful, is_valid_plan = False, False
    exec_attempt = 0
    errors = []
    execution_log = open(os.path.join(Config.results_dir, f"execution_log.txt"), "a")

    execution_log.write(f"Running execution loop for:\n{json.dumps(plan_item, indent=2)}")

    while (not is_valid_plan or not is_successful) and exec_attempt <= Config.options.get("nof_exec_attempts", 10):
        raw_exec = ""
        exec_attempt += 1
        if errors:
            is_successful, raw_exec = executor.execute(plan_item, errors=errors)
        else:
            is_successful, raw_exec = executor.execute(plan_item)

        # Logger: log executor raw output
        if logger and trial_id:
            logger.log_executor_attempt(
                trial_id=trial_id,
                plan_item=plan_item,
                attempt=exec_attempt,
                input_errors=(errors or []),
                raw_output=raw_exec,
                is_successful=is_successful,
                is_valid=None,
                validator_errors=None
            )

        if not is_successful:
            execution_log.write(f"\tEncountered errors in execution: {raw_exec}\n")
            continue

        is_valid_plan, val_res = current_validator.validate(raw_exec)
        if not is_valid_plan:
            errors = val_res
            execution_log.write(f"\tEncountered errors in execution validation: {val_res}\n")

        # Logger: log executor validation result
        if logger and trial_id:
            logger.log_executor_attempt(
                trial_id=trial_id,
                plan_item=plan_item,
                attempt=exec_attempt,
                input_errors=(errors or []),
                raw_output=raw_exec,
                is_successful=True,
                is_valid=is_valid_plan,
                validator_errors=(None if is_valid_plan else val_res)
            )

        if not is_valid_plan:
            continue

    if exec_attempt > Config.options.get("nof_exec_attempts", 10):
        execution_log.write(f"Failed to create valid plan\n")
        execution_log.close()

        # Logger: log executor final failure (keeps original exit code 0)
        if logger and trial_id:
            logger.log_phase_final(trial_id, "executor", False, parsed_json=None, note="max attempts reached")

        sys.exit(0)

    execution_log.write(f"Created valid exec JSON:\n{json.dumps(val_res, indent=2)}\n\n\n")
    execution_log.close()

    # Logger: log executor final success
    if logger and trial_id:
        logger.log_phase_final(trial_id, "executor", True, parsed_json=val_res)

    return val_res


if __name__ == '__main__':
    api_args = configure()

    Config.model_str = Config.options.get("model", None)
    if not Config.model_str:
        raise RuntimeError("Model not specified")

    logging.info(f"Starting LLM Worker with model: {Config.model_str}")
    llm = LLMWrapper()
    executor = Executor(llm)
    planner = Planner(llm)
    plan_validator = PlanValidator()

    api = ApiInterface(*api_args)
    kb = KnowledgeAugmentor()

    # Logger: experiment logger + per-run trial dir (no behavior change to core flow)
    logger = ExperimentLogger(Config.results_dir)
    trial_id = logger.new_trial(Config.options.get("user_prompt", ""))

    finalized_plan = run_plan_loop(planner, plan_validator, logger=logger, trial_id=trial_id)

    payload_log = open(os.path.join(Config.results_dir, "messages.txt"), "a")

    for plan_item in finalized_plan:
        api_payload = {}
        if plan_item.get("endpoint") == "start":
            component_type = plan_item.get("type")
            current_validator = None
            if component_type == "rtue":
                current_validator = RTUEValidator()
            elif component_type == "jammer":
                current_validator = JammerValidator()
            elif component_type == "sniffer":
                current_validator = SnifferValidator()
            elif component_type == "uu_agent":
                current_validator = UuagentValidator()
            api_payload = run_exec_loop(executor, current_validator, plan_item, logger=logger, trial_id=trial_id)
            if plan_item.get("rf") == "b200":
                api_payload["rf"] = {"type": "b200", "images_dir": "/usr/share/uhd/images/"}
            elif plan_item.get("rf") == "zmq":
                api_payload["rf"] = {"type": "zmq", "tcp_subnet": "172.22.0.0/24", "gateway": "172.22.0.1"}
        else:
            for key, val in plan_item.items():
                if key in ["endpoint"]:
                    continue
                api_payload[key] = val

        payload_log.write(f"Sending to endpoint {plan_item.get('endpoint')}:\n{api_payload}\n\n")
        api_successful = True
        api_res = {}
        if api_payload:
            api_successful, api_res = api.make_request(plan_item.get("endpoint"), payload=api_payload)
        else:
            api_successful, api_res = api.make_request(plan_item.get("endpoint"))

        if not api_successful:
            logging.error(f"API REQUEST FAILED: {json.dumps(api_res, indent=2)}")
            continue

        payload_log.write(f"Got result from {plan_item.get('endpoint')}:\n{api_res}\n\n")
        time.sleep(2)

    payload_log.close()
    while True:
        time.sleep(10)
