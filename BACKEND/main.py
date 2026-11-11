
from fastapi import FastAPI
from pydantic import BaseModel

from brain import VENBrain

app = FastAPI(title="VEN AI Backend")

# Initialize VEN's brain
ven = VENBrain()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/")
def home():
    return {
        "message": "VEN backend is online."
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    user_message = request.message

    # Let VEN think
    response = ven.think(user_message)

    return ChatResponse(reply=response)
