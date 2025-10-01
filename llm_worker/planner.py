from llm_wrapper import LLMWrapper
from config import Config

class Planner:
    def __init__(self, llm_ref: LLMWrapper):
        self.llm_ref = llm_ref
        self.errors = []

    def generate_plan(self, errors=[]):
        planner_prompt = Config.options.get("planner", None)
        if not planner_prompt:
            self.errors.append("No planner prompt in config")
            return False, self.errors

        user_prompt = Config.options.get("user_prompt", None)
        if not user_prompt:
            self.errors.append("No user prompt in config")
            return False, self.errors

        combined_prompt = f"{planner_prompt}\n\n# USER REQUEST: {user_prompt}"

        if errors:
            combined_prompt = f"{combined_prompt}\n\nENCOUNTERED ERRORS{', '.join(errors)}"

        model_response = self.llm_ref._generate_response(combined_prompt)
        if self.errors:
            return False, self.errors

        return True, model_response


