from __future__ import annotations

import os
from hashlib import sha256
from uuid import uuid4

import streamlit as st

from app.agent import RetailAssistantAgent
from app.llm_config import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_MODEL_BY_PROVIDER,
    SUPPORTED_LLM_PROVIDERS,
    provider_key_hint,
)
from app.data import CUSTOMERS, load_customers
from app.store import InMemorySessionStore


st.set_page_config(
    page_title="Retail Order Assistant",
    layout="centered",
)


def _get_api_key_from_env(provider: str) -> str:
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


def _config_signature(provider: str, model_name: str, api_key: str) -> tuple[str, str, str]:
    key_fingerprint = sha256(api_key.encode("utf-8")).hexdigest() if api_key else ""
    return (provider.strip(), model_name.strip(), key_fingerprint)


def _reset_chat(provider: str, model_name: str, api_key: str) -> None:
    st.session_state.session_id = f"streamlit-{uuid4()}"
    st.session_state.store = InMemorySessionStore()
    st.session_state.agent = RetailAssistantAgent(
        st.session_state.store,
        load_customers(),
        provider=provider,
        model_name=model_name,
        api_key=api_key,
    )
    st.session_state.messages = []
    st.session_state.last_response = None
    st.session_state.agent_config = _config_signature(provider, model_name, api_key)


with st.sidebar:
    st.header("Configuracao")
    provider = st.selectbox(
        "Provedor",
        options=SUPPORTED_LLM_PROVIDERS,
        index=SUPPORTED_LLM_PROVIDERS.index(
            os.getenv("ORDER_ASSISTANT_PROVIDER", DEFAULT_LLM_PROVIDER)
            if os.getenv("ORDER_ASSISTANT_PROVIDER", DEFAULT_LLM_PROVIDER) in SUPPORTED_LLM_PROVIDERS
            else DEFAULT_LLM_PROVIDER
        ),
        help="OpenRouter usa uma unica chave para acessar modelos de varios provedores.",
    )

    if st.session_state.get("model_provider") != provider:
        st.session_state.model_name = (
            os.getenv("ORDER_ASSISTANT_MODEL") or DEFAULT_MODEL_BY_PROVIDER[provider]
        )
        st.session_state.model_provider = provider

    api_key = st.text_input(
        "Chave de API",
        value=_get_api_key_from_env(provider),
        type="password",
        key=f"api_key_{provider}",
        help="Tambem pode vir de ORDER_ASSISTANT_API_KEY ou da variavel nativa do provedor.",
    )
    key_hint = provider_key_hint(provider, api_key)
    if key_hint:
        st.warning(key_hint)

    model_name = st.text_input(
        "Modelo",
        key="model_name",
        help="Exemplos: google/gemini-2.5-flash no OpenRouter, gemini-2.5-flash no Gemini direto.",
    )

    if st.button("Nova conversa", use_container_width=True):
        _reset_chat(provider, model_name, api_key)

    st.divider()
    st.subheader("Cliente de teste")
    demo_customer = CUSTOMERS["12345678909"]
    st.code(
        "\n".join(
            [
                f"Nome: {demo_customer['name']}",
                "CPF: 123.456.789-09",
                f"E-mail: {demo_customer['email']}",
                "Pedido rastreavel: PED-1001",
                "Pedido cancelavel: PED-1002",
                "Pedido entregue: PED-1003",
            ]
        ),
        language="text",
    )


if "agent" not in st.session_state:
    _reset_chat(provider, model_name, api_key)

if st.session_state.get("agent_config") != _config_signature(provider, model_name, api_key):
    _reset_chat(provider, model_name, api_key)


st.title("Retail Order Assistant")
st.caption("Chat com verificacao por nome, CPF e e-mail antes de acessar pedidos.")

last_response = st.session_state.get("last_response")
if last_response is not None:
    status = "verificado" if last_response.verified else "nao verificado"
    st.info(f"Sessao {status}. Acoes disponiveis: {', '.join(last_response.actions_available)}")
else:
    st.info("Sessao nao verificada. Envie nome completo, CPF e e-mail cadastrado.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Digite sua mensagem")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando assistente..."):
            response = st.session_state.agent.reply(st.session_state.session_id, prompt)
            st.session_state.last_response = response
            st.markdown(response.assistant_message)

    st.session_state.messages.append(
        {"role": "assistant", "content": st.session_state.last_response.assistant_message}
    )
