from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.models import ChatRequest, ChatResponse, HealthResponse


class ModelsTest(unittest.TestCase):
    def test_chat_request_uses_default_session_id(self) -> None:
        request = ChatRequest(message="ola")

        self.assertEqual(request.session_id, "demo")
        self.assertEqual(request.message, "ola")

    def test_chat_request_rejects_empty_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ChatRequest(session_id="", message="ola")

        with self.assertRaises(ValidationError):
            ChatRequest(session_id="s1", message="")

    def test_chat_response_serializes_optional_customer_name(self) -> None:
        response = ChatResponse(
            session_id="s1",
            verified=True,
            intent="verified",
            assistant_message="ok",
            actions_available=["listar_pedidos"],
            customer_name="Rogerio Silva",
        )

        self.assertEqual(response.model_dump()["customer_name"], "Rogerio Silva")

    def test_health_response_status(self) -> None:
        self.assertEqual(HealthResponse(status="ok").status, "ok")


if __name__ == "__main__":
    unittest.main()
