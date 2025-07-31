# finetune.py

from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset
import torch

# Load model and tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "deepseek-ai/DeepSeek-Coder-6.7B-Instruct",
    max_seq_length = 2048,
    dtype = torch.float16,
    load_in_4bit = True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,                    # Rank of LoRA
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],  # Safe defaults
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    use_gradient_checkpointing=True,
)

FastLanguageModel.for_training(model)

# Load dataset
finetune_data = load_dataset("json", data_files="intent_finetune_data.jsonl", split="train")

# Static instruction prompt (prepending this to every user input)
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

# Apply chat formatting to each example
def format_chat(example):
    full_prompt = f"{intent_prompt}\nUser Request: {example['prompt']}"
    messages = [
        {"role": "user", "content": full_prompt},
        {"role": "assistant", "content": example["completion"]},
    ]
    return {"text": tokenizer.apply_chat_template(messages, tokenize=False)}

# Convert prompts/completions to full chat-formatted text
finetune_data = finetune_data.map(format_chat)

# Training config
sft_config = SFTConfig(
    output_dir = "intent_lora_model",
    num_train_epochs = 3,
    per_device_train_batch_size = 2,
    gradient_accumulation_steps = 2,
    save_steps = 50,
    logging_steps = 10,
    learning_rate = 2e-5,
    lr_scheduler_type = "linear",
    warmup_steps = 10,
    fp16 = True,
    optim = "adamw_8bit",
    packing = False,
)

# Trainer (no formatting_func needed)
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = finetune_data,
    args = sft_config,
)

trainer.train()

# Save model
model.save_pretrained("intent_lora_model")
tokenizer.save_pretrained("intent_lora_model")
