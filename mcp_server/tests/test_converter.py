import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from converter import (
    ConfigConverter,
    convert_rtue,
    convert_sniffer,
    convert_yaml_config,
    convert_ofh_attacker,
    convert_sstorm,
    convert_oai_ue,
    validate_rtue,
    validate_sniffer,
    validate_jammer,
)


class TestConvertRTUE:
    def test_basic_conversion(self):
        config = {
            "id": "test_ue_1",
            "rf_srate": 23040000,
            "rf_tx_gain": 60,
            "rf_rx_gain": 40,
            "rat_nr_bands": 3,
            "rat_nr_nof_prb": 106,
            "usim_imsi": "001010123456789",
            "nas_apn": "internet",
        }
        result, ext = ConfigConverter.convert("rtue", config)
        assert ext == "conf"
        assert "[rf]" in result
        assert "srate = 23040000" in result
        assert "tx_gain = 60" in result
        assert "rx_gain = 40" in result
        assert "[rat.nr]" in result
        assert "bands = 3" in result
        assert "nof_prb = 106" in result
        assert "[usim]" in result
        assert "imsi = 001010123456789" in result
        assert "[nas]" in result
        assert "apn = internet" in result


class TestConvertSniffer:
    def test_basic_conversion(self):
        config = {
            "id": "sniffer_1",
            "file_path": "/tmp/capture.pcap",
            "sample_rate": 23040000,
            "frequency": 1842500000,
            "nid_1": 0,
            "ssb_numerology": 0,
        }
        result, ext = ConfigConverter.convert("sniffer", config)
        assert ext == "toml"
        assert "sample_rate = 23040000" in result
        assert "frequency = 1842500000" in result
        assert "file_path = " in result
        assert "nid_1 = 0" in result
        assert "ssb_numerology = 0" in result

    def test_with_pdcch(self):
        config = {
            "id": "sniffer_1",
            "file_path": "/tmp/capture.pcap",
            "sample_rate": 23040000,
            "frequency": 1842500000,
            "nid_1": 0,
            "ssb_numerology": 0,
            "pdcch_coreset_duration": 2,
            "pdcch_num_prbs": 48,
        }
        result, ext = ConfigConverter.convert("sniffer", config)
        assert "[[pdcch]]" in result
        assert "coreset_duration = 2" in result
        assert "num_prbs = 48" in result


class TestConvertYamlConfig:
    def test_basic_conversion(self):
        config = {"id": "test_1", "key1": "value1", "key2": 42}
        result, ext = ConfigConverter.convert("sni5gect", config)
        assert ext == "yaml"
        assert "key1: value1" in result
        assert "key2: 42" in result
        assert "id:" not in result

    def test_jammer_conversion(self):
        config = {
            "id": "jammer_1",
            "center_frequency": 2400000000,
            "bandwidth": 10000000,
            "amplitude": 0.5,
            "sampling_freq": 30720000,
            "tx_gain": 50,
            "device_args": "type=b200",
        }
        result, ext = ConfigConverter.convert("jammer", config)
        assert ext == "yaml"
        assert "center_frequency: 2400000000" in result
        assert "id:" not in result


class TestConvertOFHAttacker:
    def test_basic_conversion(self):
        config = {
            "id": "ofh_1",
            "injection_points": ["DU", "RU"],
            "du": "enp5s0f1",
            "ru": "enp8s0f0np0",
            "attacker_dir": "/attack_env",
            "results_dir": "./attack_results",
            "duration_seconds": 10,
        }
        result, ext = ConfigConverter.convert("ofh_attacker", config)
        assert ext == "toml"
        assert "DU" in result and "RU" in result
        assert 'du = "enp5s0f1"' in result


class TestConvertSStorm:
    def test_basic_conversion(self):
        config = {
            "id": "sstorm_1",
            "ue_signal_storm": True,
            "rf_srate": 23040000,
            "rf_tx_gain": 70,
            "rf_rx_gain": 40,
        }
        result, ext = ConfigConverter.convert("sstorm", config)
        assert ext == "conf"
        assert "[ue]" in result
        assert "signal_storm = True" in result
        assert "[rf]" in result
        assert "srate = 23040000" in result
        assert "tx_gain = 70" in result


class TestConvertOAIUE:
    def test_basic_conversion(self):
        config = {
            "id": "oai_ue_1",
            "r": "106",
            "numerology": "1",
            "band": "78",
        }
        result, ext = ConfigConverter.convert("oai_ue", config)
        assert ext == "args"
        assert "-r 106" in result
        assert "--numerology 1" in result
        assert "--band 78" in result

    def test_explicit_args(self):
        config = {"id": "oai_ue_1", "args": ["-r", "106", "--band", "78"]}
        result, ext = ConfigConverter.convert("oai_ue", config)
        assert result == "-r 106 --band 78"


class TestValidateRTUE:
    def test_valid_config(self):
        config = {
            "id": "test_ue_1",
            "rf_srate": 23040000,
            "rf_tx_gain": 60,
            "rf_rx_gain": 40,
            "rat_nr_bands": 3,
            "rat_nr_nof_prb": 106,
            "usim_imsi": "001010123456789",
            "nas_apn": "internet",
        }
        errors = ConfigConverter.validate("rtue", config)
        assert errors == []

    def test_missing_required(self):
        config = {"id": "test_ue_1"}
        errors = ConfigConverter.validate("rtue", config)
        assert len(errors) > 0
        assert any("rf_srate" in e for e in errors)

    def test_tx_gain_range(self):
        config = {
            "id": "test_ue_1",
            "rf_srate": 23040000,
            "rf_tx_gain": 100,
            "rf_rx_gain": 40,
            "rat_nr_bands": 3,
            "rat_nr_nof_prb": 106,
            "usim_imsi": "001010123456789",
            "nas_apn": "internet",
        }
        errors = ConfigConverter.validate("rtue", config)
        assert any("rf_tx_gain" in e for e in errors)

    def test_imsi_format(self):
        config = {
            "id": "test_ue_1",
            "rf_srate": 23040000,
            "rf_tx_gain": 60,
            "rf_rx_gain": 40,
            "rat_nr_bands": 3,
            "rat_nr_nof_prb": 106,
            "usim_imsi": "12345",
            "nas_apn": "internet",
        }
        errors = ConfigConverter.validate("rtue", config)
        assert any("imsi" in e for e in errors)


class TestValidateSniffer:
    def test_valid_config(self):
        config = {
            "id": "sniffer_1",
            "file_path": "/tmp/capture.pcap",
            "sample_rate": 23040000,
            "frequency": 1842500000,
            "nid_1": 0,
            "ssb_numerology": 0,
        }
        errors = ConfigConverter.validate("sniffer", config)
        assert errors == []

    def test_frequency_range(self):
        config = {
            "id": "sniffer_1",
            "file_path": "/tmp/capture.pcap",
            "sample_rate": 23040000,
            "frequency": 100000000000,
            "nid_1": 0,
            "ssb_numerology": 0,
        }
        errors = ConfigConverter.validate("sniffer", config)
        assert any("frequency" in e for e in errors)


class TestValidateJammer:
    def test_valid_config(self):
        config = {
            "id": "jammer_1",
            "center_frequency": 2400000000,
            "bandwidth": 10000000,
            "amplitude": 0.5,
            "sampling_freq": 30720000,
            "tx_gain": 50,
            "device_args": "type=b200",
        }
        errors = ConfigConverter.validate("jammer", config)
        assert errors == []

    def test_amplitude_range(self):
        config = {
            "id": "jammer_1",
            "center_frequency": 2400000000,
            "bandwidth": 10000000,
            "amplitude": 1.5,
            "sampling_freq": 30720000,
            "tx_gain": 50,
            "device_args": "type=b200",
        }
        errors = ConfigConverter.validate("jammer", config)
        assert any("amplitude" in e for e in errors)


class TestConfigConverterApi:
    def test_unknown_type(self):
        with pytest.raises(ValueError, match="No converter"):
            ConfigConverter.convert("unknown_type", {"id": "test"})

    def test_validate_unknown_type(self):
        errors = ConfigConverter.validate("unknown_type", {"id": "test"})
        assert len(errors) > 0
        assert "No validator" in errors[0]

    def test_uuagent_uses_rtue(self):
        config = {
            "id": "test_ue_1",
            "rf_srate": 23040000,
            "rf_tx_gain": 60,
            "rf_rx_gain": 40,
            "rat_nr_bands": 3,
            "rat_nr_nof_prb": 106,
            "usim_imsi": "001010123456789",
            "nas_apn": "internet",
        }
        result, ext = ConfigConverter.convert("uuagent", config)
        assert ext == "conf"
        assert "[rf]" in result
