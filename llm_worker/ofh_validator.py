import json
import logging
import re

import toml

from validator import Validator


class OfhValidator(Validator):
    """Validates an LLM-derived OFH DoS attacker config and converts it to TOML.

    The controller registers ``ofh`` to ``OfhConfigConverter``
    (``REQUIRED_KEYS = ['id']``), so the produced ``config_str`` must be a TOML
    dump of the JSON object minus the top-level ``id``.

    Schema matches configs/ofh/ofh.toml:
      injection_points, pcap_dir, pcap_list, du, ru, attacker_dir, results_dir,
      duration_seconds, tcpreplay_topspeed, tcpreplay_mbps, tcpreplay_loop,
      keep_history
    """

    def __init__(self):
        super().__init__()
        self.required_keys = ['id']

        self.schema = {
            'id': str,
            'injection_points': list,
            'pcap_dir': str,
            'pcap_list': list,
            'du': str,
            'ru': str,
            'attacker_dir': str,
            'results_dir': str,
            'duration_seconds': (int, float),
            'tcpreplay_topspeed': int,
            'tcpreplay_mbps': (int, float),
            'tcpreplay_loop': int,
            'keep_history': str,
        }

    def _validate_schema_values(self, json_obj: dict):
        for key, value in json_obj.items():
            if key == 'id':
                continue
            if key in self.schema:
                expected_type = self.schema[key]
                if isinstance(expected_type, type):
                    expected = (expected_type,)
                else:
                    expected = tuple(expected_type)
                if not isinstance(value, expected):
                    self.errors.append(
                        f"Invalid type for '{key}': expected {expected_type}, got {type(value).__name__}"
                    )

    def _validate_semantic_values(self, json_obj: dict):
        ts = json_obj.get('tcpreplay_topspeed')
        if ts is not None and ts not in (0, 1):
            self.errors.append("tcpreplay_topspeed must be 0 or 1")

        mbps = json_obj.get('tcpreplay_mbps')
        if mbps is not None and mbps <= 0:
            self.errors.append("tcpreplay_mbps must be > 0")

        duration = json_obj.get('duration_seconds')
        if duration is not None and duration <= 0:
            self.errors.append("duration_seconds must be > 0")

        ips = json_obj.get('injection_points')
        if ips is not None:
            if not isinstance(ips, list) or not ips:
                self.errors.append("injection_points must be a non-empty list")
            else:
                for ip in ips:
                    if ip not in ("DU", "RU"):
                        self.errors.append(f"injection_points item '{ip}' must be 'DU' or 'RU'")

    def _json_to_toml(self, json_obj: dict) -> str:
        render = {k: v for k, v in json_obj.items() if k != 'id'}
        return toml.dumps(render)

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

        self._validate_schema_values(json_obj)
        self._validate_semantic_values(json_obj)

        if self.errors:
            return False, self.errors

        config_str = self._json_to_toml(json_obj)
        if not config_str:
            self.errors.append("Converting to configuration string failed")
            return False, self.errors

        return True, {"id": component_id, "type": "ofh", "config_str": config_str}