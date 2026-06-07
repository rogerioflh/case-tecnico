from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from hashlib import sha256
from unittest.mock import patch


class SessionStateStub(dict):
    def __getattr__(self, name: str) -> object:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: object) -> None:
        self[name] = value


class ContextStub:
    def __enter__(self) -> "ContextStub":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class StreamlitStub(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("streamlit")
        self.session_state = SessionStateStub()
        self.sidebar = ContextStub()

    def set_page_config(self, **kwargs: object) -> None:
        return None

    def header(self, *args: object, **kwargs: object) -> None:
        return None

    def selectbox(self, label: str, options: tuple[str, ...], index: int = 0, **kwargs: object) -> str:
        return options[index]

    def text_input(self, label: str, value: str = "", key: str | None = None, **kwargs: object) -> str:
        if key is None:
            return value
        if key not in self.session_state:
            self.session_state[key] = value
        return str(self.session_state[key])

    def warning(self, *args: object, **kwargs: object) -> None:
        return None

    def button(self, *args: object, **kwargs: object) -> bool:
        return False

    def divider(self, *args: object, **kwargs: object) -> None:
        return None

    def subheader(self, *args: object, **kwargs: object) -> None:
        return None

    def code(self, *args: object, **kwargs: object) -> None:
        return None

    def title(self, *args: object, **kwargs: object) -> None:
        return None

    def caption(self, *args: object, **kwargs: object) -> None:
        return None

    def info(self, *args: object, **kwargs: object) -> None:
        return None

    def chat_message(self, *args: object, **kwargs: object) -> ContextStub:
        return ContextStub()

    def markdown(self, *args: object, **kwargs: object) -> None:
        return None

    def chat_input(self, *args: object, **kwargs: object) -> None:
        return None

    def spinner(self, *args: object, **kwargs: object) -> ContextStub:
        return ContextStub()


class StreamlitAppTest(unittest.TestCase):
    def load_module(self, env: dict[str, str] | None = None) -> tuple[types.ModuleType, StreamlitStub]:
        fake_streamlit = StreamlitStub()
        sys.modules.pop("app.streamlit_app", None)
        self.addCleanup(lambda: sys.modules.pop("app.streamlit_app", None))

        with patch.dict(sys.modules, {"streamlit": fake_streamlit}):
            with patch.dict(os.environ, env or {}, clear=True):
                module = importlib.import_module("app.streamlit_app")

        return module, fake_streamlit

    def test_config_signature_trims_visible_values_and_hashes_key(self) -> None:
        module, _ = self.load_module()

        signature = module._config_signature(" openai ", " gpt-4o-mini ", "secret")

        self.assertEqual(signature[:2], ("openai", "gpt-4o-mini"))
        self.assertEqual(signature[2], sha256(b"secret").hexdigest())
        self.assertNotIn("secret", signature[2])

    def test_get_api_key_from_env_uses_generic_key_first(self) -> None:
        module, _ = self.load_module()

        with patch.dict(
            os.environ,
            {"ORDER_ASSISTANT_API_KEY": "generic", "OPENROUTER_API_KEY": "provider"},
            clear=True,
        ):
            self.assertEqual(module._get_api_key_from_env("openrouter"), "generic")

    def test_get_api_key_from_env_uses_provider_fallback(self) -> None:
        module, _ = self.load_module()

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "google-key"}, clear=True):
            self.assertEqual(module._get_api_key_from_env("gemini"), "google-key")

    def test_reset_chat_recreates_state_for_selected_configuration(self) -> None:
        module, fake_streamlit = self.load_module()
        fake_streamlit.session_state.messages = [{"role": "user", "content": "antiga"}]

        module._reset_chat("openrouter", "google/gemini-2.5-flash", "")

        self.assertTrue(fake_streamlit.session_state.session_id.startswith("streamlit-"))
        self.assertEqual(fake_streamlit.session_state.messages, [])
        self.assertIsNone(fake_streamlit.session_state.last_response)
        self.assertEqual(
            fake_streamlit.session_state.agent_config,
            module._config_signature("openrouter", "google/gemini-2.5-flash", ""),
        )


if __name__ == "__main__":
    unittest.main()
