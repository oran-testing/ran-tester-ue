"""LLM wrapper: supports local GPU models and OpenRouter API.

When ``Config.options.get("provider") == "openrouter"``, the wrapper uses
the OpenRouter API instead of a local model. This allows running without a GPU.
"""

from __future__ import annotations

import json
import logging
import os

import requests

from config import Config


class LLMWrapper:
    """Wraps either a local HF model or the OpenRouter API."""

    def __init__(self):
        self.provider = (Config.options or {}).get("provider", "local")
        self.model_str = getattr(Config, "model_str", None) or (Config.options or {}).get("model", "")
        self._load_model()

    def _load_model(self):
        """Load the model - either local HF or configure for OpenRouter."""
        if self.provider == "openrouter":
            self.api_key = os.getenv("OPENROUTER_API_KEY", "")
            if not self.api_key:
                raise RuntimeError("OPENROUTER_API_KEY is not set")
            self.api_base = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
            logging.info(
                f"LLMWrapper using OpenRouter API at {self.api_base} "
                f"with model {self.model_str}"
            )
            self.model = None
            self.tokenizer = None
        else:
            logging.info(f"LLMWrapper loading local model: {self.model_str}")
            import torch
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                GenerationConfig,
            )
            self._torch = torch
            self._GenerationConfig = GenerationConfig
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_str, torch_dtype=torch.bfloat16, device_map="auto"
            )
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_str)
            logging.info("Local model loaded successfully")

    def _call_openrouter(self, messages: list[dict], temperature: float | None = None,
                         top_p: float | None = None, max_tokens: int = 1024) -> str:
        """Call the OpenRouter chat completions API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/sushant-XD/llm_worker",
        }
        payload = {
            "model": self.model_str,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p

        resp = requests.post(
            f"{self.api_base}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "").strip()

    def _generate_response(self, prompt: str) -> str:
        """Generate a response (greedy decoding for local, temp=0 for API)."""
        if self.provider == "openrouter":
            messages = [{"role": "user", "content": prompt}]
            return self._call_openrouter(messages, temperature=0.0)
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.model.device)
        gen_config = self._GenerationConfig(
            max_new_tokens=1024,
            do_sample=False,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        with self._torch.no_grad():
            output_tokens = self.model.generate(**inputs, generation_config=gen_config)
        input_length = inputs["input_ids"].shape[1]
        newly_generated_tokens = output_tokens[0, input_length:]
        return self.tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()

    def _generate_response_with_sampling(self, prompt: str,
                                          temperature: float | None = 0.3,
                                          top_p: float | None = 0.9) -> str:
        """Generate a response with sampling."""
        if self.provider == "openrouter":
            messages = [{"role": "user", "content": prompt}]
            return self._call_openrouter(
                messages, temperature=temperature or 0.3, top_p=top_p or 0.9
            )
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.model.device)
        gen_config = self._GenerationConfig(
            max_new_tokens=1024,
            do_sample=True,
            temperature=temperature or 0.3,
            top_p=top_p or 0.9,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        with self._torch.no_grad():
            output_tokens = self.model.generate(**inputs, generation_config=gen_config)
        input_length = inputs["input_ids"].shape[1]
        newly_generated_tokens = output_tokens[0, input_length:]
        return self.tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()