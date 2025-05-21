from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
import requests
import threading
import time

app = FastAPI()

class Message(BaseModel):
    sender: str
    content: str

@app.post("/message")
async def receive_message(msg: Message):
    print(f"[llm_worker] 📩 Received from {msg.sender}: {msg.content}")
    return {"status": "received"}

@app.get("/ping")
def ping():
    return JSONResponse(content={"status": "ok"})

@app.get("/status")
def status():
    return {"status": "llm_worker running"}

# Function to send a message to controller after startup
def send_to_controller():
    for attempt in range(5):  # Retry up to 5 times
        try:
            res = requests.post("http://controller:9000/from-worker", json={
                "sender": "llm_worker",
                "content": "Hello from llm_worker"
            })
            print("[llm_worker] ✅ Controller replied:", res.status_code, res.json())
            return
        except Exception as e:
            print(f"[llm_worker] ❌ Attempt {attempt+1}: Could not contact controller:", e)
            time.sleep(2)

# FastAPI startup event
@app.on_event("startup")
def startup_event():
    threading.Thread(target=send_to_controller, daemon=True).start()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
