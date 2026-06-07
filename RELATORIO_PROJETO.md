# Relatorio tecnico do projeto Retail Order Assistant

Este relatorio descreve todos os arquivos Python existentes no projeto e explica
as funcionalidades, o fluxo de execucao e a logica de implementacao.

Arquivos Python analisados:

- `app/__init__.py`
- `app/agent.py`
- `app/data.py`
- `app/llm_config.py`
- `app/main.py`
- `app/models.py`
- `app/store.py`
- `app/streamlit_app.py`
- `tests/test_agent.py`

## 1. Visao geral

O projeto implementa um assistente conversacional para uma loja virtual. O
usuario conversa com um chatbot para consultar e gerenciar pedidos. A regra
central do case e: nenhuma funcionalidade de pedido pode ser acessada antes da
verificacao de identidade por nome completo, CPF e e-mail.

O sistema tem duas interfaces:

- API HTTP com FastAPI, exposta em `app/main.py`.
- Interface visual com Streamlit, exposta em `app/streamlit_app.py`.

A logica conversacional fica em `app/agent.py`. Esse arquivo usa LangGraph para
modelar o fluxo em nos e LangChain tools para as acoes de pedido. Os dados sao
mockados em memoria em `app/data.py`.

## 2. Fluxo principal da aplicacao

O fluxo esperado e:

1. O usuario envia uma mensagem.
2. A aplicacao recupera ou cria uma sessao pelo `session_id`.
3. O grafo do agente executa primeiro o `verification_node`.
4. Se a sessao ainda nao esta verificada, o no tenta extrair nome, CPF e e-mail.
5. Se os dados estiverem ausentes ou incorretos, o fluxo termina e pede
   verificacao.
6. Se os dados conferem com a base mockada, a sessao recebe o CPF verificado.
7. Depois da verificacao, o grafo chama o `agent_node`.
8. O `agent_node` cria o modelo de LLM conforme o provedor escolhido.
9. O LLM recebe as tools de pedido e decide qual tool chamar.
10. A tool consulta ou altera os dados mockados e retorna a resposta.
11. A resposta final e salva no historico da sessao e enviada ao usuario.

O ponto de seguranca mais importante e que o LLM nao decide se o usuario esta
autenticado. Essa decisao e deterministica e acontece antes de qualquer tool de
pedido estar disponivel.

## 3. Arquivo `app/__init__.py`

Funcao: declarar o diretorio `app` como pacote Python.

Conteudo:

- Apenas uma docstring: `Retail conversational assistant package.`

Logica:

- Nao contem execucao nem regras de negocio.
- Serve para permitir imports como `from app.agent import RetailAssistantAgent`.

## 4. Arquivo `app/data.py`

Funcao: centralizar a base de dados mockada.

Estrutura principal:

- `CUSTOMERS`: dicionario indexado por CPF sem pontuacao.
- `load_customers()`: retorna uma copia profunda dos dados.

Clientes cadastrados:

- `12345678909`: Rogerio Silva, e-mail `rogerio.silva@example.com`.
- `98765432100`: Marina Costa, e-mail `marina.costa@example.com`.

Pedidos de Rogerio Silva:

- `PED-1001`: Smartphone Aurora X, status `Em transporte`.
- `PED-1002`: Fone NoiseBlock Pro, status `Em separacao`.
- `PED-1003`: Cafeteira Smart Brew, status `Entregue`.

Pedido de Marina Costa:

- `PED-2001`: Notebook Atlas 14, status `Aguardando pagamento`.

Logica:

- Os dados sao intencionalmente mockados para demonstracao.
- `load_customers()` usa `deepcopy` para evitar que testes ou sessoes diferentes
  compartilhem alteracoes no mesmo objeto global.
- Isso e relevante porque a tool de cancelamento altera o status do pedido em
  memoria. Sem `deepcopy`, um teste poderia afetar outro.

## 5. Arquivo `app/llm_config.py`

Funcao: centralizar configuracoes de provedores de LLM.

Provedores suportados:

- `openrouter`
- `openai`
- `gemini`
- `anthropic`

Modelos padrao:

- OpenRouter: `google/gemini-2.5-flash`
- OpenAI: `gpt-4o-mini`
- Gemini direto: `gemini-2.5-flash`
- Anthropic: `claude-3-5-haiku-latest`

Funcoes:

- `normalize_provider(provider)`: normaliza o nome do provedor e valida se ele e
  suportado.
- `default_provider()`: le `ORDER_ASSISTANT_PROVIDER`; se nao existir, usa
  `openrouter`.
- `default_model(provider)`: le `ORDER_ASSISTANT_MODEL`; se nao existir, usa o
  modelo padrao do provedor.
- `default_api_key(provider)`: procura chave em `ORDER_ASSISTANT_API_KEY` e nas
  variaveis nativas do provedor.
- `provider_key_hint(provider, api_key)`: detecta combinacoes provavelmente
  erradas, como chave Google/Gemini sendo usada com OpenRouter.

Variaveis de ambiente aceitas:

- Geral: `ORDER_ASSISTANT_API_KEY`, `ORDER_ASSISTANT_PROVIDER`,
  `ORDER_ASSISTANT_MODEL`.
- OpenRouter: `OPENROUTER_API_KEY`.
- OpenAI: `OPENAI_API_KEY`.
- Gemini: `GEMINI_API_KEY` ou `GOOGLE_API_KEY`.
- Anthropic: `ANTHROPIC_API_KEY`.

Logica:

- Esse modulo evita duplicacao entre o agente e a UI.
- A funcao `provider_key_hint` nao valida a chave na internet; ela apenas analisa
  o prefixo e evita erros comuns de configuracao.

## 6. Arquivo `app/models.py`

Funcao: definir os modelos Pydantic usados pela API FastAPI.

Classes:

- `ChatRequest`
- `ChatResponse`
- `HealthResponse`

`ChatRequest`:

- Entrada do endpoint `/chat`.
- Campos:
  - `session_id`: padrao `demo`, minimo 1 caractere.
  - `message`: obrigatorio, minimo 1 caractere.

`ChatResponse`:

- Saida do endpoint `/chat`.
- Campos:
  - `session_id`
  - `verified`
  - `intent`
  - `assistant_message`
  - `actions_available`
  - `customer_name`

`HealthResponse`:

- Saida de `/health` e reset de sessao.
- Campo unico: `status`.

Logica:

- Pydantic valida automaticamente tipos e campos obrigatorios.
- FastAPI usa esses modelos para documentacao automatica e validacao de request
  e response.

## 7. Arquivo `app/store.py`

Funcao: implementar memoria de sessao em RAM.

Classe `SessionState`:

- `session_id`: identificador da conversa.
- `verified_customer_cpf`: CPF do cliente autenticado, ou `None`.
- `failed_verification_attempts`: contador de tentativas falhas.
- `last_intent`: ultima intencao detectada.
- `history`: historico curto de mensagens de usuario e assistente.

Propriedade:

- `is_verified`: retorna `True` se `verified_customer_cpf` nao e `None`.

Classe `InMemorySessionStore`:

- Guarda sessoes em um dicionario `_sessions`.
- `get(session_id)`: recupera uma sessao existente ou cria uma nova.
- `reset(session_id)`: apaga a sessao.

Logica:

- A sessao permite que o usuario verifique identidade uma vez e continue usando
  as funcionalidades sem reenviar nome, CPF e e-mail a cada mensagem.
- Como o armazenamento e em RAM, reiniciar o processo apaga as sessoes.

## 8. Arquivo `app/main.py`

Funcao: expor a API HTTP com FastAPI.

Objetos globais:

- `app`: instancia FastAPI.
- `session_store`: memoria em RAM compartilhada pela API.
- `agent`: instancia de `RetailAssistantAgent`.

Endpoints:

- `GET /health`: retorna `{"status": "ok"}`.
- `POST /chat`: recebe `ChatRequest` e retorna `ChatResponse`.
- `POST /sessions/{session_id}/reset`: limpa a sessao e retorna
  `{"status": "reset"}`.

Logica:

- A camada HTTP e fina: ela nao implementa regra de negocio.
- O endpoint `/chat` delega tudo para `agent.reply(...)`.
- O reset existe para reiniciar demonstracoes ou testes manuais.

## 9. Arquivo `app/streamlit_app.py`

Funcao: criar a UI interativa com Streamlit.

Componentes da sidebar:

- Seletor de provedor (`openrouter`, `openai`, `gemini`, `anthropic`).
- Campo de chave de API.
- Campo de modelo.
- Botao `Nova conversa`.
- Dados do cliente de teste.

Funcoes auxiliares:

- `_get_api_key_from_env(provider)`: busca chave em variaveis de ambiente.
- `_config_signature(provider, model_name, api_key)`: cria uma assinatura da
  configuracao usando SHA-256 da chave, sem expor a chave.
- `_reset_chat(provider, model_name, api_key)`: cria uma nova sessao, novo store,
  novo agente e limpa o historico da UI.

Logica da UI:

- `st.session_state` guarda o agente, a sessao e mensagens da interface.
- Quando provedor, modelo ou chave mudam, a assinatura muda e a conversa e
  reiniciada.
- `provider_key_hint` mostra avisos como "chave Gemini usada com OpenRouter".
- `st.chat_input` captura a mensagem do usuario.
- A UI chama `agent.reply(...)` e renderiza a resposta.

Observacao:

- A UI nao chama a FastAPI. Ela usa o mesmo agente diretamente dentro do processo
  Streamlit.
- Isso simplifica a demo, mas significa que API e UI tem stores separados se
  forem executados em processos diferentes.

## 10. Arquivo `app/agent.py`

Funcao: implementar o cerebro conversacional, o grafo LangGraph, a verificacao
de identidade, os prompts e as LangChain tools.

### 10.1 Imports e dependencias opcionais

O arquivo tenta importar:

- LangChain agent e tools.
- LangGraph.
- Mensagens LangChain.
- Integracoes opcionais:
  - `ChatOpenAI`
  - `ChatOpenRouter`
  - `ChatGoogleGenerativeAI`
  - `ChatAnthropic`

Logica:

- Se LangChain/LangGraph nao estiverem instalados, o sistema nao quebra no
  import; ele retorna uma mensagem de configuracao ao usuario.
- Cada provedor de LLM e opcional, porque nem todo usuario precisa instalar ou
  usar todos.

### 10.2 Prompts

`ORDER_ASSISTANT_SYSTEM_PROMPT`:

- Define o comportamento geral do assistente.
- Obriga resposta em portugues.
- Proibe inventar pedidos, status, prazos ou transportadoras.
- Informa que a identidade ja foi validada antes do LLM receber as tools.

Prompts das tools:

- `LIST_ORDERS_TOOL_PROMPT`
- `TRACK_ORDER_TOOL_PROMPT`
- `CANCEL_ORDER_TOOL_PROMPT`
- `ORDER_STATUS_TOOL_PROMPT`

Logica:

- Esses prompts funcionam como descricoes semanticamente ricas das tools.
- Eles ajudam o LLM a chamar a tool correta mesmo se o usuario usar sinonimos,
  como "minhas compras", "cade meu pedido" ou "nao quero mais essa compra".

### 10.3 Estado do grafo

`AgentGraphState` e um `TypedDict` que representa o estado que passa pelos nos do
grafo.

Campos principais:

- `session_id`
- `user_message`
- `messages`
- `verified`
- `verified_customer_cpf`
- `customer_name`
- `next_node`
- `intent`
- `assistant_message`

Logica:

- O estado acumula dados entre `verification_node` e `agent_node`.
- `next_node` decide se o fluxo segue para o LLM ou termina na verificacao.

### 10.4 Dados de identidade

`IdentityData` e uma dataclass imutavel com:

- `name`
- `cpf`
- `email`

Propriedades:

- `has_any_field`: indica se algum dado de identidade foi encontrado.
- `missing_fields`: lista quais dados ainda faltam.

Logica:

- Ajuda o `verification_node` a responder com mensagens especificas: falta CPF,
  falta e-mail, falta nome etc.

### 10.5 Schemas de entrada das tools

Classes Pydantic:

- `ListOrdersInput`
- `OrderLookupInput`
- `CancelOrderInput`

Logica:

- LangChain usa esses schemas para estruturar os argumentos que o LLM deve passar
  para cada tool.
- `OrderLookupInput` e usado para rastrear e verificar status.
- `CancelOrderInput` inclui `motivo`, opcional, alem de `order_id`.

### 10.6 `verification_node`

Funcao mais importante para seguranca.

Responsabilidades:

- Recuperar a sessao.
- Se a sessao ja esta verificada, liberar o fluxo para `agent_node`.
- Se nao esta verificada, extrair nome, CPF e e-mail da mensagem.
- Se nao houver dados, pedir verificacao.
- Se houver dados incompletos, pedir os campos faltantes.
- Se os dados nao batem com a base mockada, incrementar tentativas falhas.
- Se nome, CPF e e-mail batem, salvar o CPF na sessao e liberar o fluxo.

Logica de autenticacao:

- CPF e a chave primaria da base.
- E-mail e nome sao comparados com normalizacao por `_fold`.
- `_fold` remove acentos e aplica `casefold`, reduzindo problemas com caixa e
  acentuacao.

Garantia importante:

- Se `verification_node` nao definir `next_node = "agent"`, o grafo termina sem
  chamar nenhuma tool de pedido.

### 10.7 Classe `RetailAssistantAgent`

Classe central da aplicacao.

Construtor:

- Recebe `session_store`, dados de clientes, provedor, modelo e chave.
- Normaliza o provedor.
- Define modelo e chave com fallback em variaveis de ambiente.
- Constroi o grafo com `_build_graph()`.

Metodo `reply(session_id, message)`:

1. Recupera a sessao.
2. Normaliza espacos da mensagem.
3. Monta o estado inicial do grafo.
4. Invoca o grafo.
5. Extrai a mensagem final do assistente.
6. Atualiza `last_intent`.
7. Salva usuario e assistente no historico.
8. Retorna um `ChatResponse`.

### 10.8 Construção do grafo

`_build_graph()` cria um `StateGraph`.

Nos:

- `verification_node`
- `agent_node`

Arestas:

- `START -> verification_node`
- `verification_node -> agent_node`, se `next_node == "agent"`
- `verification_node -> END`, se `next_node == "end"`
- `agent_node -> END`

Logica:

- O grafo sempre passa pela verificacao primeiro.
- O LLM so entra no fluxo apos autenticacao bem-sucedida.

### 10.9 `agent_node`

Responsabilidades:

- Verificar se LangChain/LangGraph estao instalados.
- Verificar se existe chave de API.
- Detectar chave aparentemente incompatível com o provedor.
- Bloquear fluxo se nao houver CPF verificado.
- Construir o modelo de chat.
- Criar o agente LangChain com tools.
- Invocar o agente.
- Tratar erros de LLM.

Logica:

- `agent_node` e a ponte entre verificacao deterministica e comportamento
  semantico do LLM.
- O LLM nao recebe a lista de tools antes do usuario estar verificado.

### 10.10 Fabrica de modelos

`_build_chat_model()` instancia o modelo conforme `self.provider`.

Casos:

- `openrouter`: usa `ChatOpenRouter`; se indisponivel, usa `ChatOpenAI` com
  `base_url="https://openrouter.ai/api/v1"`.
- `openai`: usa `ChatOpenAI`.
- `gemini`: usa `ChatGoogleGenerativeAI`.
- `anthropic`: usa `ChatAnthropic`.

Logica:

- A mesma logica de agente e tools pode funcionar com varios provedores.
- O que muda e apenas o adaptador de chat model.

### 10.11 Tools de pedido

`_build_order_tools(customer_cpf)` cria quatro tools LangChain:

1. `listar_pedidos`
2. `rastrear_pedido`
3. `cancelar_pedido`
4. `verificar_status_pedido`

Todas ficam fechadas sobre `customer_cpf`, que ja veio da sessao verificada.
Isso impede que o LLM escolha CPF arbitrario.

#### `listar_pedidos`

Funcao:

- Retorna todos os pedidos do cliente verificado.

Logica:

- Busca o cliente pelo CPF verificado.
- Monta uma lista textual com ID, item, status e total.

#### `rastrear_pedido`

Funcao:

- Retorna status, transportadora, codigo de rastreio e historico.

Logica:

- Normaliza o ID do pedido com `_normalize_order_id`.
- Procura apenas nos pedidos do cliente verificado.
- Se nao encontrar, retorna mensagem de acesso negado/nao encontrado.

#### `cancelar_pedido`

Funcao:

- Cancela pedidos elegiveis.

Logica:

- Busca o pedido no escopo do cliente verificado.
- Se o status for `Entregue` ou `Cancelado`, bloqueia.
- Caso contrario, altera o status para `Cancelado`.
- Adiciona uma entrada no historico de rastreamento.

#### `verificar_status_pedido`

Funcao:

- Retorna um resumo do pedido: status, item, total e transportadora.

Logica:

- E mais simples que rastreamento, pois nao retorna o historico completo.

### 10.12 Utilitarios do agente

- `_find_order`: procura pedido dentro do cliente verificado.
- `_build_langchain_messages`: converte historico da sessao para mensagens
  LangChain, usando no maximo as ultimas 12 mensagens.
- `_available_actions`: retorna as acoes disponiveis antes ou depois da
  verificacao.
- `_infer_final_intent`: tenta inferir a intencao final a partir da tool chamada.
- `_MissingDependencyGraph`: fallback se LangGraph nao estiver instalado.
- `extract_identity`: coordena extracao de nome, CPF e e-mail.
- `_extract_name`: tenta encontrar nome conhecido ou padrao textual como
  "Meu nome e ...".
- `_extract_cpf`: extrai CPF com ou sem pontuacao.
- `_extract_email`: extrai e-mail por regex.
- `_normalize_order_id`: aceita `PED-1001`, `PED1001` ou `1001`.
- `_current_customer`: retorna cliente da sessao verificada.
- `_verification_prompt`: monta mensagem padrao pedindo identidade.
- `_extract_last_ai_text`: extrai a ultima resposta textual do LLM.
- `_content_to_text`: converte formatos de conteudo LangChain para string.
- `_format_llm_error`: transforma erros de modelo/chave em mensagens mais
  amigaveis.
- `_fold`: remove acentos e normaliza caixa para comparacao.

## 11. Arquivo `tests/test_agent.py`

Funcao: validar o comportamento principal offline, sem chamar API externa.

Testes:

- `test_blocks_order_actions_before_verification`
- `test_verifies_customer_with_name_cpf_and_email`
- `test_order_tools_use_verified_customer_scope`
- `test_cancel_tool_updates_order_status`

Logica dos testes:

- O agente e criado com `api_key=""`, evitando chamadas reais a LLM.
- O primeiro teste confirma que pedidos sao bloqueados antes da verificacao.
- O segundo confirma verificacao por nome, CPF e e-mail.
- O terceiro chama as tools diretamente e confirma que um pedido de outro cliente
  nao aparece no escopo do cliente verificado.
- O quarto confirma que cancelar `PED-1002` altera o status para `Cancelado`.

Esses testes validam as regras deterministicas e as tools, mas nao validam a
qualidade de decisao do LLM, pois isso dependeria de chave, modelo e rede.

## 12. Funcionalidades existentes

### Verificacao de identidade

Entrada esperada:

```text
Meu nome e Rogerio Silva, CPF 123.456.789-09 e e-mail rogerio.silva@example.com
```

Campos exigidos:

- Nome completo.
- CPF.
- E-mail.

Resultado:

- Se correto, a sessao passa a ter `verified_customer_cpf`.
- Se incorreto ou incompleto, as tools continuam bloqueadas.

### Listar pedidos

Exemplos de mensagem:

- "listar meus pedidos"
- "quero ver minhas compras"
- "quais compras eu tenho?"

Tool chamada:

- `listar_pedidos`

### Rastrear pedido

Exemplos:

- "rastrear PED-1001"
- "cade meu pedido PED1001?"
- "onde esta a encomenda 1001?"

Tool chamada:

- `rastrear_pedido`

### Cancelar pedido

Exemplos:

- "cancelar PED-1002"
- "nao quero mais a compra PED-1002"
- "desisti do pedido 1002"

Tool chamada:

- `cancelar_pedido`

Regras:

- Pedido entregue nao pode ser cancelado.
- Pedido ja cancelado nao pode ser cancelado novamente.
- Pedido elegivel tem status alterado em memoria.

### Verificar status

Exemplos:

- "qual o status do PED-1001?"
- "situacao do pedido 1001"
- "meu pedido foi enviado?"

Tool chamada:

- `verificar_status_pedido`

## 13. Seguranca e autorizacao

O desenho separa duas responsabilidades:

- Verificacao/autorizacao: deterministica, em `verification_node`.
- Interpretacao semantica: feita pelo LLM apos a verificacao.

Isso e importante porque o LLM pode errar interpretacao, mas nao deve ter poder
para liberar acesso a dados sensiveis. A verificacao ocorre antes da criacao e
invocacao das tools de pedido.

As tools tambem sao protegidas por escopo:

- Elas recebem apenas `customer_cpf` ja verificado.
- O LLM nao passa CPF como argumento.
- `_find_order` procura pedidos somente dentro do cliente verificado.

## 14. Limitacoes atuais

- Os dados sao mockados e ficam em memoria.
- Cancelamentos nao persistem depois de reiniciar o processo.
- Nao ha banco de dados, autenticacao real, logs persistentes ou auditoria real.
- A decisao de qual tool chamar depende do modelo de LLM escolhido.
- Os testes nao chamam provedores externos.
- API FastAPI e UI Streamlit usam agentes/stores separados quando executados em
  processos diferentes.
- A extracao de nome usa regex simples e busca em nomes conhecidos; para producao,
  isso exigiria formulario estruturado ou fluxo de coleta mais robusto.
- O reconhecimento de prefixos de chave em `provider_key_hint` e apenas heuristico.

## 15. Resumo da arquitetura

```text
Usuario
  |
  | Streamlit UI ou FastAPI /chat
  v
RetailAssistantAgent.reply()
  |
  v
LangGraph StateGraph
  |
  +--> verification_node
         |
         +--> falha/incompleto: END com pedido de verificacao
         |
         +--> sucesso: agent_node
                       |
                       +--> cria chat model do provedor
                       +--> cria agente LangChain
                       +--> disponibiliza tools de pedido
                       +--> retorna resposta final
```

## 16. Conclusao

O projeto implementa corretamente o requisito central do case: um assistente
conversacional de pedidos cuja consulta e acao dependem de verificacao previa de
identidade. A implementacao atual e adequada para demonstracao tecnica porque
separa bem:

- interface HTTP;
- interface visual;
- dados mockados;
- estado de sessao;
- configuracao de LLM;
- verificacao deterministica;
- tools de negocio;
- interpretacao por LLM.

O componente mais importante do projeto e `verification_node`, pois ele impede
que a LLM ou as tools acessem pedidos antes da validacao de nome, CPF e e-mail.
