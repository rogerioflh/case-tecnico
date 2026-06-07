from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(default="demo", min_length=1)
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    session_id: str
    verified: bool
    intent: str
    assistant_message: str
    actions_available: list[str]
    customer_name: Optional[str] = None


class HealthResponse(BaseModel):
    status: str

