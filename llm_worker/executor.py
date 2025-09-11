from llm_wrapper import LLMWrapper

from config import Config

class Executor(LLMWrapper):
    def execute(self, plan_json):
        for val in ["type", "endpoint", "desc", "id"]:
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

        plan_prompt = f"User request: {plan_json.get('desc', '')}\nUse the following id: {plan_json.get('id','')}"

        combined_prompt = f"{executor_prompt}\n\n{type_prompt}\n\n{plan_prompt}"

        model_response = self._generate_response(combined_prompt)

        if self.errors:
            return False, self.errors

        return True, model_response


