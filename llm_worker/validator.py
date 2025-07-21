import re
import json

class ResponseValidator:
    def __init__(self, raw_response: str):
        self.raw_response = raw_response.strip()
        self.errors = []
        self.parsed_data = None

        # Define expected schema for JAMMER config
        self.jammer_schema = {
            "id": str,
            "center_frequency": (float, int),
            "bandwidth": (float, int),
            "amplitude": (float, int),
            "amplitude_width": (float, int),
            "initial_phase": (float, int),
            "sampling_freq": (float, int),
            "num_samples": int,
            "output_iq_file": str,
            "output_csv_file": str,
            "write_iq": bool,
            "write_csv": bool,
            "tx_gain": (float, int)
        }

    def extract_json(self):
        match = re.search(r"```(?:json)?\n([\s\S]*?)```", self.raw_response)
        if match:
            return match.group(1).strip()

        start = self.raw_response.find('{')
        end = self.raw_response.rfind('}')
        if start != -1 and end != -1:
            return self.raw_response[start:end+1]

        self.errors.append("No valid JSON structure found.")
        return None

    def parse_json(self, json_str: str):
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON parsing failed: {str(e)}")
            return None

    def validate_jammer_schema(self, data: dict):
        for key, expected_type in self.jammer_schema.items():
            if key not in data:
                self.errors.append(f"Missing key: '{key}' in jammer configuration")
                continue
            if not isinstance(data[key], expected_type):
                self.errors.append(
                    f"Invalid type for '{key}': expected {expected_type}, got {type(data[key])}"
                )

    def validate_jammer_values(self, data: dict):
        if not self.errors:
            if data["center_frequency"] <= 0:
                self.errors.append("center_frequency must be > 0")
            if data["bandwidth"] <= 0:
                self.errors.append("bandwidth must be > 0")
            if not (0 <= data["amplitude"] <= 1):
                self.errors.append("amplitude must be between 0 and 1")
            if not (0 <= data["amplitude_width"] <= 1):
                self.errors.append("amplitude_width must be between 0 and 1")
            if data["sampling_freq"] <= 0:
                self.errors.append("sampling_freq must be > 0")
            if data["num_samples"] <= 0:
                self.errors.append("num_samples must be > 0")
            if data["tx_gain"] < 0:
                self.errors.append("tx_gain must be >= 0")

    def validate(self):
        json_str = self.extract_json()
        if json_str:
            self.parsed_data = self.parse_json(json_str)
            if self.parsed_data:
                self.validate_jammer_schema(self.parsed_data)
                self.validate_jammer_values(self.parsed_data)
        return self.parsed_data

    def get_errors(self):
        return self.errors
