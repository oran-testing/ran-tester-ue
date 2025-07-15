import json
import torch
from unsloth import FastLanguageModel, is_bfloat16_supported
from datasets import load_dataset
from transformers import TrainingArguments from trl import SFTTrainer

# ── Load the dataset ──────────────────────────────────────────────────────────
dataset = load_dataset("json", data_files="sniffer_finetune_1000.jsonl", split="train")

# ── Convert to Alpaca-style instruction–output format ─────────────────────────
def convert_to_alpaca_format(example):
    return {
        "instruction": example["messages"][0]["content"],
        "input": "",
        "output": example["messages"][1]["content"],
    }

dataset = dataset.map(convert_to_alpaca_format)

# ── Format prompts ────────────────────────────────────────────────────────────
alpaca_prompt = """Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
{}

### Response:
{}"""
EOS_TOKEN = "</s>"

def formatting_prompts_func(examples):
    return {
        "text": [
            alpaca_prompt.format(inst, out) + EOS_TOKEN
            for inst, out in zip(examples["instruction"], examples["output"])
        ]
    }

dataset = dataset.map(formatting_prompts_func, batched=True)

# ── Load model ────────────────────────────────────────────────────────────────
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/gemma-3-4b-it-unsloth-bnb-4bit",
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)

# ── Apply LoRA PEFT tuning ────────────────────────────────────────────────────
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=[
    ],
    "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
    use_rslora=False,
    loftq_config=None,
)

# ── Fine-tune ─────────────────────────────────────────────────────────────────
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    dataset_num_proc=2,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        max_steps=60,
        learning_rate=2e-4,
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="outputs",
        report_to="none",
    ),
)

# ── Report GPU stats ──────────────────────────────────────────────────────────
gpu_stats = torch.cuda.get_device_properties(0)
start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024**3, 3)
max_memory = round(gpu_stats.total_memory / 1024**3, 3)
print(f"GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
print(f"{start_gpu_memory} GB of memory reserved at start.")

trainer_stats = trainer.train()

used_memory = round(torch.cuda.max_memory_reserved() / 1024**3, 3)
used_memory_for_lora = round(used_memory - start_gpu_memory, 3)
used_percentage = round(used_memory / max_memory * 100, 3)
lora_percentage = round(used_memory_for_lora / max_memory * 100, 3)

print(f"\nTraining runtime: {trainer_stats.metrics['train_runtime']} seconds")
print(f"({round(trainer_stats.metrics['train_runtime']/60, 2)} minutes)")
print(f"Peak reserved memory = {used_memory} GB")
print(f"Used by LoRA training = {used_memory_for_lora} GB")
print(f"GPU utilization = {used_percentage}% total, {lora_percentage}% for LoRA")

# ── Save final fine-tuned model ───────────────────────────────────────────────
model.save_pretrained("lora_model_sniffer")
tokenizer.save_pretrained("lora_model_sniffer")
