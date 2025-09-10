# main.py

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
import re  # plan key parsing

from validator import ResponseValidator

import chromadb
from chromadb.utils import embedding_functions


class Config:
    filename: str = ""
    options: Optional[Dict[str, Any]] = None
    log_level: int = logging.DEBUG


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


def list_processes(control_url, auth_header):
    current_endpoint = "/list"
    headers = {"Authorization": auth_header, "Accept": "application/json", "User-Agent": "llm_worker/1.0"}
    try:
        response = requests.get(url=f"{control_url}{current_endpoint}", headers=headers, verify=False)
        if response.status_code == 200:
            return True, response.json()
        return False, {"error": response.text}
    except requests.exceptions.RequestException as e:
        return False, {"error": str(e)}


def start_process(control_url, auth_header, json_payload):
    current_endpoint = "/start"
    headers = {"Authorization": auth_header, "Accept": "application/json", "User-Agent": "llm_worker/1.0", "Content-Type": "application/json"}
    try:
        response = requests.post(url=f"{control_url}{current_endpoint}", headers=headers, json=json_payload, verify=False)
        if response.status_code == 200:
            return True, response.json()
        return False, {"error": response.text}
    except requests.exceptions.RequestException as e:
        return False, {"error": str(e)}


def stop_process(control_url, auth_header, process_id):
    current_endpoint = "/stop"
    headers = {"Authorization": auth_header, "Accept": "application/json", "User-Agent": "llm_worker/1.0", "Content-Type": "application/json"}
    json_payload = {"id": process_id}
    try:
        response = requests.post(url=f"{control_url}{current_endpoint}", headers=headers, json=json_payload, verify=False)
        if response.status_code == 200:
            return True, response.json()
        return False, {"error": response.text}
    except requests.exceptions.RequestException as e:
        return False, {"error": str(e)}


def get_process_logs(control_url, auth_header, json_payload):
    current_endpoint = "/logs"
    headers = {"Authorization": auth_header, "Accept": "application/json", "User-Agent": "llm_worker/1.0", "Content-Type": "application/json"}
    try:
        response = requests.post(url=f"{control_url}{current_endpoint}", headers=headers, json=json_payload, verify=False)
        if response.status_code == 200:
            return True, response.json()
        return False, {"error": response.text}
    except requests.exceptions.RequestException as e:
        return False, {"error": str(e)}


def _parse_env_list(name: str, default_list: List[float]) -> List[float]:
    raw = os.getenv(name, "")
    if not raw:
        return default_list
    try:
        vals = [float(x.strip()) for x in raw.split(",") if x.strip()]
        return vals if vals else default_list
    except Exception:
        return default_list


def generate_response(model, tokenizer, is_sampling, prompt_content: str,
                      sample_temp: Optional[float] = None,
                      sample_top_p: Optional[float] = None,
                      max_new_tokens: Optional[int] = None) -> str:
    """
    Backwards compatible. If is_sampling=True, you can pass per-candidate temp/top_p.
    Otherwise greedy decoding is used. Defaults unchanged unless env/args provided.
    """
    messages = [{"role": "user", "content": prompt_content}]
    formatted_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(formatted_prompt, return_tensors="pt").to(model.device)

    if not is_sampling:
        generation_config = GenerationConfig(
            max_new_tokens=max_new_tokens or 1024,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )
    else:
        # Allow per-candidate overrides; fall back to env; then to safe defaults.
        env_temp = float(os.getenv("SAMPLE_TEMP", "0.3"))
        env_top_p = float(os.getenv("SAMPLE_TOP_P", "0.9"))
        t = sample_temp if sample_temp is not None else env_temp
        p = sample_top_p if sample_top_p is not None else env_top_p
        generation_config = GenerationConfig(
            max_new_tokens=max_new_tokens or 1024,
            do_sample=True,
            temperature=max(0.05, min(t, 1.5)),
            top_p=max(0.5, min(p, 1.0)),
            pad_token_id=tokenizer.eos_token_id
        )

    with torch.no_grad():
        output_tokens = model.generate(**inputs, generation_config=generation_config)
    input_length = inputs['input_ids'].shape[1]
    newly_generated_tokens = output_tokens[0, input_length:]
    return tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()


def get_plan() -> list[dict]:
    user_prompt = Config.options.get("user_prompt", "")
    plan_prompt = Config.options.get("plan_prompt", "")

    max_attempts = 5
    attempt_count = 1
    current_prompt_content = plan_prompt + user_prompt

    while attempt_count <= max_attempts:
        logging.info(f"Plan extraction attempt {attempt_count} of {max_attempts}")
        logging.info(f"Prompt sent to model:\n{current_prompt_content}")

        raw_response = generate_response(model, tokenizer, False, current_prompt_content)
        logging.info(f"Model output:\n{raw_response}")

        validator = ResponseValidator(raw_response, config_type="plan")
        validated_data = validator.validate()

        if validated_data:
            logging.info(f"Plan extraction successful. Components: {validated_data}")
            return validated_data

        error_details = "\n".join(validator.get_errors())
        logging.warning(f"Validation failed on attempt {attempt_count}")
        logging.warning("Errors:\n" + error_details)

        attempt_count += 1
        if attempt_count > max_attempts:
            break

        # Build correction prompt for next attempt
        correction_prompt_content = (
            f"Please regenerate the entire, corrected plan JSON object based on the original user request.\n"
            f"--- ORIGINAL USER REQUEST ---\n{user_prompt}"
            f"Fix these errors and nothing else:\n{error_details}\n"
        )
        logging.info(f"Correction prompt for regeneration:\n{correction_prompt_content}")
        current_prompt_content = correction_prompt_content

    logging.error("Max attempts reached. Plan extraction failed.")
    return []


# ---------- RL helpers (immediate rewards, no fallback) ----------

def _compute_reward(metrics: dict, prev_json: Optional[dict], cand_json: Optional[dict],
                    forbid_keys=("device_args", "type", "id")) -> float:
    """
    Immediate scalar reward with proximity shaping.
    Components:
      base: +10 if ok, else -0.75*error_count
      proximity penalties (larger negative if further from validity):
        - center_frequency distance to FR1/FR2; heavy extra if device=b200 and >6e9 or FR2
        - sampling_freq vs (2x bandwidth) deficit
        - sampling_freq cap for b200 (>61.44e6)
      structure:
        -0.5 per forbidden key changed
        -0.1 per added key
        -0.05 per changed key
      small bonus if in obviously good region for b200 (FR1 and <=6e9 and sf<=61.44e6)
    """
    if not metrics:
        return -10.0

    # base term
    base = 10.0 if metrics.get("ok") else -0.75 * float(metrics.get("error_count", 0))

    pen_forbid = 0.0
    pen_changed = 0.0
    pen_added = 0.0
    bonus_good = 0.0
    prox_pen = 0.0

    # structure penalties
    if isinstance(prev_json, dict) and isinstance(cand_json, dict):
        prev_keys = set(prev_json.keys())
        cand_keys = set(cand_json.keys())
        changed = [k for k in (prev_keys & cand_keys) if prev_json.get(k) != cand_json.get(k)]
        pen_changed = 0.05 * len(changed)
        for k in forbid_keys:
            if k in changed:
                pen_forbid += 0.5
        added = list(cand_keys - prev_keys)
        pen_added = 0.1 * len(added)

    # proximity shaping (jammer-centric)
    if isinstance(cand_json, dict):
        dev = (str(cand_json.get("device_args", "")) or "").lower()
        f0 = cand_json.get("center_frequency")
        sf = cand_json.get("sampling_freq")
        bw = cand_json.get("bandwidth")

        # center_frequency distance to legal regions
        if isinstance(f0, (int, float)):
            in_fr1 = 410e6 <= f0 <= 7125e6
            in_fr2 = 24.25e9 <= f0 <= 52.6e9
            if not (in_fr1 or in_fr2):
                d = min(
                    abs(f0 - 410e6) / 410e6,
                    abs(f0 - 7125e6) / 7125e6,
                    abs(f0 - 24.25e9) / 24.25e9,
                    abs(f0 - 52.6e9) / 52.6e9
                )
                prox_pen += 4.0 * min(d, 5.0)
            if "b200" in dev or "b210" in dev:
                if f0 and f0 > 6e9:
                    d = (f0 - 6e9) / 6e9
                    prox_pen += 6.0 * min(max(d, 0.0), 5.0)
                if in_fr2:
                    prox_pen += 6.0  # hard disallow for b200 in FR2
                if in_fr1 and f0 <= 6e9:
                    bonus_good += 0.5

        # sampling vs bandwidth (Nyquist)
        if isinstance(sf, (int, float)) and isinstance(bw, (int, float)):
            if sf < 2.0 * bw:
                deficit = (2.0 * bw - sf) / max(2.0 * bw, 1.0)
                prox_pen += 4.0 * min(max(deficit, 0.0), 5.0)

        # sampling cap for b200
        if isinstance(sf, (int, float)) and ("b200" in dev or "b210" in dev):
            if sf > 61.44e6:
                excess = (sf - 61.44e6) / 61.44e6
                prox_pen += 4.0 * min(max(excess, 0.0), 5.0)
            else:
                bonus_good += 0.25

    reward = base - pen_forbid - pen_added - pen_changed - prox_pen + bonus_good
    return reward


def response_validation_loop(current_response_text: str, config_type: str, original_prompt_content: str) -> str:
    if config_type in ['sniffer', 'jammer', 'rtue']:
        logging.info(f"Config type is '{config_type}'. Starting validation and self-correction loop.")
        max_attempts = 25
        attempt_count = 1

        while attempt_count <= max_attempts:
            logging.info("=" * 40 + f" VALIDATION ATTEMPT {attempt_count} of {max_attempts} " + "=" * 40)
            validator = ResponseValidator(current_response_text, config_type=config_type)
            validated_data = validator.validate()

            if validated_data:
                logging.info("Validation successful! Extracting final components.")
                return validated_data

            logging.warning("Validation failed. Preparing to self-correct.")
            attempt_count += 1
            if attempt_count > max_attempts:
                logging.error("Maximum correction attempts reached.")
                break

            error_details = "\n".join([f"- {e}" for e in validator.get_errors()])
            logging.warning(f"Validation Errors:\n{error_details}")

            # Edit-in-place prompt built from last parsed JSON (if any)
            prev_json = validator.get_last_json() or {}
            prev_json_str = json.dumps(prev_json, indent=2)

            # Fetch machine-readable hints (from validator metrics)
            metrics = validator.get_metrics() or {}
            hints = metrics.get("hints", {})
            violated_fields = metrics.get("violated_fields", [])
            must_change_list = [f for f in violated_fields if isinstance(prev_json, dict) and f in prev_json] or violated_fields

            hints_block = json.dumps(hints, indent=2) if hints else "{}"
            must_change_block = json.dumps(must_change_list, indent=2)

            edit_rules = (
                "You must output a SINGLE JSON object for the '{cfg}' component ONLY.\n"
                "STRICT RULES:\n"
                "1) Start from the CURRENT JSON shown below.\n"
                "2) Edit ONLY the fields necessary to fix the errors.\n"
                "3) You MUST modify these fields if present: {must_change}.\n"
                "4) Keep ALL other keys/structure/ID the same.\n"
                "5) Do NOT change these keys: ['device_args','type','id'].\n"
                "6) Field constraints (machine-readable hints):\n{hints}\n"
                "7) Return ONLY raw JSON. No code fences. No comments.\n\n"
                "CURRENT JSON:\n{prev}\n\n"
                "ERRORS TO FIX:\n{errs}\n\n"
                "--- ORIGINAL REQUEST ---\n{orig}\n"
            ).format(cfg=config_type, prev=prev_json_str, errs=error_details, orig=original_prompt_content,
                     hints=hints_block, must_change=must_change_block)

            # K candidates (first greedy, others sampled with per-candidate temps/top_p)
            default_K = 10
            K = int(os.getenv("LLM_K", str(default_K)))
            K = max(1, min(8, K))
            temps = _parse_env_list("LLM_TEMPS", [0.0, 0.2, 0.4, 0.6, 0.8][:K])
            topps = _parse_env_list("LLM_TOPPS", [0.9, 0.95, 0.9, 0.85, 0.8][:K])

            candidates: List[str] = []
            for i in range(K):
                is_sampling = (i != 0)  # first is greedy
                t = temps[i] if i < len(temps) else temps[-1]
                p = topps[i] if i < len(topps) else topps[-1]
                logging.info(f"Generating candidate {i + 1}/{K} (sampling={is_sampling}, temp={t:.2f}, top_p={p:.2f})...")
                cand_text = generate_response(model, tokenizer, is_sampling, edit_rules,
                                              sample_temp=t, sample_top_p=p)
                candidates.append(cand_text)

            # Score candidates with immediate reward (validator metrics only)
            best_idx = 0
            best_reward = -1e9
            best_validated_payload = None
            best_text = candidates[0]

            for idx, cand_text in enumerate(candidates):
                cand_validator = ResponseValidator(cand_text, config_type=config_type)
                cand_valid = cand_validator.validate()
                cand_metrics = cand_validator.get_metrics()
                cand_json = cand_validator.get_last_json()

                reward = _compute_reward(cand_metrics, prev_json, cand_json)
                logging.info(f"[RL] Candidate {idx + 1}/{K} reward = {reward:.3f} | ok={cand_metrics.get('ok')} | errors={cand_metrics.get('error_count')}")
                if reward > best_reward:
                    best_reward = reward
                    best_idx = idx
                    best_text = cand_text
                    best_validated_payload = cand_valid

            logging.info(f"[RL] Selected candidate {best_idx + 1}/{K} with reward {best_reward:.3f}")
            if best_validated_payload:
                logging.info("Validation successful after RL candidate selection.")
                return best_validated_payload

            # Continue loop using best candidate as the current text
            current_response_text = best_text
            logging.info("=" * 20 + f" CORRECTED OUTPUT (ATTEMPT {attempt_count}) " + "=" * 20)
            logging.info(f"'{current_response_text}'")
            logging.info("=" * 20 + " END OF CORRECTED OUTPUT " + "=" * 20)

    else:
        logging.warning(f"Skipping validation loop: No validation rules defined for config type '{config_type}'.")
        logging.info("=" * 20 + " FINAL UNVALIDATED OUTPUT " + "=" * 20)
        logging.info(current_response_text)
        logging.info("Script finished.")
    return None


def save_config_to_file(config_str: str, config_type: str, config_id: str, output_dir: str = "/host/configs"):
    import os
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{config_type}_{config_id}.toml"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w") as f:
        f.write(config_str)
    logging.info(f"Config saved to: {filepath}")


# retrieval + prompt augmentation
class KnowledgeAugmentor:
    """
    Minimal retrieval helper around ChromaDB to fetch domain snippets
    and build a context string for prompt augmentation.

    NOTE: To keep context relevant, chunks should be upserted with metadata:
      metadatas=[{"source": "kb/sniffer.md", "component": "sniffer"}, ...]
    """
    def __init__(self, db_dir="vector_db", collection_name="rf_knowledge", model_name="all-MiniLM-L6-v2"):
        logging.info("Initializing KnowledgeAugmentor...")
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
        db_client = chromadb.PersistentClient(path=db_dir)
        self.collection = db_client.get_collection(name=collection_name, embedding_function=sentence_transformer_ef)
        logging.info("KnowledgeAugmentor initialized.")

    # component-filtered retrieval to avoid mixing unrelated docs
    def retrieve_context_for_component(self, component: str, query: str, n_results: int = 3) -> str:
        logging.info(f"[KnowledgeAugmentor] Retrieving context for component='{component}' | query='{query}'")
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"component": component}
        )
        docs = results.get('documents', [[]])[0] if results else []
        if not docs:
            return ""
        ctx = []
        for i, doc in enumerate(docs):
            try:
                source = results['metadatas'][0][i].get('source', 'unknown')
            except Exception:
                source = "unknown"
            logging.info(f"  [Doc {i + 1} from '{source}']: {doc[:120].strip().replace(chr(10), ' ')}...")
            ctx.append(f"- From {source}:\n{doc}")
        return "\n\n".join(ctx).strip()

    @staticmethod
    def build_augmented_prompt(context: str, system_prompt_block: str, user_request: str, planner_params: Optional[Dict[str, Any]] = None) -> str:
        # Planner parameters are injected as authoritative constraints when present.
        params_block = ""
        if planner_params:
            params_block = f"\n--- PLANNER PARAMETERS (Authoritative) ---\n{json.dumps(planner_params, indent=2)}\n--- END OF PLANNER PARAMETERS ---\n"
        return f"""You are an expert RF systems assistant.
First, review the provided CONTEXT for critical engineering rules.
Then, use that context to follow the INSTRUCTIONS to generate a valid JSON configuration that fulfills the USER REQUEST.
If PLANNER PARAMETERS are provided, you MUST honor them (they override defaults and inferred values).

--- CONTEXT (Rules & Formulas) ---
{context}
--- END OF CONTEXT ---

--- INSTRUCTIONS (Schema & Formatting) ---
{system_prompt_block}
--- END OF INSTRUCTIONS ---

--- USER REQUEST ---
{user_request}
{params_block}Provide only the final JSON object.

--- JSON OUTPUT ---""".strip()


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
    control_ip, control_port, control_token = verify_env()
    configure()
    control_url = f"https://{control_ip}:{control_port}"
    auth_header = f"Bearer {control_token}"
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # --- Model Setup ---
    model_str = Config.options.get("model", None)
    if not model_str:
        logging.error("Model not specified")
        sys.exit(1)
    logging.debug(f"using model: {model_str}")
    model = AutoModelForCausalLM.from_pretrained(model_str, torch_dtype=torch.bfloat16, device_map="auto")
    tokenizer = AutoTokenizer.from_pretrained(model_str)

    kb = KnowledgeAugmentor()  # instantiate augmentor once

    # using llm for plan determination
    plan_output = get_plan()

    # Derive per-component parameters and step list from the planner when applicable.
    component_params: Dict[str, Dict[str, Any]] = {}
    step_list: List[str] = []

    if isinstance(plan_output, dict):
        component_params = derive_component_params(plan_output)
        step_list = derive_steps_from_components(component_params)
    elif isinstance(plan_output, list):
        step_list = plan_output
    else:
        logging.error("Planner returned an unexpected type. Aborting.")
        sys.exit(1)

    for step in step_list:
        if step.startswith("generate_"):
            comp = step.split("_", 1)[1]
            run_generate_step(comp, kb, extra_params=component_params.get(comp, {}))
        elif step.startswith("validate_"):
            comp = step.split("_", 1)[1]
            run_validate_step(comp)
        elif step.startswith("send_"):
            comp = step.split("_", 1)[1]
            run_send_step(comp, control_url, auth_header)

    logging.info("Entering infinite loop to keep container alive for inspection.")
    while True:
        time.sleep(60)
