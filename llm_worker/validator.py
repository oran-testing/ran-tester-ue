import re
import json

class Validator:
    def __init__(self):
        self.errors = []
        self.required_keys = []
        self.schema = {}

    def _json_to_config(self, json_obj):
        raise RuntimeError("_json_to_config() must be implemented by derived class")

    def validate(self, raw_str):
        raise RuntimeError("validate(self) must be implemented by derived class")

    def _extract_json(self, raw_str):
        fenced_blocks = re.findall(r"```(?:json)?\n([\s\S]*?)```", raw_str)
        for block in fenced_blocks:
            json_res = self._parse_json(block.strip())
            if json_res:
                return json_res

        bracket_pairs = [('[', ']'), ('{', '}')]
        for open_bracket, close_bracket in bracket_pairs:
            start = self.raw_response.find(open_bracket)
            end = self.raw_response.rfind(close_bracket)
            if start != -1 and end != -1:
                candidate = self.raw_response[start:end+1].strip()
                json_res = self._parse_json(candidate)
                if json_res:
                    return json_res

        self.errors.append("No valid JSON structure (array or object) could be parsed.")
        return None

    def _parse_json(self, json_str: str):
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON object: {str(e)}")
            return None

    def _validate_schema(self, parsed_json):
        if required_keys:
            for key in required_keys:
                if key not in parsed_json.keys():
                    self.errors.append(f"Missing required key: '{key}'")
                    return False

        for key, value in parsed_json.items():
            if key not in schema:
                self.errors.append(f"Unknown key provided in response: '{key}'")
                continue
            expected_type = schema[key]
            if not isinstance(value, expected_type):
                self.errors.append(f"Invalid type for key '{key}': expected {expected_type}, but got {type(value)}")
                return False

        return True
