from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app import main as api
from app.models import ChatResponse
from app.store import InMemorySessionStore


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def reply(self, session_id: str, message: str) -> ChatResponse:
        self.calls.append((session_id, message))
        return ChatResponse(
            session_id=session_id,
            verified=False,
            intent="fake_intent",
            assistant_message=f"eco: {message}",
            actions_available=["verify_identity"],
            customer_name=None,
        )


class FastAPIMainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_agent = api.agent
        self.original_store = api.session_store
        self.fake_agent = FakeAgent()
        api.agent = self.fake_agent
        api.session_store = InMemorySessionStore()
        self.client = TestClient(api.app)

    def tearDown(self) -> None:
        api.agent = self.original_agent
        api.session_store = self.original_store

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_chat_endpoint_delegates_to_agent(self) -> None:
        response = self.client.post(
            "/chat",
            json={"session_id": "s1", "message": "ola"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fake_agent.calls, [("s1", "ola")])
        self.assertEqual(response.json()["assistant_message"], "eco: ola")
        self.assertEqual(response.json()["actions_available"], ["verify_identity"])

    def test_reset_session_endpoint_clears_session_state(self) -> None:
        api.session_store.get("s1").verified_customer_cpf = "12345678909"

        response = self.client.post("/sessions/s1/reset")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "reset"})
        self.assertFalse(api.session_store.get("s1").is_verified)


if __name__ == "__main__":
    unittest.main()
