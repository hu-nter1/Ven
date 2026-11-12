
from fastapi import FastAPI
from pydantic import BaseModel

from brain import VENBrain
from context_engine import VENContext
from knowledge_engine import VENKnowledge


app = FastAPI(title="VEN AI Backend")


# Initialize VEN's engines.
ven_brain = VENBrain()
ven_context = VENContext()
ven_knowledge = VENKnowledge()


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

    user_message = request.message.strip()

    if not user_message:
        return ChatResponse(
            reply="You haven't said anything yet."
        )

    # First, try VEN's vocabulary and conversation engine.
    brain_response = ven_brain.think(user_message)

    fallback = "I am still learning. I don't understand that yet."

    if not brain_response.startswith(fallback):
        return ChatResponse(reply=brain_response)

    # If the user asks a question, search VEN's memory.
    if user_message.endswith("?"):

        # Refresh memory so newly learned facts are available.
        ven_knowledge.facts = ven_knowledge.load_memory()

        knowledge_response = ven_knowledge.answer(user_message)

        if knowledge_response != "I do not understand that question yet.":
            return ChatResponse(reply=knowledge_response)

        return ChatResponse(reply=brain_response)

    # Otherwise, try to understand and remember the statement.
    result = ven_context.process(user_message)

    if result["decision"] in (
        "new_information",
        "consistent",
        "contradiction"
    ):
        return ChatResponse(reply=result["message"])

    return ChatResponse(reply=brain_response)
