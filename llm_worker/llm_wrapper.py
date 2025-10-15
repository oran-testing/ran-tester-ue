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

    def _generate_response(self, prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.model.device)
        generation_config = GenerationConfig(max_new_tokens=1024, do_sample=False, pad_token_id=self.tokenizer.eos_token_id)
        with torch.no_grad():
            output_tokens = self.model.generate(**inputs, generation_config=generation_config)
        input_length = inputs['input_ids'].shape[1]
        newly_generated_tokens = output_tokens[0, input_length:]
        # Log token usage for each LLM call (deterministic path)
        try:
            output_length = newly_generated_tokens.shape[0]
            total_tokens = int(input_length) + int(output_length)
            logging.info(f"LLM token usage (greedy): input={input_length}, output={output_length}, total={total_tokens}")
        except Exception as e:
            logging.debug(f"Failed to log token counts (greedy): {e}")
        return self.tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()

    def _generate_response_with_sampling(self, prompt: str) -> str:
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
        # Log token usage for each LLM call (sampling path)
        try:
            output_length = newly_generated_tokens.shape[0]
            total_tokens = int(input_length) + int(output_length)
            logging.info(f"LLM token usage (sampling): input={input_length}, output={output_length}, total={total_tokens}")
        except Exception as e:
            logging.debug(f"Failed to log token counts (sampling): {e}")
        return self.tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()

