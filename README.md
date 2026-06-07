# Retail Order Assistant

Aplicacao para o case tecnico de varejo: um assistente conversacional que verifica
nome completo, CPF e e-mail antes de permitir acoes sobre pedidos.

A versao atual usa:

- FastAPI para o endpoint `/chat`.
- Streamlit para uma interface de chat.
- LangGraph para organizar o fluxo em nos.
- LangChain tools para listar, rastrear, cancelar e verificar status de pedidos.
- Dados mockados em memoria para clientes e pedidos.
- Uma LLM real configurada por provedor, modelo e chave de API.

## Como executar

No PowerShell, dentro desta pasta:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Configure o provedor, a chave da LLM e, se quiser, o modelo:

```powershell
$env:ORDER_ASSISTANT_PROVIDER="openrouter"
$env:ORDER_ASSISTANT_API_KEY="you-api-key"
$env:ORDER_ASSISTANT_MODEL="google/gemini-2.5-flash"
```

Tambem e possivel preencher esses campos pela UI Streamlit.

Provedores suportados:

- `openrouter`: usa `OPENROUTER_API_KEY` ou `ORDER_ASSISTANT_API_KEY`.
  Recomendado quando voce quer uma unica chave para modelos de varios provedores.
  Exemplo de modelo: `google/gemini-2.5-flash`.
- `gemini`: usa `GEMINI_API_KEY`, `GOOGLE_API_KEY` ou `ORDER_ASSISTANT_API_KEY`.
  Exemplo de modelo: `gemini-2.5-flash`.
- `anthropic`: usa `ANTHROPIC_API_KEY` ou `ORDER_ASSISTANT_API_KEY`.
  Exemplo de modelo: `claude-3-5-haiku-latest`.
- `openai`: usa `OPENAI_API_KEY` ou `ORDER_ASSISTANT_API_KEY`.
  Exemplo de modelo: `gpt-4o-mini`.

## UI Streamlit

```powershell
.\.venv\Scripts\python -m streamlit run app\streamlit_app.py
```

A tela permite informar a chave de API e o modelo sem alterar o codigo.

## API FastAPI

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8010
```

Depois abra:

- Documentacao interativa: http://127.0.0.1:8010/docs
- Health check: http://127.0.0.1:8010/health

## Fluxo de demonstracao

Cliente valido:

- Nome: `Rogerio Silva`
- CPF: `123.456.789-09`
- E-mail: `rogerio.silva@example.com`

Pedidos:

- `PED-1001`: pedido rastreavel.
- `PED-1002`: pedido cancelavel.
- `PED-1003`: pedido entregue, nao cancelavel.

Exemplos de mensagens:

```text
quero ver minhas compras
Meu nome e Rogerio Silva, CPF 123.456.789-09 e e-mail rogerio.silva@example.com
cade minha encomenda PED-1001?
nao quero mais a compra PED-1002
qual a situacao do pedido PED-1003?
```

## Arquitetura

O fluxo principal esta em `app/agent.py`.

`verification_node` e o guardrail deterministico. Ele consulta os dados mockados e
so marca a sessao como verificada quando nome, CPF e e-mail batem ao mesmo tempo.
Se a verificacao falha ou esta incompleta, o grafo termina sem chamar as tools de
pedido.

Depois da verificacao, o `agent_node` chama uma LLM via LangChain. A LLM recebe
quatro tools:

- `listar_pedidos`
- `rastrear_pedido`
- `cancelar_pedido`
- `verificar_status_pedido`

Cada tool tem uma descricao ampla, funcionando como uma "super-tool": o modelo
deve escolher a tool mesmo quando o usuario usa sinonimos como "minhas compras",
"cade meu pedido", "desistir da compra" ou "situacao do pedido".

## Observacoes de seguranca

- A LLM nao decide se o usuario esta autenticado.
- A autorizacao acontece antes do agente ter acesso as tools.
- As tools tambem recebem apenas o CPF ja verificado pela sessao.
- Os dados sao mockados e ficam em memoria; reiniciar o processo restaura o estado.
