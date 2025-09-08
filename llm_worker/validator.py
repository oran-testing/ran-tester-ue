import re
import json
import logging
import yaml
import toml
import configparser
from io import StringIO

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
            json_res = self._parse_json(block.strip())
            if json_res:
                return json_res

        bracket_pairs = [('[', ']'), ('{', '}')]
        for open_bracket, close_bracket in bracket_pairs:
            start = self.raw_response.find(open_bracket)
            end = self.raw_response.rfind(close_bracket)
            if start != -1 and end != -1:
                candidate = self.raw_response[start:end+1].strip()
                json_res = self._parse_json(candidate)
                if json_res:
                    return json_res

        self.errors.append("No valid JSON structure (array or object) could be parsed.")
        return None

    def _parse_json(self, json_str: str):
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON object: {str(e)}")
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




# TODO: planner validator

class RTUEValidator(Validator):
    def __init__(self):
        super()._init__()

        self.required_keys = [
            'id', 'rf_srate', 'rf_tx_gain', 'rf_rx_gain', 'rat_nr_bands',
            'rat_nr_nof_prb', 'usim_imsi', 'nas_apn'
        ]

        self.schema = {
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

    def _json_to_config(self, json_obj: dict) -> str:
        section_map = {
            'rf': 'rf_', 'rat.eutra': 'rat_eutra_', 'rat.nr': 'rat_nr_',
            'pcap': 'pcap_', 'log': 'log_', 'usim': 'usim_', 'rrc': 'rrc_',
            'nas': 'nas_', 'gui': 'gui_', 'gw': 'gw_', 'general': 'general_'
        }

        config = configparser.ConfigParser()
        config.optionxform = str

        for section_name, prefix in section_map.items():
            section_content = {}
            for flat_key, value in json_obj.items():
                if flat_key.startswith(prefix):
                    new_key = flat_key[len(prefix):]
                    section_content[new_key] = str(value)
            if section_content:
                config[section_name] = section_content

        with StringIO() as output:
            config.write(output)
            return output.getvalue()

    def validate(self, raw_str):
        raw_str = raw_str.strip()
        json_obj = self._extract_json(raw_str)
        if not json_obj:
            return False, self.errors
        component_id = json_obj.get("id")

        if not self._validate_schema(json_obj):
            return False, self.errors

        srate = json_obj.get("rf_srate")
        if isinstance(srate, (int, float)) and srate <= 0:
            self.errors.append("rf_srate must be > 0")

        txg = json_obj.get("rf_tx_gain")
        if isinstance(txg, (int, float)) and not (0 <= txg <= 90):
            self.errors.append("rf_tx_gain must be between 0 and 90")

        rxg = json_obj.get("rf_rx_gain")
        if isinstance(rxg, (int, float)) and not (0 <= rxg <= 90):
            self.errors.append("rf_rx_gain must be between 0 and 90")

        prb = json_obj.get("rat_nr_nof_prb")
        prb_max = json_obj.get("rat_nr_max_nof_prb")
        if isinstance(prb, int) and prb <= 0:
            self.errors.append("rat_nr_nof_prb must be > 0")
        if isinstance(prb_max, int) and prb_max <= 0:
            self.errors.append("rat_nr_max_nof_prb must be > 0")
        if isinstance(prb, int) and isinstance(prb_max, int) and prb_max < prb:
            self.errors.append("rat_nr_max_nof_prb must be >= rat_nr_nof_prb")

        # Optional mapping: if srate ≈ 23.04e6 or 30.72e6 then PRB should be 106
        if isinstance(srate, (int, float)) and isinstance(prb, int):
            if abs(srate - 23.04e6) < 1e5 or abs(srate - 30.72e6) < 1e5:
                if prb != 106:
                    self.errors.append("rat_nr_nof_prb must be 106 for rf_srate near 23.04e6 or 30.72e6")

        if self.errors:
            return False, self.errors

        config_str = self._json_to_config(json_obj)
        if not config_str:
            self.errors.append("Converting to configuration string failed")
            return False, self.errors

        return True, {"id": component_id, "type": "rtue", "config_str": config_str}



class SnifferValidator(Validator):
    def __init__(self):
        super().__init__()

        self.schema = {
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

    def _json_to_config(self, json_obj):
        json_obj.pop('id', None)
        return yaml.dump(json_obj, sort_keys=False, indent=2)

    def validate(self):
        raw_str = raw_str.strip()
        json_obj = self._extract_json(raw_str)
        if not json_obj:
            return False, self.errors

        if not self._validate_schema(json_obj):
            return False, self.errors

        component_id = json_obj.get("id")

        if json_obj.get("sample_rate", 0) <= 0:
            self.errors.append("sample_rate must be > 0")
        if json_obj.get("pdcch_num_prbs", 0) <= 0:
            self.errors.append("pdcch_num_prbs must be > 0")
        if not (0 <= json_obj.get("ssb_numerology") <= 4):
            self.errors.append("ssb_numerology must be >= 0 and <= 4")

        # NR band membership: FR1 or FR2
        f = json_obj.get("frequency")
        if isinstance(f, (int, float)):
            in_fr1 = 410e6 <= f <= 7125e6
            in_fr2 = 24.25e9 <= f <= 52.6e9
            if not (in_fr1 or in_fr2):
                self.errors.append("frequency must be inside NR FR1 (410e6–7.125e9) or FR2 (24.25e9–52.6e9)")

        # CORESET duration must be 1, 2, or 3
        dur = json_obj.get("pdcch_coreset_duration")
        if isinstance(dur, int) and dur not in (1, 2, 3):
            self.errors.append("pdcch_coreset_duration must be one of {1, 2, 3}")

        # Range parameters must satisfy start ≤ end
        sid0 = json_obj.get("pdcch_scrambling_id_start")
        sid1 = json_obj.get("pdcch_scrambling_id_end")
        if isinstance(sid0, int) and isinstance(sid1, int) and sid0 > sid1:
            self.errors.append("pdcch_scrambling_id_start must be <= pdcch_scrambling_id_end")

        rnti0 = json_obj.get("pdcch_rnti_start")
        rnti1 = json_obj.get("pdcch_rnti_end")
        if isinstance(rnti0, int) and isinstance(rnti1, int) and rnti0 > rnti1:
            self.errors.append("pdcch_rnti_start must be <= pdcch_rnti_end")

        # Fixed-length lists where applicable
        dci = json_obj.get("pdcch_dci_sizes_list")
        if isinstance(dci, list) and len(dci) != 2:
            self.errors.append("pdcch_dci_sizes_list must have exactly 2 elements")

        al_thr = json_obj.get("pdcch_AL_corr_thresholds")
        if isinstance(al_thr, list) and len(al_thr) != 5:
            self.errors.append("pdcch_AL_corr_thresholds must have exactly 5 elements")

        al_n = json_obj.get("pdcch_num_candidates_per_AL")
        if isinstance(al_n, list) and len(al_n) != 5:
            self.errors.append("pdcch_num_candidates_per_AL must have exactly 5 elements")

        if self.errors:
            return False, self.errors

        config_str = self._json_to_config(json_obj)
        if not config_str:
            self.errors.append("Converting to configuration string failed")
            return False, self.errors

        return True, {"id": component_id, "type": "sniffer", "config_str": config_str}


class JammerValidator(Validator);
    def __init__(self):
        super().__init__()

        self.schema = {
            "id": str, "center_frequency": (float, int), "bandwidth": (float, int),
            "amplitude": (float, int), "amplitude_width": (float, int),
            "initial_phase": (float, int), "sampling_freq": (float, int),
            "num_samples": int, "output_iq_file": str, "output_csv_file": str,
            "write_iq": bool, "write_csv": bool, "tx_gain": (float, int), "device_args": str
        }

    def _json_to_config(self, json_obj):
        sniffer_section = {}
        pdcch_section = {}

        for key, value in json_obj.items():
            if key.startswith("pdcch_"):
                new_key = key.replace("pdcch_", "", 1)
                pdcch_section[new_key] = value
            elif key in ["file_path", "sample_rate", "frequency", "nid_1", "ssb_numerology"]:
                sniffer_section[key] = value
        final_toml_structure = {"sniffer": sniffer_section, "pdcch": [pdcch_section]}
        return toml.dumps(final_toml_structure)

    def validate(self):
        raw_str = raw_str.strip()
        json_obj = self._extract_json(raw_str)
        if not json_obj:
            return False, self.errors

        if not self._validate_schema(json_obj):
            return False, self.errors

        component_id = json_obj.get("id")

        if json_obj.get("bandwidth", 0) <= 0:
            self.errors.append("bandwidth must be > 0")
        amp = json_obj.get("amplitude", -1)
        if not (0.0 <= amp <= 1.0):
            self.errors.append("amplitude must be between 0 and 1")
        if json_obj.get("tx_gain", -1) < 0 or json_obj.get("tx_gain", 0) > 90:
            self.errors.append("tx_gain must be between 0 and 90")

        # Nyquist for generation
        sf = json_obj.get("sampling_freq"); bw = json_obj.get("bandwidth")
        if isinstance(sf, (int, float)) and isinstance(bw, (int, float)):
            if sf < 2.0 * bw:
                self.errors.append("sampling_freq must be at least 2x bandwidth")

        # Frequency must be positive and within a broad RF envelope
        f0 = json_obj.get("center_frequency")
        if isinstance(f0, (int, float)):
            if f0 <= 0:
                self.errors.append("center_frequency must be > 0")
            else:
                in_fr1 = 410e6 <= f0 <= 7125e6
                in_fr2 = 24.25e9 <= f0 <= 52.6e9
                if not (in_fr1 or in_fr2):
                    self.errors.append("center_frequency must be inside NR FR1 (410e6–7.125e9) or FR2 (24.25e9–52.6e9)")

        # Hardware gating (simple detection via device_args)
        dev = json_obj.get("device_args", "") or ""
        dev_lower = dev.lower()

        # USRP B200-family constraints
        if "b200" in dev_lower or "b210" in dev_lower:
            if isinstance(f0, (int, float)):
                if f0 > 6e9:
                    self.errors.append("center_frequency exceeds B200-family tuning range (<= 6e9)")
                in_fr2 = 24.25e9 <= f0 <= 52.6e9
                if in_fr2:
                    self.errors.append("B200-family cannot operate in NR FR2 (24.25e9–52.6e9)")
            if isinstance(sf, (int, float)) and sf > 61.44e6:
                self.errors.append("sampling_freq exceeds B200-family practical maximum (~61.44e6)")
            if isinstance(bw, (int, float)) and bw > 56e6:
                self.errors.append("bandwidth exceeds B200-family front-end practical limit (~56e6)")

        # Basic sanity on num_samples
        ns = json_obj.get("num_samples", 0)
        if isinstance(ns, int) and ns <= 0:
            self.errors.append("num_samples must be > 0")

        if self.errors:
            return False, self.errors

        config_str = self._json_to_config(json_obj)
        if not config_str:
            return False, self.errors

        return True, {"id": component_id, "type": "jammer", "config_str": config_str}
