
import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
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
    new_conversation: bool = False
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

    interpreted_message = ven_brain.correct_message(user_message)
    if request.new_conversation:
        ven_brain.last_topic = None

    # First, use local conversation and vocabulary knowledge.
    brain_response = ven_brain.think(
        interpreted_message,
        request.local_hour,
        [
            turn.model_dump()
            for turn in request.conversation_history
        ],
    )
    if brain_response is not None:
        return ChatResponse(reply=brain_response)

    if interpreted_message.lower().startswith("am "):
        interpreted_message = f"I {interpreted_message}"
    result = ven_context.process(interpreted_message)

    if result["decision"] == "question":
        knowledge_response = ven_knowledge.answer(interpreted_message)
        if "I don't know that yet." not in knowledge_response:
            return ChatResponse(reply=knowledge_response)

        web_response = search_web(interpreted_message)
        if web_response:
            return web_response

        return ChatResponse(
            reply=ven_brain.response_engine.respond_to_unknown_question(
                interpreted_message
            )
        )


    if ven_web_knowledge.is_search_request(interpreted_message):
        web_response = search_web(interpreted_message)
        if web_response:
            return web_response

    if result["decision"] in (
        "new_information",
        "consistent",
        "contradiction"
    ):
        return ChatResponse(
            reply=ven_brain.response_engine.respond_to_statement(
                interpreted_message,
                result,
            )
        )

    if result["decision"] in ("incomplete", "uncertain"):
        return ChatResponse(
            reply=ven_brain.response_engine.respond_to_statement(
                interpreted_message,
                result,
            )
        )

    return ChatResponse(
        reply=ven_brain.response_engine.respond_to_unknown_question(
            interpreted_message
        )
    )


@app.get("/memory")
def read_memory():
    return {"facts": ven_context.show_memory()}


@app.delete("/memory/{fact_index}")
def forget_memory(fact_index: int):
    if not 0 <= fact_index < len(ven_context.facts):
        raise HTTPException(status_code=404, detail="Memory not found.")

    ven_context.facts.pop(fact_index)
    ven_context.save_memory()
    return {"facts": ven_context.show_memory()}
