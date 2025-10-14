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

def run_plan_loop(planner, plan_validator):
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
        if not is_successful:
            logging.error(f"Encountered errors in plan generation: {raw_plan}")
            continue

        is_valid_plan, val_res = plan_validator.validate(raw_plan)
        if not is_valid_plan:
            errors = val_res
            logging.error(f"Encountered errors in plan validation: {val_res}")
            continue

        with open(os.path.join(Config.results_dir, "plan.json"), "w") as f:
            json.dump(val_res, f, indent=4)
        return val_res

    logging.critical("Failed to create valid plan")
    sys.exit(0)


def run_exec_loop(executor, current_validator, plan_item):
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

        if not is_successful:
            execution_log.write(f"\tEncountered errors in execution: {raw_exec}\n")
            continue

        is_valid_plan, val_res = current_validator.validate(raw_exec)
        if not is_valid_plan:
            errors = val_res
            execution_log.write(f"\tEncountered errors in execution validation: {val_res}\n")
            continue

    if exec_attempt > Config.options.get("nof_exec_attempts", 10):
        execution_log.write(f"Failed to create valid plan\n")
        execution_log.close()
        sys.exit(0)

    execution_log.write(f"Created valid exec JSON:\n{json.dumps(val_res, indent=2)}\n\n\n")
    execution_log.close()
    return val_res




# ----- Modular step handlers (prefix-based) -----

GENERATED_RAW: Dict[str, str] = {}
PROMPTS_BY_COMP: Dict[str, str] = {}
VALIDATED_BY_COMP: Dict[str, dict] = {}

PLAN_KEY_RE = re.compile(r"^(rtue|sniffer|jammer)_([a-z0-9_]+)$")


def derive_component_params(plan_obj: dict) -> Dict[str, Dict[str, Any]]:
    # Converts flat planner keys into per-component parameter maps.
    comp_params: Dict[str, Dict[str, Any]] = {}
    if not isinstance(plan_obj, dict):
        return comp_params
    for k, v in plan_obj.items():
        m = PLAN_KEY_RE.match(k)
        if not m:
            continue
        comp, param = m.group(1), m.group(2)
        comp_params.setdefault(comp, {})[param] = v
    return comp_params


def derive_steps_from_components(comp_params: Dict[str, Dict[str, Any]]) -> List[str]:
    # Stable execution order.
    priority = ["rtue", "sniffer", "jammer"]
    steps: List[str] = []
    for comp in priority:
        if comp in comp_params:
            steps += [f"generate_{comp}", f"validate_{comp}", f"send_{comp}"]
    return steps


def run_generate_step(component: str, kb: KnowledgeAugmentor, extra_params: Optional[Dict[str, Any]] = None):
    logging.info(f"Plan component: {component}")
    user_prompt = Config.options.get("user_prompt", "")
    system_prompt = Config.options.get(component, "")
    original_prompt_content = system_prompt + user_prompt

    system_instructions = system_prompt.split("### USER REQUEST:")[0] if "### USER REQUEST:" in system_prompt else system_prompt
    retrieval_query = f"Rules, constraints, and known-good examples for a '{component}' configuration to fulfill: {user_prompt}"
    if extra_params:
        retrieval_query += f" with planner parameters: {json.dumps(extra_params)}"
    retrieved_context = kb.retrieve_context_for_component(component, retrieval_query)

    prompt_to_use = KnowledgeAugmentor.build_augmented_prompt(
        context=retrieved_context,
        system_prompt_block=system_instructions,
        user_request=user_prompt,
        planner_params=extra_params or {}
    )

    logging.info("=" * 20 + " EXECUTING PROMPT " + "=" * 20)
    current_response_text = generate_response(model, tokenizer, False, prompt_to_use)
    logging.info("=" * 20 + " MODEL GENERATED OUTPUT " + "=" * 20)
    logging.info(f"'{current_response_text}'")
    logging.info("=" * 20 + " END OF MODEL OUTPUT " + "=" * 20)

    GENERATED_RAW[component] = current_response_text
    PROMPTS_BY_COMP[component] = original_prompt_content


def run_validate_step(component: str):
    if component not in GENERATED_RAW:
        logging.error(f"No generated output available for '{component}'. Skipping validation.")
        return
    original_prompt_content = PROMPTS_BY_COMP.get(component, "")
    current_response_text = GENERATED_RAW[component]

    validated_data = response_validation_loop(current_response_text, component, original_prompt_content)
    if validated_data is None:
        logging.error(f"Validation failed for {component}.")
        return

    final_config_type = validated_data.get('type')
    final_config_id = validated_data.get('id')
    final_config_string = validated_data.get('config_str')

    save_config_to_file(final_config_string, final_config_type, final_config_id)

    if validated_data and validated_data.get('config_str'):
        logging.info("=" * 20 + " FINAL VALIDATED CONFIGURATION " + "=" * 20)
        VALIDATED_BY_COMP[component] = validated_data
    else:
        logging.error("=" * 20 + " SCRIPT FAILED " + "=" * 20)
        logging.error(f"Could not obtain a valid and non-empty '{component}' configuration after all attempts.")


def run_send_step(component: str, control_url: str, auth_header: str):
    if component not in VALIDATED_BY_COMP:
        logging.error(f"No validated config for {component}, cannot send.")
        return

    validated_data = VALIDATED_BY_COMP[component]
    controller_retry_max_attempts = 10
    controller_attempt_count = 1

    while controller_attempt_count <= controller_retry_max_attempts:
        final_config_type = validated_data.get('type')
        final_config_id = validated_data.get('id')
        final_config_string = validated_data.get('config_str')

        logging.info("--- PREPARING TO SEND PAYLOAD ---")
        logging.info(f"Value of final_config_id: {final_config_id} (Type: {type(final_config_id)})")
        logging.info(f"Value of final_config_type: {final_config_type} (Type: {type(final_config_type)})")
        logging.info(f"Length of final_config_string: {len(final_config_string.strip())}")
        logging.info(f"--- END OF PAYLOAD PREP ---")

        json_payload = {"id": final_config_id, "type": final_config_type, "config_str": final_config_string}
        logging.info(f"Attempting to start process with controller (Attempt {controller_attempt_count}/{controller_retry_max_attempts})...")
        logging.info(f"Payload being sent: {json.dumps(json_payload, indent=2)}")
        json_payload["rf"] = {"type": "b200", "images_dir": "/usr/share/uhd/images"}

        success, response_data = start_process(control_url, auth_header, json_payload)

        if success:
            logging.info("Successfully sent start command to controller.")
            logging.info(f"Controller response: {response_data}")
            logging.info("Script finished successfully.")
            break

        logging.error("Failed to start process via controller.")
        controller_error_details = response_data.get("error", "No error details from controller.")
        logging.error(f"Controller error: {controller_error_details}")

        controller_attempt_count += 1
        if controller_attempt_count > controller_retry_max_attempts:
            logging.critical("Maximum controller retry attempts reached. Aborting script.")
            sys.exit(1)

        logging.warning("Attempting to generate a new configuration based on controller feedback.")

        original_prompt_content = PROMPTS_BY_COMP.get(component, "")
        controller_correction_prompt = (
            f"The configuration you provided was syntactically valid, but the system controller REJECTED it for the following reason:\n"
            f"{controller_error_details}\n\n"
            f"This implies a logical or semantic error (e.g., an invalid parameter value, a resource conflict). "
            f"Please analyze this feedback and regenerate the entire, corrected JSON object based on the original request.\n"
            f"--- ORIGINAL REQUEST ---\n{original_prompt_content}"
        )

        current_response_text = generate_response(model, tokenizer, False, controller_correction_prompt)

        logging.info("=" * 20 + " RE-VALIDATING CONTROLLER CORRECTION " + "=" * 20)
        new_validated = response_validation_loop(current_response_text, component, original_prompt_content)

        if not new_validated:
            logging.error("The LLM produced a syntactically invalid configuration while trying to correct a controller error. Aborting.")
            break

        GENERATED_RAW[component] = current_response_text
        VALIDATED_BY_COMP[component] = new_validated


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

    finalized_plan = run_plan_loop(planner, plan_validator)

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
            api_payload = run_exec_loop(executor, current_validator, plan_item)
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
