from __future__ import annotations

from fastapi import FastAPI

from app.agent import RetailAssistantAgent
from app.models import ChatRequest, ChatResponse, HealthResponse
from app.store import InMemorySessionStore


app = FastAPI(
    title="Retail Order Assistant",
    version="1.0.0",
    description="Conversational assistant for customer verification and order management.",
)

session_store = InMemorySessionStore()
agent = RetailAssistantAgent(session_store)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return agent.reply(session_id=request.session_id, message=request.message)


@app.post("/sessions/{session_id}/reset", response_model=HealthResponse)
def reset_session(session_id: str) -> HealthResponse:
    session_store.reset(session_id)
    return HealthResponse(status="reset")

