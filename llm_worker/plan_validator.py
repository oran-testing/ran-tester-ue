from validator import Validator
import logging

class PlanValidator(Validator):
    def __init__(self):
        super().__init__()

        self.endpoint_schemas = {
            "start": {"id":str, "type":str, "desc":str, "endpoint":str, "rf":str},
            "stop": {"id":str, "endpoint":str},
            "logs": {"id":str, "type":str, "endpoint":str},
            "list": {"endpoint":str},
            "health": {"id":str, "endpoint":str}
        }

    def _validate_schema(self, parsed_json):
        current_schema = self.endpoint_schemas[parsed_json.get("endpoint", "start")]

        is_valid = True
        for key_val in current_schema.keys():
            if not parsed_json.get(key_val, None):
                self.errors.append(f"JSON element {parsed_json}, does not have required key {key_val}")
                is_valid = False

        for key, expected_type in current_schema.items():
            if not isinstance(parsed_json.get(key, None), expected_type):
                logging.error(f"ERROR:\n{parsed_json}")
                self.errors.append(f"JSON field {key} is not of expected type: {expected_type}")
                is_valid = False

        return is_valid



    def validate(self, raw_str):
        raw_str = raw_str.strip()
        json_obj = self._extract_json(raw_str)
        if not json_obj:
            return False, self.errors

        if not isinstance(json_obj, list):
            self.errors.append(f"Supplied JSON object is not an array: {json_obj}")
            return False, self.errors

        for plan_element in json_obj:
            if not self._validate_schema(plan_element):
                return False, self.errors

        return True, json_obj





