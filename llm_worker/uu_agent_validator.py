import configparser
import logging
from io import StringIO
import re

from validator import Validator


class UuagentValidator(Validator):
    def __init__(self):
        super().__init__()
        self.required_keys = [
            "id", "rf_type", "rf_rx_freq", "rf_srate", "rf_rx_gain", "rf_tx_gain", "rf_num_samples", "rf_iq_file"
        ]
        self.schema = {
            "id": str, "rf_type": str, "rf_rx_freq": (float, int), "rf_srate": (float, int),
            "rf_rx_gain": int, "rf_tx_gain": int, "rf_num_samples": int, "rf_iq_file": str
            }
    def _json_to_config(self, json_obj: dict) -> str:
        config_obj = json_obj.copy()
        config_obj.pop("id", None)

        config_lines = []


    def validate(self, raw_str):
        raw_str = raw_str.strip()
        return True

