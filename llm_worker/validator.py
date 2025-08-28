# validator.py
# Updated to return a structured dictionary: {type, id, config}
# and to expose last_parsed_json + metrics (with machine-readable hints).

import re
import json
import logging
import yaml
import toml
import configparser
from io import StringIO
from typing import Optional


class ResponseValidator:
    def __init__(self, raw_response: str, config_type: str = None):
        self.raw_response = raw_response.strip()
        self.config_type = config_type
        self.errors = []
        self.parsed_data = None

        # Expose last parsed JSON and basic metrics
        self.last_parsed_json: Optional[dict] = None
        self.metrics = {
            "ok": False,
            "error_count": 0,
            "errors": [],
            "violated_fields": [],
            "hints": {},   # machine-readable constraint hints populated on violations
        }

        logging.info(f"Validator initialized for type: '{self.config_type}'")

        # --- Schema Definitions ---
        self.jammer_schema = {
            "id": str, "center_frequency": (float, int), "bandwidth": (float, int),
            "amplitude": (float, int), "amplitude_width": (float, int),
            "initial_phase": (float, int), "sampling_freq": (float, int),
            "num_samples": int, "output_iq_file": str, "output_csv_file": str,
            "write_iq": bool, "write_csv": bool, "tx_gain": (float, int), "device_args": str
        }

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

        self.rtue_required_keys = [
            'id', 'rf_srate', 'rf_tx_gain', 'rf_rx_gain', 'rat_nr_bands',
            'rat_nr_nof_prb', 'usim_imsi', 'nas_apn'
        ]

        self.rtue_full_schema = {
            "id": str, "rf_freq_offset": int, "rf_tx_gain": int, "rf_rx_gain": int,
            "rf_srate": (float, int), "rf_nof_antennas": int, "rf_device_name": str,
            "rf_device_args": str, "rf_time_adv_nsamples": int, "rat_eutra_dl_earfcn": int,
            "rat_eutra_nof_carriers": int, "rat_nr_bands": int, "rat_nr_nof_carriers": int,
            "rat_nr_max_nof_prb": int, "rat_nr_nof_prb": int, "pcap_enable": str,
            "pcap_mac_filename": str, "pcap_mac_nr_filename": str, "pcap_nas_filename": str,
            "log_all_level": str, "log_phy_lib_level": str, "log_all_hex_limit": int,
            "log_filename": str, "log_file_max_size": int, "usim_mode": str, "usim_algo": str,
            "usim_opc": str, "usim_k": str, "usim_imsi": str, "usim_imei": str, "rrc_release": int,
            "rrc_ue_category": int, "nas_apn": str, "nas_apn_protocol": str, "gui_enable": bool, "gw_ip_devname": str,
            "gw_ip_netmask": str, "general_metrics_influxdb_enable": bool, "general_metrics_influxdb_url": str,
            "general_metrics_influxdb_port": int, "general_metrics_influxdb_org": str, "general_metrics_influxdb_token": str,
            "general_metrics_influxdb_bucket": str, "general_metrics_period_secs": float, "general_ue_data_identifier": str
        }

        self.valid_components = {"rtue", "sniffer", "jammer"}

    # New: getters for RL loop
    def get_last_json(self):
        return self.last_parsed_json

    def get_metrics(self):
        return self.metrics
    
    def save_debug_output(self):
        try:
            debug_file = "/var/log/validator_debug.jsonl"
            with open(debug_file, "a") as f:
                json.dump({
                    "config_type": self.config_type,
                    "raw_response": self.raw_response,
                    "errors": self.errors,
                    "parsed_data": self.parsed_data
                }, f)
                f.write("\n")
        except Exception as e:
            logging.error(f"Failed to write validator debug log: {e}")


    def validate(self) -> dict | list | None:
        json_str = self._extract_json()
        if not json_str:
            self._finalize_metrics()
            return None  # Exit early if no JSON is found

        self.parsed_data = self._parse_json(json_str)
        if not self.parsed_data:
            self._finalize_metrics()
            return None  # Exit early if JSON is invalid

        if self.config_type == "intent":
            if not isinstance(self.parsed_data, list):
                self.errors.append("Intent must be a JSON array/list")
                self._finalize_metrics()
                return None
            logging.info(f"Validating intent list: {self.parsed_data}")
            self._validate_intent_values(self.parsed_data)
            if self.errors:
                self._finalize_metrics()
                return None
            self.metrics["ok"] = True
            self._finalize_metrics()
            return self.parsed_data

        # Branch validation logic
        if self.config_type == "jammer":
            self._validate_schema(self.parsed_data, self.jammer_schema, list(self.jammer_schema.keys()))
            self._validate_jammer_values(self.parsed_data)

        elif self.config_type == "sniffer":
            self._validate_schema(self.parsed_data, self.sniffer_schema, list(self.sniffer_schema.keys()))
            self._validate_sniffer_values(self.parsed_data)

        elif self.config_type == "rtue":
            self._validate_schema(self.parsed_data, self.rtue_full_schema, self.rtue_required_keys)
            self._validate_rtue_values(self.parsed_data)

        else:
            self.errors.append(f"Unknown or unspecified config_type: '{self.config_type}'.")

        # If any validation step added errors, fail now.
        if self.errors:
            self._finalize_metrics()
            return None

        # On success, format the data into the final config string.
        config_string = self._format_validated_data(self.parsed_data)
        if not config_string and not self.errors:
            self.errors.append("Formatting to YAML/TOML failed.")
            self._finalize_metrics()
            return None

        # success
        self.metrics["ok"] = True
        self._finalize_metrics()
    
        self.save_debug_output()
        return {
            "type": self.config_type,
            "id": self.parsed_data.get("id"),
            "config_str": config_string
        }


    def _finalize_metrics(self):
        self.metrics["error_count"] = len(self.errors)
        self.metrics["errors"] = list(self.errors)

        # Heuristic extraction of violated fields: look for known field names in error strings
        violated = set()
        known_fields_by_type = {
            "jammer": [
                "center_frequency", "bandwidth", "amplitude", "amplitude_width",
                "initial_phase", "sampling_freq", "num_samples", "output_iq_file",
                "output_csv_file", "write_iq", "write_csv", "tx_gain", "device_args"
            ],
            "sniffer": [
                "file_path", "sample_rate", "frequency", "nid_1", "ssb_numerology",
                "pdcch_coreset_id", "pdcch_subcarrier_offset", "pdcch_num_prbs",
                "pdcch_numerology", "pdcch_dci_sizes_list", "pdcch_scrambling_id_start",
                "pdcch_scrambling_id_end", "pdcch_rnti_start", "pdcch_rnti_end",
                "pdcch_interleaving_pattern", "pdcch_coreset_duration",
                "pdcch_AL_corr_thresholds", "pdcch_num_candidates_per_AL"
            ],
            "rtue": list(self.rtue_full_schema.keys())
        }
        candidates = known_fields_by_type.get(self.config_type or "", [])
        for e in self.errors:
            for fld in candidates:
                if fld in e:
                    violated.add(fld)
        # also capture quoted names if present
        for e in self.errors:
            m = re.search(r"'([^']+)'", e)
            if m:
                violated.add(m.group(1))

        self.metrics["violated_fields"] = list(violated)

    def _format_validated_data(self, validated_data: dict) -> str:
        data_for_formatting = validated_data.copy()
        data_for_formatting.pop('id', None)

        if self.config_type == "jammer":
            return yaml.dump(data_for_formatting, sort_keys=False, indent=2)

        elif self.config_type == "sniffer":
            sniffer_section = {}
            pdcch_section = {}
            for key, value in data_for_formatting.items():
                if key.startswith("pdcch_"):
                    new_key = key.replace("pdcch_", "", 1)
                    pdcch_section[new_key] = value
                elif key in ["file_path", "sample_rate", "frequency", "nid_1", "ssb_numerology"]:
                    sniffer_section[key] = value
            final_toml_structure = {"sniffer": sniffer_section, "pdcch": [pdcch_section]}
            return toml.dumps(final_toml_structure)

        elif self.config_type == "rtue":
            return self._format_rtue_conf(data_for_formatting)

        return ""

    def _format_rtue_conf(self, flat_data: dict) -> str:
        section_map = {
            'rf': 'rf_', 'rat.eutra': 'rat_eutra_', 'rat.nr': 'rat_nr_',
            'pcap': 'pcap_', 'log': 'log_', 'usim': 'usim_', 'rrc': 'rrc_',
            'nas': 'nas_', 'gui': 'gui_', 'gw': 'gw_', 'general': 'general_'
        }

        config = configparser.ConfigParser()
        config.optionxform = str

        for section_name, prefix in section_map.items():
            section_content = {}
            for flat_key, value in flat_data.items():
                if flat_key.startswith(prefix):
                    new_key = flat_key[len(prefix):]
                    section_content[new_key] = str(value)
            if section_content:
                config[section_name] = section_content

        with StringIO() as output:
            config.write(output)
            return output.getvalue()

    def get_errors(self):
        return self.errors

    def _extract_json(self):
        # Try fenced code blocks first
        fenced_blocks = re.findall(r"```(?:json)?\n([\s\S]*?)```", self.raw_response)
        for block in fenced_blocks:
            try:
                _ = json.loads(block.strip())
                return block.strip()
            except json.JSONDecodeError:
                continue

        # Fall back to the largest array or object
        bracket_pairs = [('[', ']'), ('{', '}')]
        for open_bracket, close_bracket in bracket_pairs:
            start = self.raw_response.find(open_bracket)
            end = self.raw_response.rfind(close_bracket)
            if start != -1 and end != -1:
                candidate = self.raw_response[start:end + 1].strip()
                try:
                    _ = json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    continue

        self.errors.append("No valid JSON structure (array or object) could be parsed.")
        return None

    def _parse_json(self, json_str: str):
        try:
            obj = json.loads(json_str)
            self.last_parsed_json = obj
            return obj
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON parsing failed: {str(e)}")
            return None

    def _validate_schema(self, data: dict, schema: dict, required_keys: list = None):
        # Presence of required keys
        if required_keys:
            for key in required_keys:
                if key not in data:
                    self.errors.append(f"Missing required key: '{key}'")

        # Type checks and unknown keys
        for key, value in data.items():
            if key not in schema:
                self.errors.append(f"Unknown key provided in response: '{key}'")
                continue
            expected_type = schema[key]
            if not isinstance(value, expected_type):
                self.errors.append(f"Invalid type for key '{key}': expected {expected_type}, but got {type(value)}")

    # Component value validators + machine-readable hints

    def _validate_jammer_values(self, data: dict):
        hints = self.metrics.get("hints", {})

        # Basic ranges
        if data.get("bandwidth", 0) <= 0:
            self.errors.append("bandwidth must be > 0")
            hints.setdefault("bandwidth", {}).setdefault("min", 1.0)

        amp = data.get("amplitude", -1)
        if not (0.0 <= amp <= 1.0):
            self.errors.append("amplitude must be between 0 and 1")
            hints.setdefault("amplitude", {}).update({"min": 0.0, "max": 1.0})

        if data.get("tx_gain", -1) < 0 or data.get("tx_gain", 0) > 90:
            self.errors.append("tx_gain must be between 0 and 90")
            hints.setdefault("tx_gain", {}).update({"min": 0, "max": 90})

        # Nyquist for generation
        sf = data.get("sampling_freq"); bw = data.get("bandwidth")
        if isinstance(sf, (int, float)) and isinstance(bw, (int, float)):
            if sf < 2.0 * bw:
                self.errors.append("sampling_freq must be at least 2x bandwidth")
                hints.setdefault("sampling_freq", {})["min_relative"] = {"field": "bandwidth", "factor": 2.0}

        # Frequency envelope (FR1/FR2)
        f0 = data.get("center_frequency")
        if isinstance(f0, (int, float)):
            if f0 <= 0:
                self.errors.append("center_frequency must be > 0")
                hints.setdefault("center_frequency", {})["min"] = 1.0
            else:
                in_fr1 = 410e6 <= f0 <= 7125e6
                in_fr2 = 24.25e9 <= f0 <= 52.6e9
                if not (in_fr1 or in_fr2):
                    self.errors.append("center_frequency must be inside NR FR1 (410e6–7.125e9) or FR2 (24.25e9–52.6e9)")
                    hints.setdefault("center_frequency", {})["allowed_ranges"] = [[410e6, 7125e6], [24.25e9, 52.6e9]]

        # Hardware gating (device_args)
        dev = (data.get("device_args", "") or "").lower()
        if "b200" in dev or "b210" in dev:
            if isinstance(f0, (int, float)):
                if f0 > 6e9:
                    self.errors.append("center_frequency exceeds B200-family tuning range (<= 6e9)")
                    hints.setdefault("center_frequency", {})["b200_cap_max"] = 6e9
                if 24.25e9 <= f0 <= 52.6e9:
                    self.errors.append("B200-family cannot operate in NR FR2 (24.25e9–52.6e9)")
                    hints.setdefault("center_frequency", {})["b200_fr2_allowed"] = False
            if isinstance(sf, (int, float)) and sf > 61.44e6:
                self.errors.append("sampling_freq exceeds B200-family practical maximum (~61.44e6)")
                hints.setdefault("sampling_freq", {})["b200_cap_max"] = 61.44e6
            if isinstance(bw, (int, float)) and bw > 56e6:
                self.errors.append("bandwidth exceeds B200-family front-end practical limit (~56e6)")
                hints.setdefault("bandwidth", {})["b200_cap_max"] = 56e6

        # Basic sanity on num_samples
        ns = data.get("num_samples", 0)
        if isinstance(ns, int) and ns <= 0:
            self.errors.append("num_samples must be > 0")
            hints.setdefault("num_samples", {})["min"] = 1

        self.metrics["hints"] = hints

    def _validate_sniffer_values(self, data: dict):
        hints = self.metrics.get("hints", {})

        # Fundamental checks
        if data.get("sample_rate", 0) <= 0:
            self.errors.append("sample_rate must be > 0")
            hints.setdefault("sample_rate", {})["min"] = 1.0
        if data.get("pdcch_num_prbs", 0) <= 0:
            self.errors.append("pdcch_num_prbs must be > 0")
            hints.setdefault("pdcch_num_prbs", {})["min"] = 1
        if not (0 <= data.get("ssb_numerology") <= 4):
            self.errors.append("ssb_numerology must be >= 0 and <= 4")
            hints.setdefault("ssb_numerology", {}).update({"min": 0, "max": 4})

        # NR band membership: FR1 or FR2
        f = data.get("frequency")
        if isinstance(f, (int, float)):
            in_fr1 = 410e6 <= f <= 7125e6
            in_fr2 = 24.25e9 <= f <= 52.6e9
            if not (in_fr1 or in_fr2):
                self.errors.append("frequency must be inside NR FR1 (410e6–7.125e9) or FR2 (24.25e9–52.6e9)")
                hints.setdefault("frequency", {})["allowed_ranges"] = [[410e6, 7125e6], [24.25e9, 52.6e9]]

        # CORESET duration must be 1, 2, or 3
        dur = data.get("pdcch_coreset_duration")
        if isinstance(dur, int) and dur not in (1, 2, 3):
            self.errors.append("pdcch_coreset_duration must be one of {1, 2, 3}")
            hints.setdefault("pdcch_coreset_duration", {})["allowed_values"] = [1, 2, 3]

        # Range parameters must satisfy start ≤ end
        sid0 = data.get("pdcch_scrambling_id_start")
        sid1 = data.get("pdcch_scrambling_id_end")
        if isinstance(sid0, int) and isinstance(sid1, int) and sid0 > sid1:
            self.errors.append("pdcch_scrambling_id_start must be <= pdcch_scrambling_id_end")
            hints.setdefault("pdcch_scrambling_id_start", {})["lte_field"] = "pdcch_scrambling_id_end"

        rnti0 = data.get("pdcch_rnti_start")
        rnti1 = data.get("pdcch_rnti_end")
        if isinstance(rnti0, int) and isinstance(rnti1, int) and rnti0 > rnti1:
            self.errors.append("pdcch_rnti_start must be <= pdcch_rnti_end")
            hints.setdefault("pdcch_rnti_start", {})["lte_field"] = "pdcch_rnti_end"

        # Fixed-length lists where applicable
        dci = data.get("pdcch_dci_sizes_list")
        if isinstance(dci, list) and len(dci) != 2:
            self.errors.append("pdcch_dci_sizes_list must have exactly 2 elements")
            hints.setdefault("pdcch_dci_sizes_list", {})["length"] = 2

        al_thr = data.get("pdcch_AL_corr_thresholds")
        if isinstance(al_thr, list) and len(al_thr) != 5:
            self.errors.append("pdcch_AL_corr_thresholds must have exactly 5 elements")
            hints.setdefault("pdcch_AL_corr_thresholds", {})["length"] = 5

        al_n = data.get("pdcch_num_candidates_per_AL")
        if isinstance(al_n, list) and len(al_n) != 5:
            self.errors.append("pdcch_num_candidates_per_AL must have exactly 5 elements")
            hints.setdefault("pdcch_num_candidates_per_AL", {})["length"] = 5

        self.metrics["hints"] = hints

    def _validate_rtue_values(self, data: dict):
        hints = self.metrics.get("hints", {})

        # Basic RF ranges
        srate = data.get("rf_srate")
        if isinstance(srate, (int, float)) and srate <= 0:
            self.errors.append("rf_srate must be > 0")
            hints.setdefault("rf_srate", {})["min"] = 1.0

        txg = data.get("rf_tx_gain")
        if isinstance(txg, (int, float)) and not (0 <= txg <= 90):
            self.errors.append("rf_tx_gain must be between 0 and 90")
            hints.setdefault("rf_tx_gain", {}).update({"min": 0, "max": 90})

        rxg = data.get("rf_rx_gain")
        if isinstance(rxg, (int, float)) and not (0 <= rxg <= 90):
            self.errors.append("rf_rx_gain must be between 0 and 90")
            hints.setdefault("rf_rx_gain", {}).update({"min": 0, "max": 90})

        # PRB coherence
        prb = data.get("rat_nr_nof_prb")
        prb_max = data.get("rat_nr_max_nof_prb")
        if isinstance(prb, int) and prb <= 0:
            self.errors.append("rat_nr_nof_prb must be > 0")
            hints.setdefault("rat_nr_nof_prb", {})["min"] = 1
        if isinstance(prb_max, int) and prb_max <= 0:
            self.errors.append("rat_nr_max_nof_prb must be > 0")
            hints.setdefault("rat_nr_max_nof_prb", {})["min"] = 1
        if isinstance(prb, int) and isinstance(prb_max, int) and prb_max < prb:
            self.errors.append("rat_nr_max_nof_prb must be >= rat_nr_nof_prb")
            hints.setdefault("rat_nr_max_nof_prb", {})["gte_field"] = "rat_nr_nof_prb"

        # Optional mapping: if srate ≈ 23.04e6 or 30.72e6 then PRB should be 106
        if isinstance(srate, (int, float)) and isinstance(prb, int):
            if abs(srate - 23.04e6) < 1e5 or abs(srate - 30.72e6) < 1e5:
                if prb != 106:
                    self.errors.append("rat_nr_nof_prb must be 106 for rf_srate near 23.04e6 or 30.72e6")
                    hints.setdefault("rat_nr_nof_prb", {})["must_equal"] = 106

        self.metrics["hints"] = hints

    def _validate_intent_values(self, data: list) -> None:
        if not all(isinstance(item, str) for item in data):
            self.errors.append("All items in intent list must be strings")
            return

        invalid_components = [c for c in data if c not in self.valid_components]
        if invalid_components:
            self.errors.append(f"Invalid component(s) in intent list: {invalid_components}")
            return
