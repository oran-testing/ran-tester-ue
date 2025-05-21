from unsloth import FastModel
import torch
import os
import requests
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import threading

# === FastAPI setup ===
app = FastAPI()

class Message(BaseModel):
    sender: str
    content: str

@app.post("/message")
async def receive_message(msg: Message):
    print(f"📨 Received from {msg.sender}: {msg.content}")
    return {"status": "received"}

@app.get("/status")
def status():
    return {"status": "llm_worker alive"}

# === Model loading + message sending logic ===
def init_model_and_send_response():
    print("🔍 [DEBUG] Current working directory:", os.getcwd())
    print("📂 [DEBUG] Listing contents of current directory:")
    for item in os.listdir():
        print("   -", item)

    model_path = "/app/lora_model_sniffer"

    print(f"🔍 [DEBUG] Checking if model directory exists: {model_path}")
    if not os.path.exists(model_path):
        print(f"❌ [ERROR] Model directory '{model_path}' not found!")
        raise FileNotFoundError(f"Model directory '{model_path}' not found!")

    print("📦 [DEBUG] Loading model...")
    model, tokenizer = FastModel.from_pretrained(
        model_name="lora_model_sniffer",
        max_seq_length=2048,
        load_in_4bit=True,
    )
    print("✅ [DEBUG] Model loaded.")

    messages = [{
        "role": "user",
        "content": [{
            "type": "text",
            "text": "Generate a config file for the sniffer.",
        }]
    }]

    text = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to("cuda")

    print("⚙️ [DEBUG] Generating model output...")
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=200,
            temperature=1.0,
            top_p=0.95,
            top_k=64,
            repetition_penalty=1.1,
            eos_token_id=tokenizer.eos_token_id,
        )

    decoded_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    reply = decoded_output[len(text):].strip()

    print("\n--- Response ---")
    print(reply)

    # === Send message back to controller ===
    try:
        print("📡 Sending message back to controller...")
        res = requests.post("http://controller:9000/from-worker", json={
            "sender": "llm_worker",
            "content": reply
        })
        print("✅ Controller replied:", res.json())
    except Exception as e:
        print("❌ Could not contact controller:", e)

# === Entry ===
if __name__ == "__main__":
    threading.Thread(target=init_model_and_send_response, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
