from __future__ import annotations

import unittest

from app.agent import RetailAssistantAgent
from app.data import load_customers
from app.store import InMemorySessionStore


class AgentOrderToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = RetailAssistantAgent(InMemorySessionStore(), load_customers(), api_key="")
        self.tools = {
            tool.name: tool for tool in self.agent._build_order_tools("12345678909")
        }

    def test_tracking_tool_returns_carrier_code_and_history(self) -> None:
        result = self.tools["rastrear_pedido"].invoke({"order_id": "1001"})

        self.assertIn("Status do PED-1001", result)
        self.assertIn("Correios", result)
        self.assertIn("BR123456789BR", result)
        self.assertIn("Objeto postado", result)

    def test_status_tool_reports_summary_for_verified_customer(self) -> None:
        result = self.tools["verificar_status_pedido"].invoke({"order_id": "PED-1003"})

        self.assertIn("Pedido PED-1003: Entregue", result)
        self.assertIn("Cafeteira Smart Brew", result)
        self.assertIn("Loggi", result)

    def test_cancel_tool_refuses_delivered_or_already_cancelled_order(self) -> None:
        delivered = self.tools["cancelar_pedido"].invoke({"order_id": "PED-1003"})

        self.assertIn("nao pode ser cancelado", delivered)
        self.assertEqual(
            self.agent._find_order("12345678909", "PED-1003")["status"],
            "Entregue",
        )

    def test_tools_reject_unknown_order_inside_verified_account(self) -> None:
        result = self.tools["verificar_status_pedido"].invoke({"order_id": "PED-9999"})

        self.assertIn("Nao encontrei o pedido PED-9999", result)


if __name__ == "__main__":
    unittest.main()
