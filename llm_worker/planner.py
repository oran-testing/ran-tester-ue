
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

