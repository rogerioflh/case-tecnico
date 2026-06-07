from __future__ import annotations

import os


SUPPORTED_LLM_PROVIDERS = ("openrouter", "openai", "gemini", "anthropic")

DEFAULT_MODEL_BY_PROVIDER = {
    "openrouter": "google/gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-3-5-haiku-latest",
}


def normalize_provider(provider: str) -> str:
    normalized = provider.strip().casefold().replace("google", "gemini")
    if normalized not in SUPPORTED_LLM_PROVIDERS:
        raise ValueError(
            f"Provedor '{provider}' nao suportado. Use: {', '.join(SUPPORTED_LLM_PROVIDERS)}."
        )
    return normalized


def default_provider() -> str:
    return normalize_provider(os.getenv("ORDER_ASSISTANT_PROVIDER", "openrouter"))


def default_model(provider: str) -> str:
    return os.getenv("ORDER_ASSISTANT_MODEL") or DEFAULT_MODEL_BY_PROVIDER[provider]


def default_api_key(provider: str) -> str:
    provider_env = {
        "openrouter": ("OPENROUTER_API_KEY",),
        "openai": ("OPENAI_API_KEY",),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "anthropic": ("ANTHROPIC_API_KEY",),
    }
    for env_name in ("ORDER_ASSISTANT_API_KEY", *provider_env[provider]):
        value = os.getenv(env_name)
        if value:
            return value
    return ""


def provider_key_hint(provider: str, api_key: str) -> str | None:
    key = api_key.strip()
    if not key:
        return None

    if provider == "openrouter" and key.startswith("AIza"):
        return (
            "A chave informada parece ser do Google/Gemini. Para usa-la, selecione "
            "o provedor 'gemini' e o modelo 'gemini-2.5-flash'. Para OpenRouter, "
            "use uma chave gerada no painel da OpenRouter."
        )

    if provider == "gemini" and key.startswith("sk-or-"):
        return (
            "A chave informada parece ser da OpenRouter. Para usa-la, selecione "
            "o provedor 'openrouter' e um modelo no formato do OpenRouter."
        )

    if provider == "openai" and key.startswith("AIza"):
        return (
            "A chave informada parece ser do Google/Gemini. Para usa-la, selecione "
            "o provedor 'gemini'."
        )

    if provider == "anthropic" and (key.startswith("AIza") or key.startswith("sk-or-")):
        return (
            "A chave informada nao parece ser da Anthropic. Para Claude direto, "
            "use uma chave Anthropic; para OpenRouter, selecione 'openrouter'."
        )

    return None


DEFAULT_LLM_PROVIDER = default_provider()
DEFAULT_LLM_MODEL = default_model(DEFAULT_LLM_PROVIDER)
DEFAULT_LLM_API_KEY = default_api_key(DEFAULT_LLM_PROVIDER)
