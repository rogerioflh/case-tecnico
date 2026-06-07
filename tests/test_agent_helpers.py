from __future__ import annotations

import unittest

from app.agent import (
    _content_to_text,
    _extract_last_ai_text,
    _format_llm_error,
    _normalize_order_id,
    extract_identity,
    verification_node,
)
from app.data import load_customers
from app.store import InMemorySessionStore


class AgentHelpersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.customers = load_customers()

    def test_extract_identity_from_free_text(self) -> None:
        identity = extract_identity(
            "Sou Rogerio Silva, CPF 123.456.789-09, email rogerio.silva@example.com",
            self.customers,
        )

        self.assertEqual(identity.name, "Rogerio Silva")
        self.assertEqual(identity.cpf, "12345678909")
        self.assertEqual(identity.email, "rogerio.silva@example.com")
        self.assertTrue(identity.has_any_field)

    def test_normalize_order_id_accepts_common_formats(self) -> None:
        self.assertEqual(_normalize_order_id("PED-1001"), "PED-1001")
        self.assertEqual(_normalize_order_id("ped1001"), "PED-1001")
        self.assertEqual(_normalize_order_id("1001"), "PED-1001")
        self.assertEqual(_normalize_order_id(" abc-xyz "), "ABC-XYZ")

    def test_verification_node_reuses_verified_session(self) -> None:
        store = InMemorySessionStore()
        store.get("s1").verified_customer_cpf = "12345678909"

        result = verification_node(
            {"session_id": "s1", "user_message": "quero listar meus pedidos"},
            store,
            self.customers,
        )

        self.assertTrue(result["verified"])
        self.assertEqual(result["verified_customer_cpf"], "12345678909")
        self.assertEqual(result["customer_name"], "Rogerio Silva")
        self.assertEqual(result["next_node"], "agent")

    def test_verification_node_reports_missing_fields(self) -> None:
        result = verification_node(
            {"session_id": "s1", "user_message": "Meu nome e Rogerio Silva"},
            InMemorySessionStore(),
            self.customers,
        )

        self.assertFalse(result["verified"])
        self.assertEqual(result["intent"], "verify_identity")
        self.assertIn("CPF", result["assistant_message"])
        self.assertIn("e-mail cadastrado", result["assistant_message"])

    def test_verification_node_records_failed_attempt(self) -> None:
        store = InMemorySessionStore()

        result = verification_node(
            {
                "session_id": "s1",
                "user_message": (
                    "Meu nome e Rogerio Silva, CPF 123.456.789-09 e "
                    "e-mail marina.costa@example.com"
                ),
            },
            store,
            self.customers,
        )

        self.assertFalse(result["verified"])
        self.assertEqual(result["intent"], "verify_identity_failed")
        self.assertEqual(store.get("s1").failed_verification_attempts, 1)

    def test_content_to_text_flattens_provider_parts(self) -> None:
        content = [{"text": "Primeira parte"}, "segunda parte", {"other": "valor"}]

        self.assertEqual(
            _content_to_text(content),
            "Primeira parte\nsegunda parte\n{'other': 'valor'}",
        )

    def test_extract_last_ai_text_uses_last_ai_message(self) -> None:
        class Message:
            def __init__(self, message_type: str, content: object) -> None:
                self.type = message_type
                self.content = content

        result = {
            "messages": [
                Message("human", "oi"),
                Message("ai", [{"text": "resposta final"}]),
            ]
        }

        self.assertEqual(_extract_last_ai_text(result), "resposta final")

    def test_format_llm_error_maps_known_failures(self) -> None:
        self.assertIn(
            "autenticar",
            _format_llm_error(RuntimeError("401 invalid_api_key")),
        )
        self.assertIn(
            "modelo configurado",
            _format_llm_error(RuntimeError("model does not exist")),
        )
        self.assertIn(
            "Tipo do erro: RuntimeError",
            _format_llm_error(RuntimeError("timeout")),
        )


if __name__ == "__main__":
    unittest.main()
