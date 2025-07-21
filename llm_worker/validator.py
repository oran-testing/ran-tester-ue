import re
import json
import yaml

class ResponseValidator:
    def __init__(self, raw_response: str, config_type: str):
        self.raw_response = raw_response.strip()
        self.config_type = config_type.lower()
        self.errors = []
        self.parsed_data = None

        # JAMMER schema
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

        # SNIFFER schema
        self.sniffer_schema = {
            "id": str,
            "file_path": str,
            "sample_rate": (float, int),
            "frequency": (float, int),
            "nid_1": int,
            "ssb_numerology": int,
            "pdcch": list
        }

        self.pdcch_schema = {
            "coreset_id": int,
            "subcarrier_offset": int,
            "num_prbs": int,
            "numerology": int,
            "dci_sizes_list": list,
            "scrambling_id_start": int,
            "scrambling_id_end": int,
            "rnti_start": int,
            "rnti_end": int,
            "interleaving_pattern": str,
            "coreset_duration": int,
            "AL_corr_thresholds": list,
            "num_candidates_per_AL": list
        }

    def extract_json_or_yaml(self):
        # Match fenced code block
        match = re.search(r"```(?:json|yaml)?\n([\s\S]+?)```", self.raw_response)
        if match:
            return match.group(1).strip()

        # Match indented block starting with key
        yaml_like = re.search(r"(?:(sniffer|jammer):\s*\n[\s\S]+)", self.raw_response)
        if yaml_like:
            return yaml_like.group(0).strip()

        # Last resort: assume full body is config-like
        if self.raw_response.startswith(('sniffer:', 'jammer:', 'id:')) or ':' in self.raw_response:
            return self.raw_response

        self.errors.append("No valid JSON or YAML structure found.")
        return None

    def parse_json(self, text: str):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def parse_yaml(self, text: str):
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as e:
            self.errors.append(f"YAML parsing failed: {str(e)}")
            return None

    def normalize_parsed_data(self, data):
        if self.config_type == "sniffer" and isinstance(data, dict) and "sniffer" in data:
            return data["sniffer"]
        if self.config_type == "jammer" and isinstance(data, dict) and "jammer" in data:
            return data["jammer"]
        return data

    def validate_jammer_schema(self, data: dict):
        for key, expected_type in self.jammer_schema.items():
            if key not in data:
                self.errors.append(f"Missing key: '{key}' in jammer configuration")
            elif not isinstance(data[key], expected_type):
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

    def validate_sniffer_schema(self, data: dict):
        for key, expected_type in self.sniffer_schema.items():
            if key not in data:
                self.errors.append(f"Missing key: '{key}' in sniffer configuration")
            elif not isinstance(data[key], expected_type):
                self.errors.append(
                    f"Invalid type for '{key}': expected {expected_type}, got {type(data[key])}"
                )

        if "pdcch" in data and isinstance(data["pdcch"], list):
            for idx, block in enumerate(data["pdcch"]):
                for pkey, ptype in self.pdcch_schema.items():
                    if pkey not in block:
                        self.errors.append(f"Missing key '{pkey}' in pdcch[{idx}]")
                    elif not isinstance(block[pkey], ptype):
                        self.errors.append(
                            f"Invalid type for pdcch[{idx}]['{pkey}']: expected {ptype}, got {type(block[pkey])}"
                        )

    def validate_sniffer_values(self, data: dict):
        if not self.errors:
            if data["sample_rate"] <= 0:
                self.errors.append("sample_rate must be > 0")
            if data["frequency"] <= 0:
                self.errors.append("frequency must be > 0")
            if data["nid_1"] < 0:
                self.errors.append("nid_1 must be >= 0")
            if data["ssb_numerology"] not in [0, 1, 2]:
                self.errors.append("ssb_numerology must be 0, 1, or 2")

    def validate(self):
        raw_text = self.extract_json_or_yaml()
        if not raw_text:
            return None

        parsed = self.parse_json(raw_text)
        if not parsed:
            parsed = self.parse_yaml(raw_text)

        if parsed:
            self.parsed_data = self.normalize_parsed_data(parsed)
            if self.config_type == "jammer":
                self.validate_jammer_schema(self.parsed_data)
                self.validate_jammer_values(self.parsed_data)
            elif self.config_type == "sniffer":
                self.validate_sniffer_schema(self.parsed_data)
                self.validate_sniffer_values(self.parsed_data)
            else:
                self.errors.append(f"Unknown config type: '{self.config_type}'")

        return self.parsed_data

    def get_errors(self):
        return self.errors

