import json
import random
import argparse
from itertools import permutations, islice

# Canonical actions
COMPONENT_ACTIONS = {
    "rtue": "generate a rtue configuration",
    "sniffer": "generate a sniffer configuration",
    "jammer": "generate a jammer configuration"
}

# Natural prompt templates
PHRASES = {
    "rtue": [
        "set up the rtue",
        "initialize the rtue",
        "prepare the rtue",
        "start the rtue"
    ],
    "sniffer": [
        "use a sniffer",
        "observe with the sniffer",
        "run the sniffer",
        "sniff the signal"
    ],
    "jammer": [
        "jam the target",
        "interfere using jammer",
        "deploy the jammer",
        "activate the jammer"
    ]
}

def order_components(combo):
    if "rtue" in combo:
        return tuple(sorted(combo, key=lambda x: 0 if x == "rtue" else 1))
    return combo

def generate_examples(n):
    all_examples = []
    for size in [1, 2, 3]:
        for combo in permutations(COMPONENT_ACTIONS.keys(), size):
            ordered = order_components(combo)
            prompt_parts = [random.choice(PHRASES[c]) for c in ordered]
            user_prompt = " and ".join(prompt_parts)
            completion = [
                {"step": i + 1, "component": c, "action": COMPONENT_ACTIONS[c]}
                for i, c in enumerate(ordered)
            ]
            all_examples.append({
                "prompt": user_prompt,
                "completion": json.dumps(completion)
            })

    # If n is more than total available, resample with variation
    examples = []
    for _ in range(n):
        base = random.choice(all_examples)
        # Re-randomize phrases to introduce variation
        combo = [step["component"] for step in json.loads(base["completion"])]
        prompt_parts = [random.choice(PHRASES[c]) for c in combo]
        prompt = " and ".join(prompt_parts)
        examples.append({
            "prompt": prompt,
            "completion": json.dumps([
                {"step": i + 1, "component": c, "action": COMPONENT_ACTIONS[c]}
                for i, c in enumerate(combo)
            ])
        })

    return examples

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate intent fine-tuning dataset")
    parser.add_argument("-n", "--num_examples", type=int, default=100, help="Number of examples to generate")
    parser.add_argument("-o", "--output", type=str, default="intent_finetune_data.jsonl", help="Output filename")
    args = parser.parse_args()

    data = generate_examples(args.num_examples)

    with open(args.output, "w") as f:
        for ex in data:
            f.write(json.dumps(ex) + "\n")

    print(f"Generated {len(data)} examples in {args.output}")
