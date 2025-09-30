import toml

from validator import Validator

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


