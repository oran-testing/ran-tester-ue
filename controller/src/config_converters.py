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
        'ue': 'ue_',
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
        'general': 'general_',
        'recon': 'recon_'
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
        "attack_type": str,
        "center_frequency": (int, float),
        "bandwidth": (int, float),
        "amplitude": (int, float),
        "amplitude_width": (int, float),
        "initial_phase": (int, float),
        "sampling_freq": (int, float),
        "num_samples": int,
        "tx_gain": (int, float),
        "device_args": str,
        "tone_offset_hz": (int, float),
        "burst_duration_ms": (int, float),
        "idle_duration_ms": (int, float),
        "jam_bandwidth_hz": (int, float),
        "num_tones": int,
        "write_iq": bool,
        "write_csv": bool,
        "output_iq_file": str,
        "output_csv_file": str,
        "enable_autoconfigure": bool
    }

    VALID_ATTACK_TYPES = {"barrage", "constant", "random"}

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

        if 'attack_type' in json_obj:
            if json_obj['attack_type'] not in self.VALID_ATTACK_TYPES:
                errors.append(
                    f"attack_type must be one of: {', '.join(sorted(self.VALID_ATTACK_TYPES))}"
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

        if json_obj.get('attack_type') == 'random':
            if 'burst_duration_ms' in json_obj and json_obj['burst_duration_ms'] <= 0:
                errors.append("burst_duration_ms must be > 0 for random attack type")
            if 'idle_duration_ms' in json_obj and json_obj['idle_duration_ms'] <= 0:
                errors.append("idle_duration_ms must be > 0 for random attack type")

        if json_obj.get('attack_type') == 'constant':
            if 'tone_offset_hz' in json_obj:
                if abs(json_obj['tone_offset_hz']) > json_obj.get('sampling_freq', float('inf')) / 2:
                    errors.append("tone_offset_hz must be within +/- sampling_freq/2")
            if 'jam_bandwidth_hz' in json_obj and json_obj['jam_bandwidth_hz'] <= 0:
                errors.append("jam_bandwidth_hz must be > 0 for constant attack type")

        return errors

    def from_json(self, json_obj: dict) -> str:
        errors = self.validate(json_obj)
        if errors:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        config_data = {k: v for k, v in json_obj.items() if k != 'id'}

        return yaml.dump(config_data, sort_keys=False, indent=2)


class RaSpoofConfigConverter(ConfigConverter):
    """Converts JSON to YAML format for RA Spoof (PRACH injector)"""

    REQUIRED_KEYS = [
        'id', 'tx_gain_db', 'tx_device_args',
        'influx_host', 'influx_org', 'influx_token', 'influx_bucket'
    ]

    SCHEMA = {
        "id": str,
        "tx_gain_db": (int, float),
        "tx_preamble_index": int,
        "tx_device_args": str,
        "influx_host": str,
        "influx_port": int,
        "influx_org": str,
        "influx_token": str,
        "influx_bucket": str,
        "influx_data_id": str,
        "cfo_correct": bool,
        "cfo_sign": int,
        "cfo_manual_hz": (int, float),
        "timing_tx_offset_us": (int, float),
        "timing_rx_to_tx_cal_us": (int, float),
        "timing_ssb_first_symbol_override": int,
        "freq_msg1_freq_start_override": int,
        "freq_msg1_fdm_override": int,
        "run_continuous": bool,
        "run_max_tx": int,
        "run_resync_every": int,
        "run_gnb_log_path": str,
        "run_autotune": bool,
        "flood_enabled": bool,
        "flood_num_preambles": int,
        "flood_strategy": str,
        "flood_power_backoff_db": (int, float),
        "flood_slm_candidates": int,
        "multi_ro_freq_pos_count": int
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

        if 'tx_gain_db' in json_obj:
            if not (0 <= json_obj['tx_gain_db'] <= 90):
                errors.append("tx_gain_db must be between 0 and 90")

        if 'tx_preamble_index' in json_obj:
            if not (0 <= json_obj['tx_preamble_index'] <= 63):
                errors.append("tx_preamble_index must be between 0 and 63")

        if 'flood_num_preambles' in json_obj:
            if not (1 <= json_obj['flood_num_preambles'] <= 64):
                errors.append("flood_num_preambles must be between 1 and 64")

        if 'flood_strategy' in json_obj:
            if json_obj['flood_strategy'] not in ('superimpose', 'cycle'):
                errors.append("flood_strategy must be 'superimpose' or 'cycle'")

        if 'cfo_sign' in json_obj:
            if json_obj['cfo_sign'] not in (-1, 1):
                errors.append("cfo_sign must be -1 or 1")

        if 'multi_ro_freq_pos_count' in json_obj:
            if json_obj['multi_ro_freq_pos_count'] < 1:
                errors.append("multi_ro_freq_pos_count must be >= 1")

        if 'influx_port' in json_obj:
            if not (1 <= json_obj['influx_port'] <= 65535):
                errors.append("influx_port must be between 1 and 65535")

        return errors

    def from_json(self, json_obj: dict) -> str:
        errors = self.validate(json_obj)
        if errors:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        config_data = {k: v for k, v in json_obj.items() if k != 'id'}

        config = {}
        flat_to_nested = {
            "tx_gain_db": ("tx", "gain_db"),
            "tx_preamble_index": ("tx", "preamble_index"),
            "tx_device_args": ("tx", "device_args"),
            "cfo_correct": ("cfo", "correct"),
            "cfo_sign": ("cfo", "sign"),
            "cfo_manual_hz": ("cfo", "manual_hz"),
            "timing_tx_offset_us": ("timing", "tx_offset_us"),
            "timing_rx_to_tx_cal_us": ("timing", "rx_to_tx_cal_us"),
            "timing_ssb_first_symbol_override": ("timing", "ssb_first_symbol_override"),
            "freq_msg1_freq_start_override": ("freq", "msg1_freq_start_override"),
            "freq_msg1_fdm_override": ("freq", "msg1_fdm_override"),
            "run_continuous": ("run", "continuous"),
            "run_max_tx": ("run", "max_tx"),
            "run_resync_every": ("run", "resync_every"),
            "run_gnb_log_path": ("run", "gnb_log_path"),
            "run_autotune": ("run", "autotune"),
            "flood_enabled": ("flood", "enabled"),
            "flood_num_preambles": ("flood", "num_preambles"),
            "flood_strategy": ("flood", "strategy"),
            "flood_power_backoff_db": ("flood", "power_backoff_db"),
            "flood_slm_candidates": ("flood", "slm_candidates"),
            "multi_ro_freq_pos_count": ("multi_ro", "freq_pos_count"),
            "influx_host": ("influx", "host"),
            "influx_port": ("influx", "port"),
            "influx_org": ("influx", "org"),
            "influx_token": ("influx", "token"),
            "influx_bucket": ("influx", "bucket"),
            "influx_data_id": ("influx", "data_id"),
        }

        for flat_key, value in config_data.items():
            if flat_key in flat_to_nested:
                section, key = flat_to_nested[flat_key]
                if section not in config:
                    config[section] = {}
                config[section][key] = value
            else:
                config[flat_key] = value

        return yaml.dump(config, sort_keys=False, indent=2)


CONFIG_CONVERTERS = {
    "rtue": RTUEConfigConverter(),
    "sniffer": SnifferConfigConverter(),
    "sni5gect": Sni5gectConfigConverter(),
    "jammer": JammerConfigConverter(),
    "ssb_spoofer": Sni5gectConfigConverter(),
    "uuagent": RTUEConfigConverter(),
    "ra_spoof": RaSpoofConfigConverter(),
}
