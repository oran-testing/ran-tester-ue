# main.py

"""
TODO:
- make ResponseValidator abstract
- fix logging
- add description to each planner element
- make validator for planner
- allow another LLM to be used for the planner
- add analyzer
"""

import torch
from transformers import (
    AutoTokenizer, GenerationConfig,
    AutoModelForCausalLM
)

import yaml
import json
import logging
import time
import os
import sys
from typing import List, Dict, Union, Optional, Any
import argparse
import pathlib

from validator import ResponseValidator


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



def generate_response(model, tokenizer, prompt_content: str) -> str:
    messages = [{"role": "user", "content": prompt_content}]
    formatted_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(formatted_prompt, return_tensors="pt").to(model.device)
    generation_config = GenerationConfig(max_new_tokens=1024, do_sample=False, pad_token_id=tokenizer.eos_token_id)
    with torch.no_grad():
        output_tokens = model.generate(**inputs, generation_config=generation_config)
    input_length = inputs['input_ids'].shape[1]
    newly_generated_tokens = output_tokens[0, input_length:]
    return tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()

def generate_response_with_sampling(model, tokenizer, prompt_content: str) -> str:
    messages = [{"role": "user", "content": prompt_content}]
    formatted_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(formatted_prompt, return_tensors="pt").to(model.device)
    generation_config = GenerationConfig(
        max_new_tokens=1024,
        do_sample=True,
        temperature=0.3,
        top_p=0.9,
        pad_token_id=tokenizer.eos_token_id
    )
    with torch.no_grad():
        output_tokens = model.generate(**inputs, generation_config=generation_config)
    input_length = inputs['input_ids'].shape[1]
    newly_generated_tokens = output_tokens[0, input_length:]
    return tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()


def get_intent() -> list[dict]:
    user_prompt = Config.options.get("user_prompt", "")
    intent_prompt = Config.options.get("intent_prompt", "")

    max_attempts = 5
    attempt_count = 1
    current_prompt_content = intent_prompt + user_prompt

    while attempt_count <= max_attempts:
        logging.info(f"Intent extraction attempt {attempt_count} of {max_attempts}")
        logging.info(f"Prompt sent to model:\n{current_prompt_content}")

        raw_response = generate_response(model, tokenizer, current_prompt_content)
        logging.info(f"Model output:\n{raw_response}")

        validator = ResponseValidator(raw_response, config_type="intent")
        validated_data = validator.validate()

        if validated_data:
            logging.info(f"Intent extraction successful. Components: {validated_data}")
            return validated_data

        error_details = "\n".join(validator.get_errors())
        logging.warning(f"Validation failed on attempt {attempt_count}")
        logging.warning("Errors:\n" + error_details)

        attempt_count += 1
        if attempt_count > max_attempts:
            break

        # Build correction prompt for next attempt
        correction_prompt_content = (
            f"The previous intent JSON you provided was invalid for the following reasons:\n"
            f"{error_details}\n\n"
            f"Please regenerate the entire, corrected intent JSON object based on the original user request.\n"
            f"--- ORIGINAL USER REQUEST ---\n{user_prompt}"
        )
        logging.info(f"Correction prompt for regeneration:\n{correction_prompt_content}")
        current_prompt_content = correction_prompt_content

    logging.error("Max attempts reached. Intent extraction failed.")
    return []


def response_validation_loop(current_response_text: str, config_type:str, original_prompt_content: str) -> str:
    if config_type in ['sniffer', 'jammer', 'rtue']:
        logging.info(f"Config type is '{config_type}'. Starting validation and self-correction loop.")
        max_attempts = 25
        attempt_count = 1

        while attempt_count <= max_attempts:
            logging.info("="*40 + f" VALIDATION ATTEMPT {attempt_count} of {max_attempts} " + "="*40)
            validator = ResponseValidator(current_response_text, config_type=config_type)
            validated_data = validator.validate()

            if validated_data:
                logging.info("Validation successful! Extracting final components.")
                return validated_data

            logging.warning("Validation failed. Preparing to self-correct.")
            attempt_count += 1
            if attempt_count > max_attempts:
                logging.error("Maximum correction attempts reached."); break
            error_details = "\n".join([f"- {e}" for e in validator.get_errors()])
            logging.warning(f"Validation Errors:\n{error_details}")
            
            # uncomment later if memory becomes an issue

            # if torch.cuda.is_available():
            #     logging.info("Clearing CUDA cache to prevent out-of-memory errors.")
            #     torch.cuda.empty_cache()

            # add explicit, component-specific guardrails to steer correction
            constraint_hint = ""
            if config_type == "jammer":
                constraint_hint = (
                    "Apply these constraints strictly for 'jammer':\n"
                    "- center_frequency must be within NR FR1 (410e6–7.125e9) or FR2 (24.25e9–52.6e9).\n"
                    "- If device_args contains b200/b210, center_frequency <= 6e9 and FR2 is not allowed.\n"
                    "- sampling_freq >= 2x bandwidth, and for b200-family sampling_freq <= 61.44e6; bandwidth <= ~56e6.\n"
                    "- amplitude in [0,1], tx_gain in [0,90], num_samples > 0.\n"
                )
            elif config_type == "sniffer":
                constraint_hint = (
                    "Apply these constraints strictly for 'sniffer':\n"
                    "- frequency must be within NR FR1 (410e6–7.125e9) or FR2 (24.25e9–52.6e9).\n"
                    "- ssb_numerology in [0,4]; pdcch_coreset_duration in {1,2,3}.\n"
                    "- pdcch_num_prbs > 0; list lengths: dci_sizes=2, AL_corr_thresholds=5, num_candidates_per_AL=5.\n"
                )
            elif config_type == "rtue":
                constraint_hint = (
                    "Apply these constraints strictly for 'rtue':\n"
                    "- rf_srate > 0; rf_tx_gain and rf_rx_gain in [0,90].\n"
                    "- rat_nr_nof_prb > 0 and rat_nr_max_nof_prb >= rat_nr_nof_prb.\n"
                    "- If rf_srate ≈ 23.04e6 or 30.72e6 then rat_nr_nof_prb must be 106.\n"
                )

            correction_prompt_content = (
                f"You must output a SINGLE JSON object for the '{config_type}' component ONLY. "
                f"DO NOT include code fences or commentary. Fix the fields that violate the errors below so the JSON passes validation.\n\n"
                f"{constraint_hint}"
                f"Errors to fix:\n{error_details}\n\n"
                f"Regenerate the COMPLETE JSON now based on the original request below.\n"
                f"--- ORIGINAL REQUEST ---\n{original_prompt_content}"
            )
            logging.info("Generating corrected response...")
            current_response_text = generate_response_with_sampling(model, tokenizer, correction_prompt_content)
            logging.info("="*20 + f" CORRECTED OUTPUT (ATTEMPT {attempt_count}) " + "="*20)
            logging.info(f"'{current_response_text}'")
            logging.info("="*20 + " END OF CORRECTED OUTPUT " + "="*20)

    else:
        logging.warning(f"Skipping validation loop: No validation rules defined for config type '{config_type}'.")
        logging.info("="*20 + " FINAL UNVALIDATED OUTPUT " + "="*20)
        logging.info(current_response_text)
        logging.info("Script finished.")
    return None



if __name__ == '__main__':
    api_args = verify_env()

    configure()

    # --- Model Setup ---
    model_str = Config.options.get("model", None)
    if not model_str:
        logging.error("Model not specified")
        sys.exit(1)
    logging.debug(f"using model: {model_str}")
    model = AutoModelForCausalLM.from_pretrained(model_str, torch_dtype=torch.bfloat16, device_map="auto")
    tokenizer = AutoTokenizer.from_pretrained(model_str)


    api_iface = ApiInterface(*api_args)
    kb = KnowledgeAugmentor()

    intent_output = get_intent()

    for config_type in intent_output:
        logging.info(f"Intent component: {config_type}")
        user_prompt = Config.options.get("user_prompt", "")
        system_prompt = Config.options.get(config_type, "")
        original_prompt_content = system_prompt + user_prompt  # preserved for logs/validator context

        #   prompt structuring
        # - Extract INSTRUCTIONS block from the system prompt.
        # - Retrieve engineering CONTEXT filtered to the specific component.
        # - Build a single, well-structured augmented prompt.

        # split out instruction-only portion if system prompt includes a user section.
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
        current_response_text = generate_response(model, tokenizer, prompt_to_use)
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
                current_response_text = generate_response(model, tokenizer, controller_correction_prompt)
                
                logging.info("="*20 + " RE-VALIDATING CONTROLLER CORRECTION " + "="*20)
                validated_data = response_validation_loop(current_response_text, config_type, original_prompt_content)
                
                if not validated_data:
                    logging.error("The LLM produced a syntactically invalid configuration while trying to correct a controller error. Aborting.")
                
        else:
            logging.error("="*20 + " SCRIPT FAILED " + "="*20)
            logging.error(f"Could not obtain a valid and non-empty '{config_type}' configuration after all attempts.")
            sys.exit(1)



    # logging.info("Entering infinite loop to keep container alive for inspection.")
    # while True:
    #     time.sleep(60)
