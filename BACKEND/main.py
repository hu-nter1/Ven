
import logging

from fastapi import FastAPI
from pydantic import BaseModel

from brain import VENBrain
from context_engine import VENContext
from knowledge_engine import VENKnowledge
from web_knowledge import VENWebKnowledge, WebLookupError


app = FastAPI(title="VEN AI Backend")
logger = logging.getLogger(__name__)


# Initialize VEN's engines.
ven_brain = VENBrain()
ven_context = VENContext()
ven_knowledge = VENKnowledge(
    facts=ven_context.facts,
    nlp=ven_context.semantic_engine.interpreter.nlp
)
ven_web_knowledge = VENWebKnowledge(
    nlp=ven_context.semantic_engine.interpreter.nlp
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    source_title: str | None = None
    source_url: str | None = None


def search_web(message):
    try:
        result = ven_web_knowledge.search(message)
    except WebLookupError as error:
        logger.warning("Wikipedia lookup failed: %s", error)
        return ChatResponse(
            reply="I couldn't reach Wikipedia right now. Please try again later."
        )

    if result:
        return ChatResponse(
            reply=result.reply,
            source_title=result.title,
            source_url=result.url,
        )

    return None


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

    is_unknown_word = brain_response.startswith("I don't have the word")
    if not brain_response.startswith(fallback) and not (
        is_unknown_word and ven_web_knowledge.is_search_request(user_message)
    ):
        return ChatResponse(reply=brain_response)

    result = ven_context.process(user_message)

    if result["decision"] == "question":
        knowledge_response = ven_knowledge.answer(user_message)
        if "I don't know that yet." not in knowledge_response:
            return ChatResponse(reply=knowledge_response)

        web_response = search_web(user_message)
        if web_response:
            return web_response

        return ChatResponse(reply=brain_response)

    if ven_web_knowledge.is_search_request(user_message):
        web_response = search_web(user_message)
        if web_response:
            return web_response

    if result["decision"] in (
        "new_information",
        "consistent",
        "contradiction"
    ):
        return ChatResponse(reply=result["message"])

    return ChatResponse(reply=brain_response)
