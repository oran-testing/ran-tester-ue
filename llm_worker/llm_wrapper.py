import logging
import torch
from transformers import (
    AutoTokenizer, GenerationConfig,
    AutoModelForCausalLM
)

from config import Config

class LLMWrapper:
    def __init__(self):
        self.model = AutoModelForCausalLM.from_pretrained(Config.model_str, torch_dtype=torch.bfloat16, device_map="auto")
        self.tokenizer = AutoTokenizer.from_pretrained(Config.model_str)

    def _generate_response(self, prompt: str, phase: str = None, call_type: str = None, token_acc: dict = None) -> str:
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.model.device)
        generation_config = GenerationConfig(max_new_tokens=1024, do_sample=False, pad_token_id=self.tokenizer.eos_token_id)
        with torch.no_grad():
            output_tokens = self.model.generate(**inputs, generation_config=generation_config)
        input_length = inputs['input_ids'].shape[1]
        newly_generated_tokens = output_tokens[0, input_length:]
        output_length = newly_generated_tokens.shape[0]
        total_tokens = int(input_length) + int(output_length)
        tag = f"[{phase.upper()}][{call_type}]" if phase and call_type else "[LLM]"
        logging.info(f"{tag} input={input_length}, output={output_length}, total={total_tokens}")
        if token_acc is not None and phase:
            token_acc.setdefault(phase, {"input": 0, "output": 0})
            token_acc[phase]["input"] += int(input_length)
            token_acc[phase]["output"] += int(output_length)
            logging.info(f"[{phase.upper()}] total input={token_acc[phase]['input']}, total output={token_acc[phase]['output']}")
        return self.tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()

    def _generate_response_with_sampling(self, prompt: str, phase: str = None, call_type: str = None, token_acc: dict = None) -> str:
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.model.device)

        generation_config = GenerationConfig(
            max_new_tokens=1024,
            do_sample=True,
            temperature=0.3,
            top_p=0.9,
            pad_token_id=self.tokenizer.eos_token_id
        )

        with torch.no_grad():
            output_tokens = self.model.generate(**inputs, generation_config=generation_config)

        input_length = inputs['input_ids'].shape[1]
        newly_generated_tokens = output_tokens[0, input_length:]
        output_length = newly_generated_tokens.shape[0]
        total_tokens = int(input_length) + int(output_length)
        tag = f"[{phase.upper()}][{call_type}]" if phase and call_type else "[LLM]"
        logging.info(f"{tag} input={input_length}, output={output_length}, total={total_tokens}")
        if token_acc is not None and phase:
            token_acc.setdefault(phase, {"input": 0, "output": 0})
            token_acc[phase]["input"] += int(input_length)
            token_acc[phase]["output"] += int(output_length)
            logging.info(f"[{phase.upper()}] total input={token_acc[phase]['input']}, total output={token_acc[phase]['output']}")
        return self.tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()

