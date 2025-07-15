# auto_tuner_agent.py (Optimized for High-VRAM GPU)
import os
import socket
import time
import requests
import logging
import torch
import yaml
import re
import random
import argparse
from tqdm import tqdm
from itertools import product
import threading
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from transformers import (
    AutoTokenizer, GenerationConfig,
    AutoModelForCausalLM
)
from simulation_env import mock_run_simulation_and_get_reward

# ... (HyperparameterAgent and other functions remain unchanged) ...
class HyperparameterAgent:
    def __init__(self, action_space: dict):
        self.action_space = action_space
        self.q_table = {}
        self.learning_rate = 0.1
        self.epsilon = 0.9
        self.epsilon_decay = 0.95
        self.min_epsilon = 0.1

    def get_action(self) -> dict:
        actions = self._get_all_actions()
        if random.random() < self.epsilon:
            print("[Auto-Tuner] ACTION: Exploring with random hyperparameters.")
            return random.choice(actions)
        else:
            print("[Auto-Tuner] ACTION: Exploiting with best-known hyperparameters.")
            if not self.q_table: return random.choice(actions)
            best_action_tuple = max(self.q_table, key=self.q_table.get)
            return dict(best_action_tuple)

    def learn(self, action: dict, reward: float):
        action_tuple = tuple(sorted(action.items()))
        old_q = self.q_table.get(action_tuple, 0.0)
        new_q = old_q + self.learning_rate * (reward - old_q)
        self.q_table[action_tuple] = new_q
        print(f"[Auto-Tuner] LEARNING: Q-value for {dict(action_tuple)} updated to {new_q:.4f}")
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)
        print(f"[Auto-Tuner] STATUS: New exploration rate (epsilon) is {self.epsilon:.3f}")

    def _get_all_actions(self) -> list[dict]:
        keys, values = self.action_space.keys(), self.action_space.values()
        return [dict(zip(keys, instance)) for instance in product(*values)]

def _parse_llm_output(text: str) -> dict:
    try:
        if "### YAML Output:" in text:
            yaml_string = text.split("### YAML Output:")[-1].strip()
            if yaml_string.startswith("```yaml"):
                yaml_string = yaml_string.split("```yaml\n", 1)[-1]
                if "```" in yaml_string:
                     yaml_string = yaml_string.rsplit("```", 1)[0]
            config = yaml.safe_load(yaml_string)
            if isinstance(config, dict): return config
    except (yaml.YAMLError, IndexError): pass
    return None

def execute_generation_run(hparams: dict, model, tokenizer) -> float:
    print(f"\n--- [Worker] Starting run with Generation HPs: {hparams} ---")
    
    PROMPT_TEMPLATE = """You are a highly skilled RF engineer specializing in electronic countermeasures.
Your mission is to generate a complete YAML configuration file to effectively jam a target frequency.
### Instructions:
1.  Analyze the `High-Level Goal`.
2.  Determine the optimal values for **all** required configuration parameters.
3.  The output MUST be a single, valid YAML block containing all necessary keys.
4.  Use snake_case for all keys (e.g., `center_frequency`).
5.  Use scientific 'e' notation for frequencies and bandwidth.
6.  Do not output anything other than the given set of keys.
### Example:
High-Level Goal: Jam a target at 0.915 GHz
### Example YAML Output:
amplitude: 0.9
amplitude_width: 0.1
center_frequency: 9.15e8
bandwidth: 10e6
initial_phase: 0
sampling_freq: 20e6
num_samples: 20000
output_iq_file: "output.fc32"
output_csv_file: "output.csv"
write_iq: false
write_csv: true
device_args: "type=b200"
tx_gain: 55
---
### Current Task:
High-Level Goal: Jam a target at {freq:.4f} GHz
### YAML Output:
"""
    test_frequencies = [1.83, 1.842, 1.85, 1.865, 1.88, 1.90, 1.915, 1.923]
    
    generation_config = GenerationConfig(
        max_new_tokens=250,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=True,
        **hparams
    )

    prompts = [PROMPT_TEMPLATE.format(freq=f) for f in test_frequencies]
    inputs = tokenizer(prompts, return_tensors="pt", padding=True, truncation=True).to(model.device)
    
    output_tokens = model.generate(**inputs, generation_config=generation_config)
    full_texts = tokenizer.batch_decode(output_tokens, skip_special_tokens=True)

    total_score = 0
    print("="*40)
    print(f"DEBUGGING: Batch outputs for HPs: {hparams}")
    for i, full_text in enumerate(full_texts):
        config = _parse_llm_output(full_text)
        score = mock_run_simulation_and_get_reward(config)
        total_score += score

    print("="*40)
    avg_score = total_score / len(test_frequencies)
    print(f"--- [Worker] Run Complete. Final average score: {avg_score:.4f} ---")
    return avg_score

app = FastAPI()
@app.post("/command")
async def receive_command(command: str):
    """
    Receives a command from the controller.
    If the command is 'start_tuning', it starts the main_tuning_task in a new thread.
    """
    logging.info(f"Received command from controller: '{command}'")
    
    if command:

        logging.info("Acknowledged received the following command: " + command)
        # Start the main tuning logic in a non-blocking background thread
        return {"status": "ok", "message": "Thanks for the command."}
    else:
        logging.warning(f"Unknown command: '{command}'")
        return {"status": "error", "message": f"Unknown command: {command}"}



logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

def contact_controller(message: str):
    # The controller's API is at http://controller:9000
    # The name 'controller' works because they are in the same Docker network.
    controller_url = "http://controller:9000/from-worker"
    payload = { "sender": "llm_agent", "content": message }
    
    logging.info(f"LLM Agent is online. Attempting to contact controller at {controller_url}")
    
    # Retry connecting to the controller in case it's not ready yet
    for i in range(10): # Retry for ~50 seconds
        try:
            response = requests.post(controller_url, json=payload, timeout=10)
            response.raise_for_status()
            logging.info(f"Successfully contacted controller. Response: {response.json()}")
            return
        except requests.exceptions.RequestException as e:
            logging.warning(f"Could not contact controller (attempt {i+1}/10): {e}. Retrying in 5 seconds...")
            time.sleep(5)
    
    logging.error("Failed to contact controller after multiple attempts. Exiting.")
    exit(1)





# ... (main function remains unchanged) ...
def main():
    parser = argparse.ArgumentParser(description="Auto-Tuner for LLM Generation.")
    parser.add_argument("--model", type=str, default="deepseek-ai/DeepSeek-Coder-6.7B-Instruct", help="Base model to use.")
    parser.add_argument("--loops", type=int, default=50, help="Number of hyperparameter sets to test.")
    args = parser.parse_args()

    hyperparameter_space = {
        'temperature': [0.6, 0.7, 0.8],
        'top_p': [0.85, 0.90, 0.95],
        'repetition_penalty': [1.0, 1.1, 1.15],
    }
    
    auto_tuner = HyperparameterAgent(hyperparameter_space)
    run_history = []

    print("="*20 + " LOADING BASE MODEL (HIGH PRECISION) " + "="*20)
    print(f"Using model: {args.model}")
    
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16, 
        device_map="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token
    print("="*20 + " MODEL LOADED " + "="*20)

    try:
        print(f"Running for {args.loops} loops. Press Ctrl+C to stop early and see results.")
        for i in range(args.loops):
            print(f"\n{'='*15} Auto-Tuner Episode {i+1}/{args.loops} {'='*15}")
            chosen_hps = auto_tuner.get_action()
            reward = execute_generation_run(
                hparams=chosen_hps, model=model, tokenizer=tokenizer
            )
            auto_tuner.learn(action=chosen_hps, reward=reward)
            run_history.append({'reward': reward, 'hps': chosen_hps})
            
    except KeyboardInterrupt:
        print("\n\nUser interrupt detected! Stopping the training loop and proceeding to report results.")
    
    print("\n" + "="*20 + " Sequential Run-by-Run History " + "="*20)
    for i, run in enumerate(run_history):
        reward = run['reward']
        hps = run['hps']
        print(f"  Episode {i+1:02d}: Score = {reward:+.4f} | Hyperparameters: {hps}")
        
    sorted_q_table = sorted(auto_tuner.q_table.items(), key=lambda item: item[1], reverse=True)
    
    best_hps = dict(sorted_q_table[0][0])
    print(f"\nRECOMMENDED GENERATION HYPERPARAMETERS: {best_hps}")




if __name__ == "__main__":
    contact_controller("LLM Agent is online and ready for tasks.")
        
    logging.info("LLM worker now listening for commands on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

    main()
