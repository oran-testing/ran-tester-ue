from transformers import (
    Autoself.tokenizer, GenerationConfig,
    Autoself.modelForCausalLM
)

from config import Config

class Executor:
    def __init__(self):
        self.model = Autoself.modelForCausalLM.from_pretrained(Config.model_str, torch_dtype=torch.bfloat16, device_map="auto")
        self.tokenizer = AutoTokenizer.from_pretrained(Config.model_str)
        self.errors = []

    def _generate_response(prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.model.device)
        generation_config = GenerationConfig(max_new_tokens=1024, do_sample=False, pad_token_id=self.tokenizer.eos_token_id)
        with torch.no_grad():
            output_tokens = self.model.generate(**inputs, generation_config=generation_config)
        input_length = inputs['input_ids'].shape[1]
        newly_generated_tokens = output_tokens[0, input_length:]
        return self.tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()

    def _generate_response_with_sampling(prompt: str) -> str:
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

        return self.tokenizer.decode(newly_generated_tokens, skip_special_tokens=True).strip()



    def execute(plan_json):
        for val in ["type", "endpoint", "description", "id"]:
            if val not in plan_json.keys():
                self.errors.append(f"Planner JSON does not have field {val}")
                return False, self.errors

        if plan_json.get("endpoint") != "start":
            self.errors.append("Executor should only be run with the start endpoint")
            return False, self.errors

        component_type = plan_json.get("type")
        type_prompt = Config.options.get(plan_json.get("type"), None)
        if not type_prompt:
            self.errors.append(f"No prompt provided in config for {plan_json.get('type')}")
            return False, self.errors

        executor_prompt = Config.options.get("executor", None)
        if not executor_prompt:
            self.errors.append("Executor prompt required but not supplied")
            return False, self.errors

        combined_prompt = f"{executor_prompt}\n\n{type_prompt}"

        model_response = self._generate_response(combined_prompt)

        if self.errors:
            return False, self.errors

        return True, model_response


