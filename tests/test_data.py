from __future__ import annotations

import unittest

from app.data import CUSTOMERS, load_customers


class DataTest(unittest.TestCase):
    def test_load_customers_returns_expected_fixture_shape(self) -> None:
        customers = load_customers()

        self.assertIn("12345678909", customers)
        self.assertEqual(customers["12345678909"]["name"], "Rogerio Silva")
        self.assertGreaterEqual(len(customers["12345678909"]["orders"]), 3)
        self.assertIn("tracking_history", customers["12345678909"]["orders"][0])

    def test_load_customers_returns_deep_copy(self) -> None:
        customers = load_customers()
        customers["12345678909"]["orders"][0]["status"] = "Alterado no teste"
        customers["12345678909"]["orders"][0]["tracking_history"].append("mutacao")

        fresh = load_customers()

        self.assertEqual(CUSTOMERS["12345678909"]["orders"][0]["status"], "Em transporte")
        self.assertEqual(fresh["12345678909"]["orders"][0]["status"], "Em transporte")
        self.assertNotIn("mutacao", fresh["12345678909"]["orders"][0]["tracking_history"])


if __name__ == "__main__":
    unittest.main()
