import configparser
import logging
from io import StringIO
import re

from validator import Validator


class UuagentValidator(Validator):
    def __init__(self):
        super().__init__()
        self.required_keys = [
            "id", "rf.type", "rf.rx_freq", "rf.srate", "rf.rx_gain", "rf.tx_gain", "rf.num_samples", "rf.iq_file"
        ]
        self.schema = {
            "id": str, "rf.type": str, "rf.rx_freq": (float, int), "rf.srate": (float, int),
            "rf.rx_gain": int, "rf.tx_gain": int, "rf.num_samples": int, "rf.iq_file": str, "rf.device_args": str,
            }
    def _json_to_config(self, json_obj: dict) -> str:
        config_obj = json_obj.copy()
        config_obj.pop("id", None)

        config_lines = []
        for key, value in config_obj.items():
            config_lines.append(f"{key} = {value}")
        return "\n".join(config_lines)


    def validate(self, raw_str):
        raw_str = raw_str.strip()
        json_obj = self._extract_json(raw_str)
        if not json_obj:
            return False, self.errors
        if not self._validate_schema(json_obj):
            return False, self.errors
        
        component_id = json_obj.get("id")
        #type check
        rf_type = json_obj.get("rf.type")
        if rf_type not in ["uhd", "zmq"]:
            self.errors.append("rf.type must be 'uhd' or 'zmq'")
        #frequency check

        rx_freq = json_obj.get("rf.rx_freq")
        if isinstance(rx_freq, (int, float)):
            if rx_freq <= 0:
                self.errors.append("rf.rx_freq 0 error")
            else:
                in_fr1 = 410e6 <= rx_freq <= 7125e6
                in_fr2 = 24.25e9 <= rx_freq <= 52.6e9
                if not (in_fr1 or in_fr2):
                    self.errors.append("rf.rx_freq must be inside NR FR1 (410e6–7.125e9) or FR2 (24.25e9–52.6e9)")
        #sample rate check
        srate = json_obj.get("rf.srate")
        if isinstance(srate, (int, float)) and srate <= 0:
            self.errors.append("rf.srate must be > 0")
        #gain checks
        rx_gain = json_obj.get("rf.rx_gain")
        if isinstance(rx_gain, (int, float)):
            if not (0 <= rx_gain <= 90):
                self.errors.append("rf.rx_gain must be between 0 and 90 dB")

        tx_gain = json_obj.get("rf.tx_gain")
        if isinstance(tx_gain, (int, float)):
            if not (0 <= tx_gain <= 90):
                self.errors.append("rf.tx_gain must be between 0 and 90 dB")
        
        num_samples = json_obj.get("rf.num_samples")
        if isinstance(num_samples, int):
            if num_samples <= 0:
                self.errors.append("rf.num_samples must be > 0")
            elif num_samples > 10000000:
                self.errors.append("rf.num_samples must be <= 10000000")

        #validate file path
        iq_file = json_obj.get("rf.iq_file", "")
        if not iq_file:
            self.errors.append("rf.iq_file cannot be empty")
        elif not iq_file.startswith("/output/"):
            self.errors.append("rf.iq_file should be in /output/ directory for docker deployment")

        #hardware specific for uhd type and b200
        device_args = json_obj.get("rf.device_args", "")
        if rf_type == "uhd" and "b200" in device_args:
            # B200 specific constraints
            if isinstance(rx_freq, (int, float)) and rx_freq > 6e9:
                self.errors.append("B200-family devices cannot operate above 6 GHz")
            if isinstance(srate, (int, float)) and srate > 61.44e6:
                self.errors.append("B200-family sampling rate should not exceed ~61.44 MHz")
        
        #gen catch all
        if self.errors:
            return False, self.errors
        
        config_str = self._json_to_config(json_obj)
        if not config_str:
            return False, self.errors

        return True, {"id": component_id, "type": "uu_agent", "config_str": config_str}
