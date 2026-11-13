
import logging
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from brain import VENBrain
from context_engine import VENContext
from knowledge_engine import VENKnowledge
from web_knowledge import VENWebKnowledge, WebLookupError


app = FastAPI(title="VEN AI Backend")
logger = logging.getLogger(__name__)


# Initialize VEN's engines.
ven_context = VENContext()
ven_brain = VENBrain()
ven_knowledge = VENKnowledge(
    facts=ven_context.facts,
    nlp=ven_context.semantic_engine.interpreter.nlp
)
ven_web_knowledge = VENWebKnowledge(
    nlp=ven_context.semantic_engine.interpreter.nlp
)


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str
    local_hour: int | None = Field(default=None, ge=0, le=23)
    conversation_history: list[ConversationTurn] = Field(
        default_factory=list,
        max_length=8,
    )


class ChatResponse(BaseModel):
    reply: str
    source_title: str | None = None
    source_url: str | None = None


def search_web(message):
    try:
        result = ven_web_knowledge.search(message)
    except WebLookupError as error:
        logger.warning("Public web search failed: %s", error)
        return ChatResponse(
            reply=(
                "I couldn't reach public web search right now. "
                "Please try again later."
            )
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

    # First, use local conversation and vocabulary knowledge.
    brain_response = ven_brain.think(
        user_message,
        request.local_hour,
        [
            turn.model_dump()
            for turn in request.conversation_history
        ],
    )
    if brain_response is not None:
        return ChatResponse(reply=brain_response)

    interpreted_message = user_message
    if user_message.lower().startswith("am "):
        interpreted_message = f"I {user_message}"
    result = ven_context.process(interpreted_message)

    if result["decision"] == "question":
        knowledge_response = ven_knowledge.answer(user_message)
        if "I don't know that yet." not in knowledge_response:
            return ChatResponse(reply=knowledge_response)

        web_response = search_web(user_message)
        if web_response:
            return web_response

        return ChatResponse(
            reply=ven_brain.response_engine.respond_to_unknown_question(
                user_message
            )
        )

    if ven_web_knowledge.is_search_request(user_message):
        web_response = search_web(user_message)
        if web_response:
            return web_response

    if result["decision"] in (
        "new_information",
        "consistent",
        "contradiction"
    ):
        return ChatResponse(
            reply=ven_brain.response_engine.respond_to_statement(
                user_message,
                result,
            )
        )

    if result["decision"] in ("incomplete", "uncertain"):
        return ChatResponse(
            reply=ven_brain.response_engine.respond_to_statement(
                user_message,
                result,
            )
        )

    return ChatResponse(
        reply=ven_brain.response_engine.respond_to_unknown_question(
            user_message
        )
    )
