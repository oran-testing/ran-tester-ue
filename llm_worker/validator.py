import logging
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
            block = block.strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError as e:
                self.errors.append(f"Invalid JSON object: {str(e)}")

        self.errors.append("No valid JSON structure (array or object) could be parsed.")
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
