# validator.py

import yaml
import tomllib
import configparser
import re
from textwrap import dedent
from typing import Dict, Any, List, Optional

# --- PyYAML Scientific Notation & Duplicate Key Patches (Proven to be necessary) ---
SCIENTIFIC_NOTATION_REGEX = re.compile(r'[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)', re.X)
def _no_duplicate_yaml_constructor(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(f"Duplicate key '{key}' found at line {node.start_mark.line + 1}")
        value = loader.construct_object(value_node, deep=deep)
        mapping[key] = value
    return loader.construct_mapping(node, deep)
yaml.add_implicit_resolver('tag:yaml.org,2002:float', SCIENTIFIC_NOTATION_REGEX, Loader=yaml.FullLoader)
yaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_yaml_constructor, Loader=yaml.FullLoader)


class LLMResponseValidator:
    # ... (__init__ and process methods are the same and correct) ...
    def __init__(self, llm_response: str):
        if not llm_response or not llm_response.strip(): self.llm_response = ""
        else: self.llm_response = dedent(llm_response).strip()
        self.errors: List[str] = []; self.process_type: Optional[str] = None; self.process_id: Optional[str] = None; self.config_data: Optional[Dict] = None
    def process(self) -> Dict[str, Any]:
        if not self.llm_response: self.errors.append("Empty response received."); return self._create_failure_output()
        self.config_data = self._extract_config()
        if self.errors: return self._create_failure_output()
        if not self.config_data: self.errors.append("Could not find or parse a valid configuration block."); return self._create_failure_output()
        self.process_type = self._infer_process_type()
        if not self.process_type:
            if not self.errors: self.errors.append("Could not determine process type.")
            return self._create_failure_output()
        self.process_id = self._extract_process_id()
        if not self.process_id: self.errors.append("Could not find a process 'id'."); return self._create_failure_output()
        if self.process_type == "jammer": self._validate_jammer_rules()
        elif self.process_type == "sniffer": self._validate_sniffer_rules()
        return self._create_failure_output() if self.errors else self._create_success_output()

    def _validate_jammer_rules(self):
        """Validates jammer configuration against the FULL schema, including positive integer checks."""
        required_fields = {
            "center_frequency": (float, int), "bandwidth": (float, int), "sampling_freq": (float, int),
            "tx_gain": int, "num_samples": int, "device_args": str, "amplitude": (float, int),
            "amplitude_width": (float, int), "initial_phase": (float, int), "output_iq_file": str, "write_iq": bool
        }
        for field, f_type in required_fields.items():
            if field not in self.config_data: self.errors.append(f"Jammer config missing required field: '{field}'.")
            elif not isinstance(self.config_data.get(field), f_type): self.errors.append(f"Jammer field '{field}' has wrong type. Expected {f_type}, got {type(self.config_data[field])}.")
        
        samp_freq = self.config_data.get('sampling_freq')
        bandwidth = self.config_data.get('bandwidth')
        if isinstance(samp_freq, (int, float)) and isinstance(bandwidth, (int, float)):
            if samp_freq < bandwidth: self.errors.append("Jammer value error: 'sampling_freq' must be >= 'bandwidth'.")
        
        amplitude = self.config_data.get('amplitude')
        if isinstance(amplitude, (int, float)) and not (0.0 <= amplitude <= 1.0):
            self.errors.append(f"Jammer value error: 'amplitude' must be between 0.0 and 1.0, but got {amplitude}.")

        # --- FIX for Test #21 ---
        # IMPROVEMENT: Check for positive integer values where logical
        num_samples = self.config_data.get('num_samples')
        if isinstance(num_samples, int) and num_samples <= 0:
            self.errors.append(f"Jammer value error: 'num_samples' must be a positive integer, but got {num_samples}.")

    def _validate_sniffer_rules(self):
        """Validates sniffer configuration against the FULL schema, including list content types."""
        if "sniffer" not in self.config_data:
            self.errors.append("Sniffer config missing required section: '[sniffer]'.")
        else:
            sniffer_section = self.config_data['sniffer']
            required_sniffer_fields = { "file_path": str, "sample_rate": (float, int), "frequency": (float, int), "nid_1": int, "ssb_numerology": int }
            for field, f_type in required_sniffer_fields.items():
                if field not in sniffer_section: self.errors.append(f"Sniffer section '[sniffer]' missing required field: '{field}'.")
                elif not isinstance(sniffer_section.get(field), f_type): self.errors.append(f"Sniffer field 'sniffer.{field}' has wrong type. Expected {f_type}, got {type(sniffer_section[field])}.")
            ssb_num = sniffer_section.get('ssb_numerology')
            if isinstance(ssb_num, int) and not (0 <= ssb_num <= 4): self.errors.append(f"Sniffer value error: 'ssb_numerology' must be 0-4.")

        pdcch_list = self.config_data.get("pdcch")
        if not isinstance(pdcch_list, list) or not pdcch_list:
            self.errors.append("Sniffer config must have at least one '[[pdcch]]' table (i.e., a non-empty list).")
        else:
            required_pdcch_fields = { "coreset_id": int, "num_prbs": int, "dci_sizes_list": list }
            for i, pdcch_item in enumerate(pdcch_list):
                for field, f_type in required_pdcch_fields.items():
                    if field not in pdcch_item: self.errors.append(f"Sniffer '[[pdcch]]' item #{i} is missing required field: '{field}'.")
                    elif not isinstance(pdcch_item.get(field), f_type): self.errors.append(f"Sniffer field 'pdcch.{field}' in item #{i} has wrong type.")
                
                # --- FIX for Test #20 ---
                # IMPROVEMENT: Check contents of dci_sizes_list
                dci_list = pdcch_item.get("dci_sizes_list")
                if isinstance(dci_list, list) and not all(isinstance(x, int) for x in dci_list):
                    self.errors.append(f"Sniffer 'dci_sizes_list' in item #{i} must contain only integers.")
    
    # ... (_extract_config, _infer_process_type, _extract_process_id, _create_success/failure_output) remain the same ...
    def _extract_config(self) -> Optional[Dict]:
        response_lower = self.llm_response.lower()
        if "### yaml output:" in response_lower:
            try:
                config_string = re.split(r"###\s*yaml\s*output:", self.llm_response, flags=re.IGNORECASE)[-1].strip()
                if config_string.startswith("```"): config_string = re.split(r"```(?:yaml)?\n", config_string, maxsplit=1)[-1].rsplit("```", 1)[0]
                return yaml.load(config_string, Loader=yaml.FullLoader)
            except yaml.YAMLError as e:
                self.errors.append(f"Failed to parse YAML content. Error: {e}"); return None
        if "### toml output:" in response_lower:
            try:
                config_string = re.split(r"###\s*toml\s*output:", self.llm_response, flags=re.IGNORECASE)[-1].strip()
                if config_string.startswith("```"): config_string = re.split(r"```(?:toml)?\n", config_string, maxsplit=1)[-1].rsplit("```", 1)[0]
                return tomllib.loads(config_string)
            except tomllib.TOMLDecodeError as e:
                self.errors.append(f"Failed to parse TOML content. Error: {e}"); return None
        return None
    def _infer_process_type(self) -> Optional[str]:
        if not self.config_data: return None
        is_jammer = {"center_frequency", "bandwidth", "tx_gain"}.issubset(self.config_data.keys())
        is_sniffer = "sniffer" in self.config_data or "pdcch" in self.config_data
        if is_jammer and is_sniffer: self.errors.append("Ambiguous configuration: Keys for both 'jammer' and 'sniffer' types were found."); return None
        return "jammer" if is_jammer else "sniffer" if is_sniffer else None
    def _extract_process_id(self) -> Optional[str]:
        match = re.search(r"^\s*id:\s*['\"]?([\w_.-]+)['\"]?", self.llm_response, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else None
    def _create_success_output(self) -> Dict[str, Any]:
        config_string_final = ""
        if self.process_type == "jammer": config_string_final = yaml.dump(self.config_data, sort_keys=False, indent=2)
        elif self.process_type == "sniffer":
            lines = []
            if 'sniffer' in self.config_data: lines.append('[sniffer]'); lines.extend([f"{k} = {repr(v)}" for k, v in self.config_data['sniffer'].items()]); lines.append('')
            if 'pdcch' in self.config_data:
                for item in self.config_data['pdcch']: lines.append('[[pdcch]]'); lines.extend([f"{k} = {repr(v)}" for k, v in item.items()]); lines.append('')
            config_string_final = "\n".join(lines)
        return {"process_type": self.process_type, "process_id": self.process_id, "config_string": config_string_final.strip(), "errors": []}
    def _create_failure_output(self) -> Dict[str, Any]:
        return {"original_response": self.llm_response, "errors": self.errors}