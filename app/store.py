from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionState:
    session_id: str
    verified_customer_cpf: Optional[str] = None
    failed_verification_attempts: int = 0
    last_intent: str = "start"
    history: list[dict[str, str]] = field(default_factory=list)

    @property
    def is_verified(self) -> bool:
        return self.verified_customer_cpf is not None


class InMemorySessionStore:
    """Small state store used to simulate conversational memory by session_id."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def get(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
