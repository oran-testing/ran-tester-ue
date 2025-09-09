from validator import Validator

class PlanValidator(Validator):
    def __init__(self):
        super()._init__()

        self.endpoint_schemas = {
            "start": {"id":str, "type":str, "desc":str, "endpoint":str},
            "stop": {"id":str, "endpoint":str},
            "logs": {"id":str, "endpoint":str},
            "list": {"endpoint":str},
            "health": {"id":str, "endpoint":str}
        }

    def _validate_schema(self, parsed_json):
        is_valid = True
        current_endpoint = parsed_json.get("endpoint", None)
        if not current_endpoint or not isinstance(current_endpoint, str):
            self.errors.append(f"JSON element {parsed_json}, does not have an endpoint")
            is_valid = False

        current_schema = self.endpoint_schemas[current_endpoint]

        for key, expected_type in current_endpoint.items():
            if not isinstance(parsed_json.get(key, None), expected_type):
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

        for plan_element in parsed_json:
            if not self._validate_schema(plan_element):
                return False, self.errors

        return True, json_obj





