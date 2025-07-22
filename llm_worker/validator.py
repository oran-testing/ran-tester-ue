# validator.py
# Updated to return a structured dictionary: {type, id, config}

import re
import json
import logging
import yaml
import toml

class ResponseValidator:
    def __init__(self, raw_response: str, config_type: str = None):
        self.raw_response = raw_response.strip()
        self.config_type = config_type
        self.errors = []
        self.parsed_data = None
        logging.info(f"Validator initialized for type: '{self.config_type}'")

        # --- Schema Definitions ---
        # Jammer schema defines all expected keys and their types. The prompt forces all keys to be present.
        self.jammer_schema = {
            "id": str, "center_frequency": (float, int), "bandwidth": (float, int),
            "amplitude": (float, int), "amplitude_width": (float, int),
            "initial_phase": (float, int), "sampling_freq": (float, int),
            "num_samples": int, "output_iq_file": str, "output_csv_file": str,
            "write_iq": bool, "write_csv": bool, "tx_gain": (float, int), "device_args": str
        }
        # Sniffer schema defines all flattened keys. The prompt also forces all keys to be present.
        self.sniffer_schema = {
            "id": str, "file_path": str, "sample_rate": (float, int),
            "frequency": (float, int), "nid_1": int, "ssb_numerology": int,
            "pdcch_coreset_id": int, "pdcch_subcarrier_offset": int,
            "pdcch_num_prbs": int, "pdcch_numerology": int,
            "pdcch_dci_sizes_list": list, "pdcch_scrambling_id_start": int,
            "pdcch_scrambling_id_end": int, "pdcch_rnti_start": int,
            "pdcch_rnti_end": int, "pdcch_interleaving_pattern": str,
            "pdcch_coreset_duration": int, "pdcch_AL_corr_thresholds": list,
            "pdcch_num_candidates_per_AL": list
        }

        # Defines the minimum set of keys that MUST be present for an RT-UE config.
        self.rtue_required_keys = [
            'id', 'rf_srate', 'rf_tx_gain', 'rf_rx_gain', 'rat_nr_bands',
            'rat_nr_nof_prb', 'usim_imsi', 'nas_apn'
        ]
        
        # Defines all possible valid keys for an RT-UE config and their types for validation.
        self.rtue_full_schema = {
            "id": str, "rf_freq_offset": int, "rf_tx_gain": int, "rf_rx_gain": int,
            "rf_srate": (float, int), "rf_nof_antennas": int, "rf_device_name": str,
            "rf_device_args": str, "rf_time_adv_nsamples": int, "rat_eutra_dl_earfcn": int,
            "rat_eutra_nof_carriers": int, "rat_nr_bands": list, "rat_nr_nof_carriers": int,
            "rat_nr_max_nof_prb": int, "rat_nr_nof_prb": int, "pcap_enable": str,
            "pcap_mac_filename": str, "pcap_mac_nr_filename": str, "pcap_nas_filename": str,
            "log_all_level": str, "log_phy_lib_level": str, "log_all_hex_limit": int,
            "log_filename": str, "log_file_max_size": int, "usim_mode": str, "usim_algo": str,
            "usim_opc": str, "usim_k": str, "usim_imsi": str, "usim_imei": str, "rrc_release": int,
            "rrc_ue_category": int, "nas_apn": str, "nas_apn_protocol": str, "gui_enable": bool
        } 

    def validate(self) -> dict | None:
        json_str = self._extract_json()
        if not json_str: return None # Exit early if no JSON is found

        self.parsed_data = self._parse_json(json_str)
        if not self.parsed_data: return None # Exit early if JSON is invalid

        # Branch validation logic based on the config type determined in main.py
        if self.config_type == "jammer":
            # For jammer, all keys in its schema are considered required.
            self._validate_schema(self.parsed_data, self.jammer_schema, list(self.jammer_schema.keys()))
            self._validate_jammer_values(self.parsed_data)
        elif self.config_type == "sniffer":
            # Same for sniffer, all keys are required.
            self._validate_schema(self.parsed_data, self.sniffer_schema, list(self.sniffer_schema.keys()))
            self._validate_sniffer_values(self.parsed_data)
        elif self.config_type == "rtue":
            # For RT-UE, we check for a specific subset of required keys.
            self._validate_schema(self.parsed_data, self.rtue_full_schema, self.rtue_required_keys)
        else:
            self.errors.append(f"Unknown or unspecified config_type: '{self.config_type}'.")

        # If any validation step added errors, fail now.
        if self.errors:
            return None

        # On success, format the data into the final config string.
        config_string = self._format_validated_data(self.parsed_data)
        if not config_string and not self.errors:
            self.errors.append("Formatting to YAML/TOML failed.")
            return None

        # Return the final structured dictionary for main.py to use.
        return {
            "type": self.config_type,
            "id": self.parsed_data.get("id"),
            "config_str": config_string
        }
    
    def _format_validated_data(self, validated_data: dict) -> str:
        # Create a copy so we don't modify the original parsed data.
        data_for_formatting = validated_data.copy()
        
        # The 'id' is for the manifest, not the file content, so remove it before formatting.
        data_for_formatting.pop('id', None)

        if self.config_type == "jammer":
            # Convert the dictionary to a YAML formatted string.
            return yaml.dump(data_for_formatting, sort_keys=False, indent=2)
        
        elif self.config_type == "sniffer":
            sniffer_section = {}
            pdcch_section = {}
            # Re-create the nested TOML structure from the flat JSON keys.
            for key, value in data_for_formatting.items():
                if key.startswith("pdcch_"):
                    # "pdcch_coreset_id" becomes "coreset_id" in the pdcch section.
                    new_key = key.replace("pdcch_", "", 1)
                    pdcch_section[new_key] = value
                elif key in ["file_path", "sample_rate", "frequency", "nid_1", "ssb_numerology"]:
                    sniffer_section[key] = value
            
            final_toml_structure = {"sniffer": sniffer_section, "pdcch": [pdcch_section]}
            return toml.dumps(final_toml_structure) # Convert dict to TOML string.
            
        elif self.config_type == "rtue":
            # Delegate to the specific rtue formatter.
            return self._format_rtue_toml(data_for_formatting)
        return ""
        

    def _format_rtue_toml(self, flat_data: dict) -> str:
        # Maps the final TOML section names to the prefixes used in the flat JSON keys.
        section_map = {
            'rf': 'rf_', 'rat.eutra': 'rat_eutra_', 'rat.nr': 'rat_nr_',
            'pcap': 'pcap_', 'log': 'log_', 'usim': 'usim_', 'rrc': 'rrc_',
            'nas': 'nas_', 'gui': 'gui_'
        }
        reconstructed_data = {}
        for toml_section, prefix in section_map.items():
            section_content = {}
            # Find all keys in the flat data that belong to the current section.
            for flat_key, value in flat_data.items():
                if flat_key.startswith(prefix):
                    # "rf_tx_gain" becomes "tx_gain"
                    new_key = flat_key[len(prefix):]
                    section_content[new_key] = value
            # Only add the section to the TOML if keys for it were found.
            if section_content:
                current_level = reconstructed_data
                # Handle nested sections like 'rat.nr' by splitting on the dot.
                path = toml_section.split('.')
                for part in path[:-1]:
                    current_level = current_level.setdefault(part, {})
                current_level[path[-1]] = section_content
        return toml.dumps(reconstructed_data)

    def get_errors(self):
        return self.errors

    def _extract_json(self):
        # Find a JSON block, whether it's in a markdown code fence or not.
        match = re.search(r"```(?:json)?\n([\s\S]*?)```", self.raw_response)
        if match: return match.group(1).strip()
        start = self.raw_response.find('{')
        end = self.raw_response.rfind('}')
        if start != -1 and end != -1: return self.raw_response[start:end+1]
        self.errors.append("No valid JSON structure (e.g., '{...}') found.")
        return None

    def _parse_json(self, json_str: str):
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON parsing failed: {str(e)}")
            return None

    def _validate_schema(self, data: dict, schema: dict, required_keys: list = None):
        # check if all required keys are present in the data.
        if required_keys:
            for key in required_keys:
                if key not in data:
                    self.errors.append(f"Missing required key: '{key}'")
        
        # check for type correctness and find any unexpected keys.
        for key, value in data.items():
            if key not in schema:
                self.errors.append(f"Unknown key provided in response: '{key}'")
                continue # Skip type check for unknown keys
            
            expected_type = schema[key]
            # Check if the value's type matches the expected type in the schema.
            if not isinstance(value, expected_type):
                self.errors.append(f"Invalid type for key '{key}': expected {expected_type}, but got {type(value)}")

    def _validate_jammer_values(self, data: dict):
        # Specific business logic checks for jammer values.
        if data.get("bandwidth", 0) <= 0: self.errors.append("bandwidth must be > 0")
        if not (0 <= data.get("amplitude", -1) <= 1): self.errors.append("amplitude must be between 0 and 1")
        if data.get("tx_gain", -1) < 0: self.errors.append("tx_gain must be >= 0")

    def _validate_sniffer_values(self, data: dict):
        # Specific business logic checks for sniffer values.
        if data.get("sample_rate", 0) <= 0: self.errors.append("sample_rate must be > 0")
        if data.get("pdcch_num_prbs", 0) <= 0: self.errors.append("pdcch_num_prbs must be > 0")
        if not (0 <= data.get("ssb_numerology") <= 4): self.errors.append("ssb_numerology must be >= 0 and <= 4")
