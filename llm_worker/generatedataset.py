# intent_generate_dataset.py
import json
import random
from itertools import permutations

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

# Helper to order components per rules (rtue always first)
def order_components(combo):
    if "rtue" in combo:
        return tuple(sorted(combo, key=lambda x: 0 if x == "rtue" else 1))
    return combo

examples = []

# Generate combinations of 1, 2, and 3 components
for size in [1, 2, 3]:
    for combo in permutations(COMPONENT_ACTIONS.keys(), size):
        ordered = order_components(combo)

        # Natural language request
        prompt_parts = [random.choice(PHRASES[c]) for c in ordered]
        user_prompt = " and ".join(prompt_parts)

        # Canonical JSON completion
        completion = [
            {"step": i+1, "component": c, "action": COMPONENT_ACTIONS[c]}
            for i, c in enumerate(ordered)
        ]

        examples.append({
            "prompt": user_prompt,
            "completion": json.dumps(completion)
        })

# Write to file
with open("intent_finetune_data.jsonl", "w") as f:
    for ex in examples:
        f.write(json.dumps(ex) + "\n")

print(f"Generated {len(examples)} examples in intent_finetune_data.jsonl")
