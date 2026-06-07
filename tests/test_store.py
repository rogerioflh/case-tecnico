from __future__ import annotations

import unittest

from app.store import InMemorySessionStore, SessionState


class StoreTest(unittest.TestCase):
    def test_session_state_verification_flag_depends_on_customer_cpf(self) -> None:
        session = SessionState(session_id="s1")
        self.assertFalse(session.is_verified)

        session.verified_customer_cpf = "12345678909"

        self.assertTrue(session.is_verified)

    def test_store_get_returns_same_session_instance(self) -> None:
        store = InMemorySessionStore()

        first = store.get("s1")
        first.history.append({"role": "user", "content": "ola"})
        second = store.get("s1")

        self.assertIs(first, second)
        self.assertEqual(second.history, [{"role": "user", "content": "ola"}])

    def test_store_reset_removes_existing_session(self) -> None:
        store = InMemorySessionStore()
        session = store.get("s1")
        session.verified_customer_cpf = "12345678909"

        store.reset("s1")
        fresh = store.get("s1")

        self.assertIsNot(session, fresh)
        self.assertFalse(fresh.is_verified)

    def test_store_reset_is_idempotent(self) -> None:
        store = InMemorySessionStore()

        store.reset("missing")

        self.assertFalse(store.get("missing").is_verified)


if __name__ == "__main__":
    unittest.main()
