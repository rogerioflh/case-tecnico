**Cenário:** Uma empresa de varejo está desenvolvendo um serviço back-end em Python utilizando FastAPI. Este serviço irá expor um endpoint que utiliza frameworks de IA para ajudar 
clientes a gerenciarem seus pedidos por meio de uma interface conversacional.

**Sua Tarefa*:* Implemente um agente de IA conversacional que suporte o seguinte fluxo de interação: 
1.  Verificação do Usuário: O assistente deve primeiro verificar a identidade do cliente usando seu nome completo, CPF e e-mail cadastrado;

2.  Listar Pedidos: Esta ação deve estar disponível somente após a verificação bem-sucedida do usuário;

3.  Rastrear Pedido: Esta ação deve estar disponível somente após a verificação bem-sucedida do usuário;

4.  Cancelar Pedido: Esta ação deve estar disponível somente após a verificação bem-sucedida do usuário.

**Requisitos:** 
-  O endpoint deve simular uma experiência conversacional entre o cliente e o assistente 
de IA (se não souber o que é FastAPI, endpoints pode fazer no jupyter notebook). 
-  O acesso às ações relacionadas a pedidos (listar, rastrear, cancelar) deve ser 
estritamente condicionado à verificação bem-sucedida da identidade; 
-  Você pode utilizar qualquer framework de IA conversacional de sua preferência, como  LangChain ou LangGraph, para implementar a lógica do agente. 

**Orientações:**  
-  Considere a pessoa que interage com o endpoint como um cliente de uma loja virtual. 

- O assistente deve guiá-lo pelo processo passo a passo começando pela verificação de  identidade  antes de conceder acesso às funcionalidades de gerenciamento de pedidos.