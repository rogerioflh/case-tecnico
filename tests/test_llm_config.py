from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app import llm_config


class LLMConfigTest(unittest.TestCase):
    def test_normalize_provider_accepts_supported_names_and_alias(self) -> None:
        self.assertEqual(llm_config.normalize_provider(" OpenAI "), "openai")
        self.assertEqual(llm_config.normalize_provider("google"), "gemini")
        self.assertEqual(llm_config.normalize_provider("ANTHROPIC"), "anthropic")

    def test_normalize_provider_rejects_unknown_provider(self) -> None:
        with self.assertRaisesRegex(ValueError, "nao suportado"):
            llm_config.normalize_provider("local")

    def test_default_provider_reads_environment(self) -> None:
        with patch.dict(os.environ, {"ORDER_ASSISTANT_PROVIDER": "google"}, clear=True):
            self.assertEqual(llm_config.default_provider(), "gemini")

    def test_default_model_uses_environment_override(self) -> None:
        with patch.dict(os.environ, {"ORDER_ASSISTANT_MODEL": "custom-model"}, clear=True):
            self.assertEqual(llm_config.default_model("openai"), "custom-model")

    def test_default_model_uses_provider_default_without_override(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(llm_config.default_model("openrouter"), "google/gemini-2.5-flash")

    def test_default_api_key_prefers_generic_environment_key(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ORDER_ASSISTANT_API_KEY": "generic-key",
                "OPENAI_API_KEY": "provider-key",
            },
            clear=True,
        ):
            self.assertEqual(llm_config.default_api_key("openai"), "generic-key")

    def test_default_api_key_uses_provider_specific_fallback(self) -> None:
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "google-key"}, clear=True):
            self.assertEqual(llm_config.default_api_key("gemini"), "google-key")

    def test_provider_key_hint_detects_mismatched_key_family(self) -> None:
        self.assertIn("Google/Gemini", llm_config.provider_key_hint("openrouter", "AIza123"))
        self.assertIn("OpenRouter", llm_config.provider_key_hint("gemini", "sk-or-123"))
        self.assertIsNone(llm_config.provider_key_hint("openai", "sk-openai"))
        self.assertIsNone(llm_config.provider_key_hint("openrouter", ""))


if __name__ == "__main__":
    unittest.main()
