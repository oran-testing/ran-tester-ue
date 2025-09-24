import configparser
import logging
from io import StringIO
import re

from validator import Validator

class RTUEValidator(Validator):
    def __init__(self):
        super().__init__()

        self.required_keys = [
            'id', 'rf_srate', 'rf_tx_gain', 'rf_rx_gain', 'rat_nr_bands',
            'rat_nr_nof_prb', 'usim_imsi', 'nas_apn'
        ]

        self.schema = {
            "id": str, "rf_freq_offset": int, "rf_tx_gain": int, "rf_rx_gain": int,
            "rf_srate": (float, int), "rf_nof_antennas": int, "rf_device_name": str,
            "rf_device_args": str, "rat_eutra_dl_earfcn": int,
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

    def _parse_rf_args(self, args: str) -> dict:
        result = {}
        for part in args.split(','):
            if '=' not in part:
                continue
            key, value = part.split('=', 1)
            result[key.strip()] = value.strip()
        return result

    def _validate_uhd_args(self, args: str):
        parsed = self._parse_rf_args(args)

        if 'addr' not in parsed:
            self.errors.append("Missing 'addr' in UHD args.")

    def _validate_zmq_args(self, args: str):
        parsed = self._parse_rf_args(args)

        if 'tx_port' not in parsed:
            self.errors.append("Missing 'tx_port' in ZMQ args.")

        if 'rx_port' not in parsed:
            self.errors.append("Missing 'rx_port' in ZMQ args.")

        for port in ['tx_port', 'rx_port']:
            if port in parsed:
                if not re.match(r'^tcp://[\d\.]+:\d+$', parsed[port]):
                    self.errors.append(f"Invalid format for {port}: {parsed[port]}")

    def validate(self, raw_str):
        raw_str = raw_str.strip()
        json_obj = self._extract_json(raw_str)
        if not json_obj:
            return False, self.errors
        component_id = json_obj.get("id")

        logging.info(f"EXEC JSON: {json_obj}")

        if not self._validate_schema(json_obj):
            return False, self.errors

        rf_type = json_obj.get("rf_device_name")
        if rf_type == "uhd":
            self._validate_uhd_args(json_obj.get("rf_device_args"))
        elif rf_type == "zmq":
            self._validate_zmq_args(json_obj.get("rf_device_args"))
        else:
            self.errors.append(f"Unknown rf_device_name {rf_type}. Valid options are uhd, zmq")

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




