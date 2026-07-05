import yaml
import toml
import configparser
from io import StringIO
from typing import Dict, Any, Tuple


class ConfigConverter:
    """Converts JSON configurations to appropriate formats"""

    FORMAT_MAP = {
        "rtue": "conf",
        "sniffer": "toml",
        "sni5gect": "yaml",
        "jammer": "yaml",
        "ssb_spoofer": "yaml",
        "uuagent": "conf",
        "ra_spoof": "yaml"
    }

    @staticmethod
    def convert(component_type: str, config_json: Dict[str, Any]) -> Tuple[str, str]:
        converter = CONVERTERS.get(component_type)
        if not converter:
            raise ValueError(f"No converter for component type: {component_type}")

        config_string = converter(config_json)
        file_ext = ConfigConverter.FORMAT_MAP.get(component_type, "yaml")

        return config_string, file_ext


def convert_rtue(json_obj: Dict[str, Any]) -> str:
    section_map = {
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

    config = configparser.ConfigParser()
    config.optionxform = str

    for section_name, prefix in section_map.items():
        section_content = {}
        for key, value in json_obj.items():
            if key.startswith(prefix):
                new_key = key[len(prefix):]
                section_content[new_key] = str(value)
        if section_content:
            config[section_name] = section_content

    with StringIO() as output:
        config.write(output)
        return output.getvalue()


def convert_sniffer(json_obj: Dict[str, Any]) -> str:
    sniffer_section = {}
    pdcch_section = {}

    for key, value in json_obj.items():
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


def convert_yaml_config(json_obj: Dict[str, Any]) -> str:
    config_data = {k: v for k, v in json_obj.items() if k != 'id'}
    return yaml.dump(config_data, sort_keys=False, indent=2)


def convert_ra_spoof(json_obj: Dict[str, Any]) -> str:
    config_data = {k: v for k, v in json_obj.items() if k != 'id'}

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

    config = {}
    for flat_key, value in config_data.items():
        if flat_key in flat_to_nested:
            section, key = flat_to_nested[flat_key]
            if section not in config:
                config[section] = {}
            config[section][key] = value
        else:
            config[flat_key] = value

    return yaml.dump(config, sort_keys=False, indent=2)


CONVERTERS = {
    "rtue": convert_rtue,
    "uuagent": convert_rtue,
    "sniffer": convert_sniffer,
    "sni5gect": convert_yaml_config,
    "jammer": convert_yaml_config,
    "ssb_spoofer": convert_yaml_config,
    "ra_spoof": convert_ra_spoof
}
