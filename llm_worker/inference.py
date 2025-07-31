# inference.py

from unsloth import FastLanguageModel
import torch

# Load finetuned model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "intent_lora_model",
    max_seq_length = 2048,
    dtype = torch.float16,
    load_in_4bit = True,
    device_map = "auto",
)

model.eval()

# The same prompt used in training
intent_prompt = """You are an expert RF engineering assistant. Your job is to convert the user's request into a precise, ordered list of configuration steps.

**Output must be a valid JSON array. No explanations.**

---
**Allowed Components and Actions (use exactly):**
- "rtue": "generate a rtue configuration"
- "sniffer": "generate a sniffer configuration"
- "jammer": "generate a jammer configuration"

Only use these exact actions. Do not invent or modify them.

---
**Rules:**
- Only one step per component.
- If rtue is used, it must be step 1.
- Do not extract parameters like frequency or gain into separate steps — those are part of the configuration.
- Output only the structure below:

[
  {
    "step": 1,
    "component": "component_name",
    "action": "action_to_perform"
  }
]

---
"""

# Inference loop
while True:
    user_input = input("\nUser Request (type 'exit' to quit): ").strip()
    if user_input.lower() == "exit":
        break

    # Construct full prompt with user and assistant roles
    full_prompt = tokenizer.apply_chat_template(
        [
            {"role": "user", "content": f"{intent_prompt}\nUser Request: {user_input}"},
            {"role": "assistant", "content": ""},  # generation starts here
        ],
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(full_prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.2,
            top_p=0.95,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)

    print("\n===== Output =====")
    print(decoded.split("User Request:")[-1].strip())
