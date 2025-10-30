import logging
import torch
# from transformers import (
#     AutoTokenizer, GenerationConfig,
#     AutoModelForCausalLM
# )
import os
from openai import OpenAI
from config import Config

class LLMWrapper:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY") or Config.options.get("api_key")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found in environment or config")
        self.client = OpenAI(api_key=api_key)
        self.model = Config.model_str
        logging.info(f"Initialized OpenAI client with model: {self.model}")


    def _generate_response(self, prompt: str) -> str:
        try:
            kwargs = {
                "model": self.model,
                "input": prompt,
                "max_output_tokens": 2048,
                "reasoning": {"effort" : "minimal"},
                "text": {"verbosity":  "low"}
            }
            response = self.client.responses.create(**kwargs)
            generated_text = response.output_text
            if hasattr(response, 'usage') and response.usage:
                logging.info(f"LLM token usage: input={response.usage.input_tokens}, "
                           f"output={response.usage.output_tokens}, "
                           f"total={response.usage.total_tokens}")
            
            return generated_text

        except Exception as e:
            logging.error(f"OPENAI Call failed: {e}")
            raise

    def _generate_response_with_sampling(self, prompt: str) -> str:
        return self._generate_response(prompt)

