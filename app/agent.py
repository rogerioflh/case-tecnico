from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

from app.data import load_customers
from app.llm_config import (
    DEFAULT_LLM_API_KEY,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    default_api_key,
    default_model,
    normalize_provider,
    provider_key_hint,
)
from app.models import ChatResponse
from app.store import InMemorySessionStore, SessionState

try:
    from langchain.agents import create_agent
    from langchain.tools import tool
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
    from langgraph.graph import END, START, StateGraph
except ImportError as exc:  # pragma: no cover - exercised before dependencies are installed
    LANGCHAIN_IMPORT_ERROR: ImportError | None = exc
    create_agent = None  # type: ignore[assignment]
    tool = None  # type: ignore[assignment]
    AIMessage = None  # type: ignore[assignment]
    HumanMessage = None  # type: ignore[assignment]
    BaseMessage = Any  # type: ignore[misc,assignment]
    StateGraph = None  # type: ignore[assignment]
    START = "__start__"  # type: ignore[assignment]
    END = "__end__"  # type: ignore[assignment]
else:
    LANGCHAIN_IMPORT_ERROR = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - optional provider integration
    ChatOpenAI = None  # type: ignore[assignment]

try:
    from langchain_openrouter import ChatOpenRouter
except ImportError:  # pragma: no cover - optional provider integration
    ChatOpenRouter = None  # type: ignore[assignment]

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:  # pragma: no cover - optional provider integration
    ChatGoogleGenerativeAI = None  # type: ignore[assignment]

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # pragma: no cover - optional provider integration
    ChatAnthropic = None  # type: ignore[assignment]


ORDER_ASSISTANT_SYSTEM_PROMPT = """
Voce e um assistente conversacional de uma loja virtual.

Regras obrigatorias:
- Responda em portugues do Brasil.
- A identidade ja foi verificada por um no deterministico antes de voce receber a conversa.
- Nunca solicite dados sensiveis novamente se o usuario ja estiver verificado.
- Use as tools para qualquer consulta ou acao sobre pedidos.
- Nao invente pedidos, status, prazos, transportadoras ou politicas.
- Se faltar o codigo do pedido, pergunte pelo codigo no formato PED-1001.
- Para cancelamento, confirme claramente o resultado retornado pela tool.
- Seja curto, util e direto, como um atendimento por chat.
""".strip()

LIST_ORDERS_TOOL_PROMPT = """
Super-tool para listar pedidos do cliente verificado.

Use quando o usuario quiser ver compras, historico, encomendas, pedidos em aberto,
"minhas compras", "o que eu comprei", "quais pedidos tenho", ou formulacoes
equivalentes, mesmo sem usar literalmente a palavra listar.

A tool nao recebe CPF, email ou nome: a autorizacao vem do verification_node.
Retorne todos os pedidos disponiveis para a conta verificada.
""".strip()

TRACK_ORDER_TOOL_PROMPT = """
Super-tool para rastrear entrega de um pedido do cliente verificado.

Use quando o usuario quiser acompanhar entrega, saber onde esta, obter rastreio,
transportadora, codigo de rastreamento, historico logistico, prazo de entrega,
"cade meu pedido", "minha encomenda chegou?", ou equivalentes.

Entrada obrigatoria: codigo do pedido. Extraia formatos como PED-1001, PED1001
ou apenas 1001 quando o contexto indicar pedido.
""".strip()

CANCEL_ORDER_TOOL_PROMPT = """
Super-tool para cancelar um pedido do cliente verificado.

Use quando o usuario manifestar intencao de cancelar, desistir, suspender,
interromper, devolver antes do envio, nao querer mais a compra, pedir estorno
por cancelamento, ou outra formulacao equivalente, mesmo sem usar a palavra
cancelar.

Entrada obrigatoria: codigo do pedido. A tool decide se o status permite
cancelamento; o LLM nao deve prometer cancelamento antes do retorno da tool.
""".strip()

ORDER_STATUS_TOOL_PROMPT = """
Super-tool para verificar o status resumido de um pedido do cliente verificado.

Use quando o usuario perguntar situacao, andamento, estado atual, se foi pago,
se foi separado, se foi enviado, se foi entregue, se esta cancelado, ou qualquer
consulta de status que nao precise do historico completo de rastreamento.

Entrada obrigatoria: codigo do pedido.
""".strip()


class AgentGraphState(TypedDict, total=False):
    session_id: str
    user_message: str
    messages: list[BaseMessage]
    verified: bool
    verified_customer_cpf: str | None
    customer_name: str | None
    next_node: Literal["agent", "end"]
    intent: str
    assistant_message: str


@dataclass(frozen=True)
class IdentityData:
    name: str | None
    cpf: str | None
    email: str | None

    @property
    def has_any_field(self) -> bool:
        return bool(self.name or self.cpf or self.email)

    @property
    def missing_fields(self) -> list[str]:
        missing = []
        if not self.name:
            missing.append("nome completo")
        if not self.cpf:
            missing.append("CPF")
        if not self.email:
            missing.append("e-mail cadastrado")
        return missing


class ListOrdersInput(BaseModel):
    observacao: str | None = Field(
        default=None,
        description="Resumo opcional do que o cliente pediu ao solicitar a lista.",
    )


class OrderLookupInput(BaseModel):
    order_id: str = Field(
        description="Codigo do pedido, aceitando formatos como PED-1001, PED1001 ou 1001.",
    )


class CancelOrderInput(BaseModel):
    order_id: str = Field(
        description="Codigo do pedido, aceitando formatos como PED-1001, PED1001 ou 1001.",
    )
    motivo: str | None = Field(
        default=None,
        description="Motivo informado pelo cliente, se houver.",
    )


def verification_node(
    graph_state: AgentGraphState,
    session_store: InMemorySessionStore,
    customers: dict[str, dict[str, Any]],
) -> AgentGraphState:
    """Gatekeeper node: validates name, CPF and email before protected tools run."""

    session = session_store.get(graph_state["session_id"])
    customer = _current_customer(session, customers)
    if customer:
        return {
            **graph_state,
            "verified": True,
            "verified_customer_cpf": session.verified_customer_cpf,
            "customer_name": customer["name"],
            "next_node": "agent",
        }

    identity = extract_identity(graph_state["user_message"], customers)
    if not identity.has_any_field:
        return {
            **graph_state,
            "verified": False,
            "next_node": "end",
            "intent": "verify_identity",
            "assistant_message": _verification_prompt(
                "Antes de acessar informacoes de pedidos, preciso verificar sua identidade."
            ),
        }

    missing = identity.missing_fields
    if missing:
        return {
            **graph_state,
            "verified": False,
            "next_node": "end",
            "intent": "verify_identity",
            "assistant_message": _verification_prompt(
                f"Ainda falta informar: {', '.join(missing)}."
            ),
        }

    matched_customer = customers.get(identity.cpf or "")
    if (
        not matched_customer
        or _fold(matched_customer["email"]) != _fold(identity.email or "")
        or _fold(matched_customer["name"]) != _fold(identity.name or "")
    ):
        session.failed_verification_attempts += 1
        return {
            **graph_state,
            "verified": False,
            "next_node": "end",
            "intent": "verify_identity_failed",
            "assistant_message": _verification_prompt(
                "Nao consegui validar esses dados. Confira nome, CPF e e-mail cadastrado."
            ),
        }

    session.verified_customer_cpf = identity.cpf
    return {
        **graph_state,
        "verified": True,
        "verified_customer_cpf": identity.cpf,
        "customer_name": matched_customer["name"],
        "next_node": "agent",
        "intent": "verified",
    }


class RetailAssistantAgent:
    """LangGraph workflow with a deterministic verification gate and LangChain tools."""

    def __init__(
        self,
        session_store: InMemorySessionStore,
        customers: dict[str, dict[str, Any]] | None = None,
        provider: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.session_store = session_store
        self.customers = customers or load_customers()
        self.provider = normalize_provider(provider or DEFAULT_LLM_PROVIDER)
        self.model_name = model_name or default_model(self.provider)
        self.api_key = api_key if api_key is not None else default_api_key(self.provider)
        self.graph = self._build_graph()

    def reply(self, session_id: str, message: str) -> ChatResponse:
        session = self.session_store.get(session_id)
        normalized_message = " ".join(message.strip().split())
        graph_input: AgentGraphState = {
            "session_id": session_id,
            "user_message": normalized_message,
            "messages": self._build_langchain_messages(session, normalized_message),
            "verified": session.is_verified,
            "verified_customer_cpf": session.verified_customer_cpf,
            "intent": "start",
        }

        result = self.graph.invoke(graph_input)
        assistant_message = result.get("assistant_message") or (
            "Nao consegui gerar uma resposta. Tente reformular sua mensagem."
        )

        session.last_intent = result.get("intent", "unknown")
        session.history.append({"role": "user", "content": normalized_message})
        session.history.append({"role": "assistant", "content": assistant_message})

        customer = _current_customer(session, self.customers)
        return ChatResponse(
            session_id=session_id,
            verified=session.is_verified,
            intent=session.last_intent,
            assistant_message=assistant_message,
            actions_available=self._available_actions(session),
            customer_name=customer["name"] if customer else None,
        )

    def _build_graph(self) -> Any:
        if StateGraph is None:
            return _MissingDependencyGraph()

        workflow = StateGraph(AgentGraphState)
        workflow.add_node(
            "verification_node",
            lambda state: verification_node(state, self.session_store, self.customers),
        )
        workflow.add_node("agent_node", self._agent_node)
        workflow.add_edge(START, "verification_node")
        workflow.add_conditional_edges(
            "verification_node",
            lambda state: state.get("next_node", "end"),
            {"agent": "agent_node", "end": END},
        )
        workflow.add_edge("agent_node", END)
        return workflow.compile()

    def _agent_node(self, graph_state: AgentGraphState) -> AgentGraphState:
        if LANGCHAIN_IMPORT_ERROR is not None:
            return {
                **graph_state,
                "intent": "configuration_error",
                "assistant_message": (
                    "As dependencias LangChain/LangGraph ainda nao estao instaladas. "
                    "Execute: .\\.venv\\Scripts\\python -m pip install -r requirements.txt"
                ),
            }

        if not self.api_key:
            return {
                **graph_state,
                "intent": "configuration_error",
                "assistant_message": (
                    "Configure a chave da LLM antes de conversar. Informe a chave na UI "
                    f"Streamlit ou use uma variavel de ambiente compativel com {self.provider}."
                ),
            }

        key_hint = provider_key_hint(self.provider, self.api_key)
        if key_hint:
            return {
                **graph_state,
                "intent": "configuration_error",
                "assistant_message": key_hint,
            }

        customer_cpf = graph_state.get("verified_customer_cpf")
        if not customer_cpf:
            return {
                **graph_state,
                "intent": "authorization_blocked",
                "assistant_message": _verification_prompt(
                    "Sua sessao ainda nao esta verificada."
                ),
            }

        try:
            model = self._build_chat_model()
        except RuntimeError as exc:
            return {
                **graph_state,
                "intent": "configuration_error",
                "assistant_message": str(exc),
            }

        llm_agent = create_agent(
            model=model,
            tools=self._build_order_tools(customer_cpf),
            system_prompt=ORDER_ASSISTANT_SYSTEM_PROMPT,
        )
        try:
            result = llm_agent.invoke({"messages": graph_state["messages"]})
        except Exception as exc:  # pragma: no cover - depends on external provider
            return {
                **graph_state,
                "intent": "llm_error",
                "assistant_message": _format_llm_error(exc),
            }

        return {
            **graph_state,
            "intent": self._infer_final_intent(result),
            "assistant_message": _extract_last_ai_text(result),
        }

    def _build_chat_model(self) -> Any:
        if self.provider == "openrouter":
            os.environ["OPENROUTER_API_KEY"] = self.api_key
            if ChatOpenRouter is not None:
                return ChatOpenRouter(model=self.model_name, temperature=0, max_retries=2)
            if ChatOpenAI is not None:
                return ChatOpenAI(
                    model=self.model_name,
                    api_key=self.api_key,
                    base_url="https://openrouter.ai/api/v1",
                    temperature=0,
                )
            raise RuntimeError(
                "Instale langchain-openrouter ou langchain-openai para usar OpenRouter."
            )

        if self.provider == "openai":
            if ChatOpenAI is None:
                raise RuntimeError("Instale langchain-openai para usar OpenAI.")
            return ChatOpenAI(model=self.model_name, api_key=self.api_key, temperature=0)

        if self.provider == "gemini":
            if ChatGoogleGenerativeAI is None:
                raise RuntimeError("Instale langchain-google-genai para usar Gemini.")
            return ChatGoogleGenerativeAI(model=self.model_name, api_key=self.api_key, temperature=0)

        if self.provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = self.api_key
            if ChatAnthropic is None:
                raise RuntimeError("Instale langchain-anthropic para usar Claude/Anthropic.")
            return ChatAnthropic(
                model=self.model_name,
                api_key=self.api_key,
                temperature=0,
                max_tokens=1024,
            )

        raise RuntimeError(f"Provedor nao suportado: {self.provider}.")

    def _build_order_tools(self, customer_cpf: str) -> list[Any]:
        if tool is None:
            return []

        def guarded_customer() -> dict[str, Any] | None:
            return self.customers.get(customer_cpf)

        @tool("listar_pedidos", args_schema=ListOrdersInput, description=LIST_ORDERS_TOOL_PROMPT)
        def listar_pedidos(observacao: str | None = None) -> str:
            customer = guarded_customer()
            if not customer:
                return "A sessao nao esta verificada. Bloqueie a acao e solicite verificacao."

            lines = [f"Encontrei {len(customer['orders'])} pedido(s) para {customer['name']}:"]
            for order in customer["orders"]:
                lines.append(
                    f"- {order['id']} | {order['item']} | {order['status']} | {order['total']}"
                )
            return "\n".join(lines)

        @tool("rastrear_pedido", args_schema=OrderLookupInput, description=TRACK_ORDER_TOOL_PROMPT)
        def rastrear_pedido(order_id: str) -> str:
            order = self._find_order(customer_cpf, order_id)
            normalized_order_id = _normalize_order_id(order_id)
            if not order:
                return f"Nao encontrei o pedido {normalized_order_id} na conta verificada."

            history = "\n".join(f"- {item}" for item in order["tracking_history"])
            return (
                f"Status do {order['id']}: {order['status']}.\n"
                f"Transportadora: {order['carrier']}.\n"
                f"Codigo de rastreio: {order['tracking_code']}.\n"
                f"Historico:\n{history}"
            )

        @tool("cancelar_pedido", args_schema=CancelOrderInput, description=CANCEL_ORDER_TOOL_PROMPT)
        def cancelar_pedido(order_id: str, motivo: str | None = None) -> str:
            order = self._find_order(customer_cpf, order_id)
            normalized_order_id = _normalize_order_id(order_id)
            if not order:
                return f"Nao encontrei o pedido {normalized_order_id} na conta verificada."

            status = _fold(order["status"])
            if status in {"entregue", "cancelado"}:
                return (
                    f"O pedido {order['id']} esta com status '{order['status']}' "
                    "e nao pode ser cancelado."
                )

            order["status"] = "Cancelado"
            audit_message = "Cancelamento solicitado pelo atendimento conversacional"
            if motivo:
                audit_message = f"{audit_message}. Motivo informado: {motivo}"
            order["tracking_history"].append(audit_message)
            return (
                f"Cancelamento solicitado com sucesso para o pedido {order['id']}. "
                "O status foi atualizado para 'Cancelado'."
            )

        @tool(
            "verificar_status_pedido",
            args_schema=OrderLookupInput,
            description=ORDER_STATUS_TOOL_PROMPT,
        )
        def verificar_status_pedido(order_id: str) -> str:
            order = self._find_order(customer_cpf, order_id)
            normalized_order_id = _normalize_order_id(order_id)
            if not order:
                return f"Nao encontrei o pedido {normalized_order_id} na conta verificada."

            return (
                f"Pedido {order['id']}: {order['status']}.\n"
                f"Item: {order['item']}.\n"
                f"Total: {order['total']}.\n"
                f"Transportadora: {order['carrier']}."
            )

        return [listar_pedidos, rastrear_pedido, cancelar_pedido, verificar_status_pedido]

    def _find_order(self, customer_cpf: str, order_id: str) -> dict[str, Any] | None:
        customer = self.customers.get(customer_cpf)
        if not customer:
            return None

        normalized = _normalize_order_id(order_id)
        for order in customer["orders"]:
            if order["id"].upper() == normalized:
                return order
        return None

    def _build_langchain_messages(
        self,
        session: SessionState,
        user_message: str,
    ) -> list[BaseMessage]:
        if HumanMessage is None or AIMessage is None:
            return []

        messages: list[BaseMessage] = []
        for item in session.history[-12:]:
            if item["role"] == "user":
                messages.append(HumanMessage(content=item["content"]))
            elif item["role"] == "assistant":
                messages.append(AIMessage(content=item["content"]))
        messages.append(HumanMessage(content=user_message))
        return messages

    def _available_actions(self, session: SessionState) -> list[str]:
        if not session.is_verified:
            return ["verify_identity"]
        return [
            "listar_pedidos",
            "rastrear_pedido",
            "cancelar_pedido",
            "verificar_status_pedido",
        ]

    @staticmethod
    def _infer_final_intent(result: dict[str, Any]) -> str:
        messages = result.get("messages", [])
        for message in reversed(messages):
            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                first_call = tool_calls[0]
                return first_call.get("name", "tool_call")
        return "llm_chat"


class _MissingDependencyGraph:
    def invoke(self, state: AgentGraphState) -> AgentGraphState:
        return {
            **state,
            "intent": "configuration_error",
            "assistant_message": (
                "As dependencias LangChain/LangGraph ainda nao estao instaladas. "
                "Execute: .\\.venv\\Scripts\\python -m pip install -r requirements.txt"
            ),
        }


def extract_identity(text: str, customers: dict[str, dict[str, Any]]) -> IdentityData:
    return IdentityData(
        name=_extract_name(text, customers),
        cpf=_extract_cpf(text),
        email=_extract_email(text),
    )


def _extract_name(text: str, customers: dict[str, dict[str, Any]]) -> str | None:
    folded_text = _fold(text)
    for customer in customers.values():
        if _fold(customer["name"]) in folded_text:
            return customer["name"]

    match = re.search(
        r"(?:meu nome\s+(?:e|eh|esta como)|sou|me chamo|nome\s*[:=])\s+"
        r"(.+?)(?:,|;|\s+cpf|\s+e-?mail|\s+email|$)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).strip()


def _extract_cpf(text: str) -> str | None:
    match = re.search(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", text)
    if not match:
        return None
    return re.sub(r"\D", "", match.group(0))


def _extract_email(text: str) -> str | None:
    match = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text)
    return match.group(0).lower() if match else None


def _normalize_order_id(order_id: str) -> str:
    match = re.search(r"(?:PED[-\s]?)?(\d{4})", order_id, re.IGNORECASE)
    if match:
        return f"PED-{match.group(1)}"
    return order_id.strip().upper()


def _current_customer(
    session: SessionState,
    customers: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not session.verified_customer_cpf:
        return None
    return customers.get(session.verified_customer_cpf)


def _verification_prompt(prefix: str) -> str:
    return (
        f"{prefix} Envie nome completo, CPF e e-mail cadastrado. "
        "Exemplo: Meu nome e Rogerio Silva, CPF 123.456.789-09 e "
        "e-mail rogerio.silva@example.com."
    )


def _extract_last_ai_text(result: dict[str, Any]) -> str:
    messages = result.get("messages", [])
    for message in reversed(messages):
        if getattr(message, "type", None) == "ai":
            return _content_to_text(getattr(message, "content", ""))
    if messages:
        return _content_to_text(getattr(messages[-1], "content", ""))
    return "Nao consegui gerar uma resposta."


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content)


def _format_llm_error(exc: Exception) -> str:
    error_text = str(exc).casefold()
    if "401" in error_text or "invalid_api_key" in error_text or "incorrect api key" in error_text:
        return (
            "Nao consegui autenticar na API da LLM. Confira se a chave foi copiada "
            "inteira, se ainda esta ativa e se pertence ao provedor do modelo selecionado. "
            "Depois de trocar a chave, inicie uma nova conversa."
        )
    if "model" in error_text and ("not found" in error_text or "does not exist" in error_text):
        return (
            "Nao consegui acessar o modelo configurado. Confira se o nome do modelo "
            "esta correto e se sua chave tem permissao para usa-lo."
        )
    return (
        "Nao consegui chamar a LLM agora. Verifique modelo, chave de API e conectividade. "
        f"Tipo do erro: {type(exc).__name__}."
    )


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_accents.casefold()
