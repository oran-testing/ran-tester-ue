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

from rtue_validator import RTUEValidator
from sniffer_validator import SnifferValidator
from jammer_validator import JammerValidator


class Config:
    filename : str = ""
    options : dict = None
    log_level : int = logging.DEBUG

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

    model_str = Config.options.get("model", None)
    if not model_str:
        raise RuntimeError("Model not specified")

    logging.debug(f"using model: {model_str}")

    executor = Executor(model_str)
    api_iface = ApiInterface(*api_args)
    kb = KnowledgeAugmentor()

    intent_output = get_intent()

    for config_type in intent_output:
        logging.info(f"Intent component: {config_type}")
        user_prompt = Config.options.get("user_prompt", "")
        system_prompt = Config.options.get(config_type, "")
        original_prompt_content = system_prompt + user_prompt

        system_instructions = system_prompt.split("### USER REQUEST:")[0] if "### USER REQUEST:" in system_prompt else system_prompt

        # build a retrieval query that is explicit about the component and goal.
        retrieval_query = f"Rules, constraints, and known-good examples for a '{config_type}' configuration to fulfill: {user_prompt}"

        retrieved_context = kb.retrieve_context_for_component(config_type, retrieval_query)

        # construct the final augmented prompt.
        prompt_to_use = KnowledgeAugmentor.build_augmented_prompt(
            context=retrieved_context,
            system_prompt_block=system_instructions,
            user_request=user_prompt
        )
        # --------------------------------------------------------------------

        # ---Initial Generation ---
        logging.info("="*20 + " EXECUTING PROMPT " + "="*20)
        current_response_text = executor.generate_response(model, tokenizer, prompt_to_use)
        logging.info("="*20 + " MODEL GENERATED OUTPUT " + "="*20)
        logging.info(f"'{current_response_text}'")
        logging.info("="*20 + " END OF MODEL OUTPUT " + "="*20)


        # --- Validation and Self-Correction Loop ---
        validated_data = response_validation_loop(current_response_text, config_type, original_prompt_content)
        if validated_data is None:
            logging.error(f"Validation failed for {config_type}.")
            continue
        final_config_type = validated_data.get('type')
        final_config_id = validated_data.get('id')
        final_config_string = validated_data.get('config_str')

        # --- Final Outcome Logic (with controller API call) ---
        if validated_data and validated_data.get('config_str'):
            logging.info("="*20 + " FINAL VALIDATED CONFIGURATION " + "="*20)


            controller_retry_max_attempts = 10
            controller_attempt_count = 1
            
            while controller_attempt_count <= controller_retry_max_attempts:
                # Extract latest validated data
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
                json_payload["rf"] = {"type":"b200","images_dir":"/usr/share/uhd/images"}
                
                success, response_data = api_iface.make_request("/start", payload=json_payload)

                if success:
                    logging.info("Successfully sent start command to controller.")
                    logging.info(f"Controller response: {response_data}")
                    logging.info("Script finished successfully.")
                    break

                # --- Handle Controller Rejection ---
                logging.error("Failed to start process via controller.")
                controller_error_details = response_data.get("error", "No error details from controller.")
                logging.error(f"Controller error: {controller_error_details}")
                
                controller_attempt_count += 1
                if controller_attempt_count > controller_retry_max_attempts:
                    logging.critical("Maximum controller retry attempts reached. Aborting script.")
                    sys.exit(1)

                logging.warning("Attempting to generate a new configuration based on controller feedback.")

                # Create a new prompt to correct the controller-level semantic error
                controller_correction_prompt = (
                    f"The configuration you provided was syntactically valid, but the system controller REJECTED it for the following reason:\n"
                    f"{controller_error_details}\n\n"
                    f"This implies a logical or semantic error (e.g., an invalid parameter value, a resource conflict). "
                    f"Please analyze this feedback and regenerate the entire, corrected JSON object based on the original request.\n"
                    f"--- ORIGINAL REQUEST ---\n{original_prompt_content}"
                )
                
                # Generate a new configuration based on controller feedback
                current_response_text = executor.generate_response(model, tokenizer, controller_correction_prompt)
                
                logging.info("="*20 + " RE-VALIDATING CONTROLLER CORRECTION " + "="*20)
                validated_data = response_validation_loop(current_response_text, config_type, original_prompt_content)
                
                if not validated_data:
                    logging.error("The LLM produced a syntactically invalid configuration while trying to correct a controller error. Aborting.")
                
        else:
            logging.error("="*20 + " SCRIPT FAILED " + "="*20)
            logging.error(f"Could not obtain a valid and non-empty '{config_type}' configuration after all attempts.")
            sys.exit(1)



