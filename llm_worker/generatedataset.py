import json
import random
import argparse

# Try importing toml, fallback if not installed
try:
    import toml
    def dict_to_toml(cfg):
        return toml.dumps(cfg)
except ImportError:
    print("WARNING: 'toml' module not found. Using fallback TOML serializer.")

    # Minimal fallback: simple manual conversion for your dict structure.
    # Only works for your config shape — extend if needed.
    def dict_to_toml(cfg):
        lines = []
        for section, content in cfg.items():
            if isinstance(content, dict):
                lines.append(f"[{section}]")
                for k, v in content.items():
                    # For basic types only
                    if isinstance(v, str):
                        lines.append(f'{k} = "{v}"')
                    elif isinstance(v, (int, float, bool)):
                        lines.append(f"{k} = {v}")
                    else:
                        lines.append(f"{k} = {json.dumps(v)}")
                lines.append("")
            elif isinstance(content, list):
                # Assuming list of dicts
                for item in content:
                    lines.append(f"[[{section}]]")
                    for k, v in item.items():
                        if isinstance(v, str):
                            lines.append(f'{k} = "{v}"')
                        elif isinstance(v, (int, float, bool)):
                            lines.append(f"{k} = {v}")
                        else:
                            lines.append(f"{k} = {json.dumps(v)}")
                    lines.append("")
        return "\n".join(lines)

# ── Your existing code ──

file_paths = ["/home/oran-testbed/5g-sniffer/iq_1842MHz_pdcch_traffic.fc32"]
sample_rates = [23040000, 24576000, 19200000]
frequencies = [1842500000, 1860000000, 1885000000]
nid_1_options = [1, 2, 3]
ssb_numerologies = [0, 1]

coreset_ids            = [1, 2, 3]
subcarrier_offsets     = [426, 128, 64]
num_prbs_list          = [30, 50, 100]
numerologies           = [0, 1, 2]
dci_sizes_choices      = [[41], [24, 56], [32]]
scramble_start_choices = [1, 5, 10]
scramble_end_choices   = [10, 20, 30]
rnti_start_choices     = [17921, 20000, 30000]
rnti_end_choices       = [17930, 20010, 30010]
interleaving_patterns  = ["non-interleaved", "interleaved"]
coreset_durations      = [1, 2]
AL_thresholds_choices  = [[1, 0.5, 0.5, 1, 1], [0.8, 0.8, 0.8, 0.8, 0.8]]
num_candidates_choices = [[0, 4, 4, 0, 0], [1, 2, 2, 1, 1]]

prompt_templates = [
    "generate a config file for the sniffer",
    "create a TOML config for the 5G sniffer",
    "please generate a sniffer config file",
    "make me a sniffer_config.toml",
    "output a 5G sniffer config in TOML format"
]

def sample_config():
    return {
        "sniffer": {
            "file_path": random.choice(file_paths),
            "sample_rate": random.choice(sample_rates),
            "frequency": random.choice(frequencies),
            "nid_1": random.choice(nid_1_options),
            "ssb_numerology": random.choice(ssb_numerologies),
        },
        "pdcch": [
            {
                "coreset_id": random.choice(coreset_ids),
                "subcarrier_offset": random.choice(subcarrier_offsets),
                "num_prbs": random.choice(num_prbs_list),
                "numerology": random.choice(numerologies),
                "dci_sizes_list": random.choice(dci_sizes_choices),
                "scrambling_id_start": random.choice(scramble_start_choices),
                "scrambling_id_end": random.choice(scramble_end_choices),
                "rnti_start": random.choice(rnti_start_choices),
                "rnti_end": random.choice(rnti_end_choices),
                "interleaving_pattern": random.choice(interleaving_patterns),
                "coreset_duration": random.choice(coreset_durations),
                "AL_corr_thresholds": random.choice(AL_thresholds_choices),
                "num_candidates_per_AL": random.choice(num_candidates_choices),
            }
        ]
    }

def generate_example():
    cfg = sample_config()
    toml_str = dict_to_toml(cfg)
    user_prompt = random.choice(prompt_templates)
    return {
        "messages": [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": toml_str}
        ]
    }

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate synthetic JSONL for fine-tuning a sniffer-config LLM"
    )
    p.add_argument(
        "--num-examples", "-n", type=int, default=1000,
        help="How many examples to generate (default: 1000)"
    )
    return p.parse_args()

def main():
    args = parse_args()
    examples = [generate_example() for _ in range(args.num_examples)]

    output_file = "sniffer_finetune_1000.jsonl"
    with open(output_file, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")

    print(f"Created {output_file} with {len(examples)} examples.")

if __name__ == "__main__":
    main()
