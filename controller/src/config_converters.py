import yaml
import toml
import configparser
from io import StringIO


class ConfigConverter:
    """Base class for config format converters"""

    def from_json(self, json_obj: dict) -> str:
        raise NotImplementedError

    def validate(self, json_obj: dict) -> list:
        raise NotImplementedError


class RTUEConfigConverter(ConfigConverter):
    """Converts JSON to .conf (INI-style) format for RTUE"""

    SECTION_MAP = {
        'rf': 'rf_',
        'rat.eutra': 'rat_eutra_',
        'rat.nr': 'rat_nr_',
        'pcap': 'pcap_',
        'log': 'log_',
        'usim': 'usim_',
        'rrc': 'rrc_',
        'nas': 'nas_',
        'gui': 'gui_',
        'gw': 'gw_',
        'general': 'general_'
    }

    REQUIRED_KEYS = [
        'id', 'rf_srate', 'rf_tx_gain', 'rf_rx_gain',
        'rat_nr_bands', 'rat_nr_nof_prb', 'usim_imsi', 'nas_apn'
    ]

    SCHEMA = {
        "id": str,
        "rf_freq_offset": int,
        "rf_tx_gain": int,
        "rf_rx_gain": int,
        "rf_srate": (int, float),
        "rf_nof_antennas": int,
        "rf_device_name": str,
        "rf_device_args": str,
        "rf_time_adv_nsamples": int,
        "rat_eutra_dl_earfcn": int,
        "rat_eutra_nof_carriers": int,
        "rat_nr_bands": int,
        "rat_nr_nof_carriers": int,
        "rat_nr_max_nof_prb": int,
        "rat_nr_nof_prb": int,
        "pcap_enable": str,
        "pcap_mac_filename": str,
        "pcap_mac_nr_filename": str,
        "pcap_nas_filename": str,
        "log_all_level": str,
        "log_phy_lib_level": str,
        "log_all_hex_limit": int,
        "log_filename": str,
        "log_file_max_size": int,
        "usim_mode": str,
        "usim_algo": str,
        "usim_opc": str,
        "usim_k": str,
        "usim_imsi": str,
        "usim_imei": str,
        "rrc_release": int,
        "rrc_ue_category": int,
        "nas_apn": str,
        "nas_apn_protocol": str,
        "gui_enable": bool,
        "gw_ip_devname": str,
        "gw_ip_netmask": str,
        "general_metrics_influxdb_enable": bool,
        "general_metrics_influxdb_url": str,
        "general_metrics_influxdb_port": int,
        "general_metrics_influxdb_org": str,
        "general_metrics_influxdb_token": str,
        "general_metrics_influxdb_bucket": str,
        "general_metrics_period_secs": float,
        "general_ue_data_identifier": str
    }

    def validate(self, json_obj: dict) -> list:
        errors = []

        for key in self.REQUIRED_KEYS:
            if key not in json_obj:
                errors.append(f"Missing required key: '{key}'")

        for key, value in json_obj.items():
            if key in self.SCHEMA:
                expected_type = self.SCHEMA[key]
                if not isinstance(value, expected_type):
                    errors.append(
                        f"Invalid type for '{key}': expected {expected_type}, got {type(value).__name__}"
                    )

        if 'rf_tx_gain' in json_obj:
            if not (0 <= json_obj['rf_tx_gain'] <= 90):
                errors.append("rf_tx_gain must be between 0 and 90")

        if 'rf_rx_gain' in json_obj:
            if not (0 <= json_obj['rf_rx_gain'] <= 90):
                errors.append("rf_rx_gain must be between 0 and 90")

        if 'rf_srate' in json_obj and json_obj['rf_srate'] <= 0:
            errors.append("rf_srate must be > 0")

        if 'rat_nr_nof_prb' in json_obj and json_obj['rat_nr_nof_prb'] <= 0:
            errors.append("rat_nr_nof_prb must be > 0")

        if 'rat_nr_max_nof_prb' in json_obj and json_obj['rat_nr_max_nof_prb'] <= 0:
            errors.append("rat_nr_max_nof_prb must be > 0")

        if 'usim_imsi' in json_obj:
            import re
            if not re.match(r'^[0-9]{15}$', json_obj['usim_imsi']):
                errors.append("usim_imsi must be 15 digits")

        return errors

    def from_json(self, json_obj: dict) -> str:
        errors = self.validate(json_obj)
        if errors:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        config_data = {k: v for k, v in json_obj.items() if k != 'id'}

        config = configparser.ConfigParser()
        config.optionxform = str

        for section_name, prefix in self.SECTION_MAP.items():
            section_content = {}
            for flat_key, value in config_data.items():
                if flat_key.startswith(prefix):
                    new_key = flat_key[len(prefix):]
                    section_content[new_key] = str(value)
            if section_content:
                config[section_name] = section_content

        with StringIO() as output:
            config.write(output)
            return output.getvalue()


class SnifferConfigConverter(ConfigConverter):
    """Converts JSON to TOML format for Sniffer"""

    REQUIRED_KEYS = [
        'id', 'file_path', 'sample_rate', 'frequency',
        'nid_1', 'ssb_numerology'
    ]

    SCHEMA = {
        "id": str,
        "file_path": str,
        "sample_rate": (int, float),
        "frequency": (int, float),
        "nid_1": int,
        "ssb_numerology": int,
        "pdcch_coreset_id": int,
        "pdcch_subcarrier_offset": int,
        "pdcch_num_prbs": int,
        "pdcch_numerology": int,
        "pdcch_dci_sizes_list": list,
        "pdcch_scrambling_id_start": int,
        "pdcch_scrambling_id_end": int,
        "pdcch_rnti_start": int,
        "pdcch_rnti_end": int,
        "pdcch_interleaving_pattern": str,
        "pdcch_coreset_duration": int,
        "pdcch_AL_corr_thresholds": list,
        "pdcch_num_candidates_per_AL": list
    }

    def validate(self, json_obj: dict) -> list:
        errors = []

        for key in self.REQUIRED_KEYS:
            if key not in json_obj:
                errors.append(f"Missing required key: '{key}'")

        for key, value in json_obj.items():
            if key in self.SCHEMA:
                expected_type = self.SCHEMA[key]
                if not isinstance(value, expected_type):
                    errors.append(
                        f"Invalid type for '{key}': expected {expected_type}, got {type(value).__name__}"
                    )

        if 'sample_rate' in json_obj and json_obj['sample_rate'] <= 0:
            errors.append("sample_rate must be > 0")

        if 'frequency' in json_obj:
            f = json_obj['frequency']
            in_fr1 = 410e6 <= f <= 7125e6
            in_fr2 = 24.25e9 <= f <= 52.6e9
            if not (in_fr1 or in_fr2):
                errors.append("frequency must be in FR1 (410e6-7.125e9) or FR2 (24.25e9-52.6e9)")

        if 'ssb_numerology' in json_obj:
            if not (0 <= json_obj['ssb_numerology'] <= 4):
                errors.append("ssb_numerology must be between 0 and 4")

        if 'pdcch_coreset_duration' in json_obj:
            if json_obj['pdcch_coreset_duration'] not in (1, 2, 3):
                errors.append("pdcch_coreset_duration must be 1, 2, or 3")

        return errors

    def from_json(self, json_obj: dict) -> str:
        errors = self.validate(json_obj)
        if errors:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        config_data = {k: v for k, v in json_obj.items() if k != 'id'}

        sniffer_section = {}
        pdcch_section = {}

        for key, value in config_data.items():
            if key.startswith("pdcch_"):
                new_key = key.replace("pdcch_", "", 1)
                pdcch_section[new_key] = value
            elif key in ["file_path", "sample_rate", "frequency", "nid_1", "ssb_numerology"]:
                sniffer_section[key] = value

        config = {
            "sniffer": sniffer_section,
            "pdcch": [pdcch_section] if pdcch_section else []
        }

        return toml.dumps(config)


class Sni5gectConfigConverter(ConfigConverter):
    """Converts JSON to YAML format for Sni5gect"""

    REQUIRED_KEYS = ['id']

    def validate(self, json_obj: dict) -> list:
        errors = []

        for key in self.REQUIRED_KEYS:
            if key not in json_obj:
                errors.append(f"Missing required key: '{key}'")

        return errors

    def from_json(self, json_obj: dict) -> str:
        errors = self.validate(json_obj)
        if errors:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        config_data = {k: v for k, v in json_obj.items() if k != 'id'}

        return yaml.dump(config_data, sort_keys=False, indent=2)


class JammerConfigConverter(ConfigConverter):
    """Converts JSON to YAML format for Jammer"""

    REQUIRED_KEYS = [
        'id', 'center_frequency', 'bandwidth', 'amplitude',
        'sampling_freq', 'tx_gain', 'device_args'
    ]

    SCHEMA = {
        "id": str,
        "center_frequency": (int, float),
        "bandwidth": (int, float),
        "amplitude": (int, float),
        "amplitude_width": (int, float),
        "initial_phase": (int, float),
        "sampling_freq": (int, float),
        "num_samples": int,
        "tx_gain": (int, float),
        "device_args": str,
        "write_iq": bool,
        "write_csv": bool,
        "output_iq_file": str,
        "output_csv_file": str
    }

    def validate(self, json_obj: dict) -> list:
        errors = []

        for key in self.REQUIRED_KEYS:
            if key not in json_obj:
                errors.append(f"Missing required key: '{key}'")

        for key, value in json_obj.items():
            if key in self.SCHEMA:
                expected_type = self.SCHEMA[key]
                if not isinstance(value, expected_type):
                    errors.append(
                        f"Invalid type for '{key}': expected {expected_type}, got {type(value).__name__}"
                    )

        if 'center_frequency' in json_obj:
            f0 = json_obj['center_frequency']
            if f0 <= 0:
                errors.append("center_frequency must be > 0")
            else:
                in_fr1 = 410e6 <= f0 <= 7125e6
                in_fr2 = 24.25e9 <= f0 <= 52.6e9
                if not (in_fr1 or in_fr2):
                    errors.append("center_frequency must be in FR1 (410e6-7.125e9) or FR2 (24.25e9-52.6e9)")

        if 'tx_gain' in json_obj:
            if not (0 <= json_obj['tx_gain'] <= 90):
                errors.append("tx_gain must be between 0 and 90")

        if 'amplitude' in json_obj:
            if not (0 <= json_obj['amplitude'] <= 1.0):
                errors.append("amplitude must be between 0 and 1")

        if 'bandwidth' in json_obj and json_obj['bandwidth'] <= 0:
            errors.append("bandwidth must be > 0")

        if 'sampling_freq' in json_obj and 'bandwidth' in json_obj:
            if json_obj['sampling_freq'] < 2.0 * json_obj['bandwidth']:
                errors.append("sampling_freq must be at least 2x bandwidth")

        return errors

    def from_json(self, json_obj: dict) -> str:
        errors = self.validate(json_obj)
        if errors:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        config_data = {k: v for k, v in json_obj.items() if k != 'id'}

        return yaml.dump(config_data, sort_keys=False, indent=2)


CONFIG_CONVERTERS = {
    "rtue": RTUEConfigConverter(),
    "sniffer": SnifferConfigConverter(),
    "sni5gect": Sni5gectConfigConverter(),
    "jammer": JammerConfigConverter(),
    "ssb_spoofer": Sni5gectConfigConverter(),
    "uuagent": RTUEConfigConverter(),
}
