import json
import logging
import re

import yaml

from validator import Validator


class SSBSpooferValidator(Validator):
    """Validates an LLM-derived ssb_spoofer config and converts it to YAML.

    The controller registers ``ssb_spoofer`` to ``Sni5gectConfigConverter``
    (``REQUIRED_KEYS = ['id']``), so the produced ``config_str`` must be a YAML
    dump of the JSON object minus the top-level ``id``. The nested structure
    mirrors ``configs/ssb_spoofer/srs_band3.yaml``:
    ``rf`` / ``ssb`` / ``attack`` / ``operation``.
    """

    def __init__(self):
        super().__init__()

        self.required_keys = ['id']

        self.required_sections = ['rf', 'ssb', 'attack', 'operation']

        self.rf_keys = {
            'device_name': str, 'device_args': str, 'rx_freq_hz': (int, float),
            'tx_freq_hz': (int, float), 'srate_hz': (int, float),
            'rx_gain_db': (int, float), 'tx_gain_db': (int, float),
        }

        self.ssb_keys = {
            'pattern': str, 'scs_khz': (int, float), 'periodicity_ms': (int, float),
            'ssb_freq_offset_hz': (int, float), 'beta_pss': (int, float),
            'beta_sss': (int, float), 'beta_pbch': (int, float),
            'beta_pbch_dmrs': (int, float),
        }

        self.attack_keys = {
            'target_pci': int, 'scan_for_target': bool, 'modify_cell_barred': bool,
            'cell_barred_value': bool, 'modify_coreset0_idx': bool,
            'coreset0_idx_value': int, 'modify_ss0_idx': bool, 'ss0_idx_value': int,
            'modify_intra_freq_resel': bool, 'intra_freq_resel_value': bool,
            'tx_power_offset_db': (int, float), 'continuous_tx': bool,
            'max_bursts': int, 'burst_interval_us': (int, float),
            'burst_length_ms': (int, float),
        }

        self.operation_keys = {
            'scan_duration_sec': (int, float), 'log_level': str, 'log_file': str,
            'save_samples': bool, 'samples_file': str,
        }

    def _validate_section(self, section: dict, schema: dict, name: str):
        if not isinstance(section, dict):
            self.errors.append(f"'{name}' must be a JSON object")
            return

        for key, expected_type in schema.items():
            if key not in section:
                self.errors.append(f"Missing required key: '{name}.{key}'")
                continue
            if isinstance(expected_type, type):
                expected = (expected_type,)
            else:
                expected = tuple(expected_type)
            value = section[key]
            if not isinstance(value, expected):
                self.errors.append(
                    f"Invalid type for key '{name}.{key}': expected {expected_type}, got {type(value)}")

    def _validate_section_types(self, json_obj: dict):
        for section_name in self.required_sections:
            if section_name not in json_obj:
                self.errors.append(f"Missing required section: '{section_name}'")
                continue
            schema = getattr(self, f"{section_name}_keys")
            self._validate_section(json_obj[section_name], schema, section_name)

    def _validate_b210_limits(self, json_obj: dict):
        rf = json_obj.get('rf') or {}
        attack = json_obj.get('attack') or {}

        srate = rf.get('srate_hz')
        if isinstance(srate, (int, float)) and srate <= 0:
            self.errors.append("rf.srate_hz must be > 0")

        for gain_key in ('rx_gain_db', 'tx_gain_db'):
            gain = rf.get(gain_key)
            if isinstance(gain, (int, float)) and not (0 <= gain <= 90):
                self.errors.append(f"rf.{gain_key} must be between 0 and 90")

        for freq_key in ('rx_freq_hz', 'tx_freq_hz'):
            freq = rf.get(freq_key)
            if isinstance(freq, (int, float)):
                if freq <= 0:
                    self.errors.append(f"rf.{freq_key} must be > 0")
                elif freq > 6e9:
                    self.errors.append(
                        f"rf.{freq_key} exceeds B210 max center frequency of 6 GHz")

        if isinstance(srate, (int, float)) and srate > 61.44e6:
            self.errors.append("rf.srate_hz exceeds B210 max sample rate of 61.44 MHz")

        burst_us = attack.get('burst_interval_us')
        if isinstance(burst_us, (int, float)) and burst_us <= 0:
            self.errors.append("attack.burst_interval_us must be > 0")

        burst_ms = attack.get('burst_length_ms')
        if isinstance(burst_ms, (int, float)) and burst_ms <= 0:
            self.errors.append("attack.burst_length_ms must be > 0")

    def _json_to_yaml(self, json_obj: dict) -> str:
        render = {k: v for k, v in json_obj.items() if k != 'id'}
        return yaml.dump(render, sort_keys=False, indent=2)

    def _extract_json(self, raw_str: str):
        fenced_blocks = re.findall(r"```(?:json)?\n([\s\S]*?)```", raw_str)
        for block in fenced_blocks:
            block = block.strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue

        start = raw_str.find('{')
        end = raw_str.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw_str[start:end + 1])
            except json.JSONDecodeError:
                pass

        self.errors.append("No valid JSON object could be parsed.")
        return None

    def validate(self, raw_str):
        raw_str = raw_str.strip()
        json_obj = self._extract_json(raw_str)
        if not json_obj:
            return False, self.errors
        component_id = json_obj.get('id')

        logging.info(f"EXEC JSON: {json_obj}")

        if not isinstance(json_obj, dict):
            self.errors.append("Response must be a single JSON object")
            return False, self.errors

        if not self.required_keys[0] in json_obj:
            self.errors.append(f"Missing required key: '{self.required_keys[0]}'")
            return False, self.errors

        self._validate_section_types(json_obj)
        self._validate_b210_limits(json_obj)

        if self.errors:
            return False, self.errors

        config_str = self._json_to_yaml(json_obj)
        if not config_str:
            self.errors.append("Converting to configuration string failed")
            return False, self.errors

        return True, {"id": component_id, "type": "ssb_spoofer", "config_str": config_str}