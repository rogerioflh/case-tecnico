from __future__ import annotations

import unittest

from app.agent import RetailAssistantAgent
from app.data import load_customers
from app.store import InMemorySessionStore


class RetailAssistantAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = RetailAssistantAgent(InMemorySessionStore(), load_customers(), api_key="")

    def test_blocks_order_actions_before_verification(self) -> None:
        response = self.agent.reply("s1", "quero listar meus pedidos")

        self.assertFalse(response.verified)
        self.assertEqual(response.intent, "verify_identity")
        self.assertEqual(response.actions_available, ["verify_identity"])

    def test_verifies_customer_with_name_cpf_and_email(self) -> None:
        response = self.agent.reply(
            "s1",
            "Meu nome e Rogerio Silva, CPF 123.456.789-09 e e-mail rogerio.silva@example.com",
        )

        self.assertTrue(response.verified)
        self.assertEqual(response.customer_name, "Rogerio Silva")
        self.assertIn("listar_pedidos", response.actions_available)

    def test_order_tools_use_verified_customer_scope(self) -> None:
        tools = {tool.name: tool for tool in self.agent._build_order_tools("12345678909")}

        listed = tools["listar_pedidos"].invoke({"observacao": "minhas compras"})
        other_customer_order = tools["rastrear_pedido"].invoke({"order_id": "PED-2001"})

        self.assertIn("PED-1001", listed)
        self.assertIn("Nao encontrei", other_customer_order)

    def test_cancel_tool_updates_order_status(self) -> None:
        tools = {tool.name: tool for tool in self.agent._build_order_tools("12345678909")}

        cancel = tools["cancelar_pedido"].invoke({"order_id": "PED-1002", "motivo": "desisti"})
        status = tools["verificar_status_pedido"].invoke({"order_id": "PED1002"})

        self.assertIn("Cancelamento solicitado com sucesso", cancel)
        self.assertIn("Cancelado", status)


if __name__ == "__main__":
    unittest.main()
