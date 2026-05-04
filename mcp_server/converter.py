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
        "uuagent": "conf"
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


CONVERTERS = {
    "rtue": convert_rtue,
    "uuagent": convert_rtue,
    "sniffer": convert_sniffer,
    "sni5gect": convert_yaml_config,
    "jammer": convert_yaml_config,
    "ssb_spoofer": convert_yaml_config
}
