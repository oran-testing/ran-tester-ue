# finetune.py
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset
import torch

# Load base model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "deepseek-ai/DeepSeek-Coder-6.7B-Instruct",
    max_seq_length = 2048,
    dtype = torch.float16,
    load_in_4bit = True,
)

FastLanguageModel.for_training(model)

# Load dataset
finetune_data = load_dataset("json", data_files="intent_finetune_data.jsonl", split="train")

# Tokenization function for chat format
def formatting_prompts_func(example):
    return [
        {
            "role": "user",
            "content": example["prompt"],
        },
        {
            "role": "assistant",
            "content": example["completion"],
        },
    ]

# Config for SFT training
sft_config = SFTConfig(
    output_dir = "intent_lora_model",
    num_train_epochs = 3,
    per_device_train_batch_size = 2,
    gradient_accumulation_steps = 2,
    max_seq_length = 2048,
    save_steps = 50,
    logging_steps = 10,
    learning_rate = 2e-5,
    lr_scheduler_type = "linear",
    warmup_steps = 10,
    bf16 = True,
    optim = "adamw_8bit",
    packing = False,
)

# Trainer
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = finetune_data,
    formatting_func = formatting_prompts_func,
    args = sft_config,
)

trainer.train()

# Save final model
model.save_pretrained("intent_lora_model")
tokenizer.save_pretrained("intent_lora_model")
