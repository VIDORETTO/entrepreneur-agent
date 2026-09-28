# Revisão TK-008

Baseline fixo: `9cf0f9c` (HEAD antes do ticket). Foram examinados worktree,
arquivos novos, staging (vazio), diff de commits (vazio) e `git diff --check`.
O contrato atual foi conferido em
`https://developers.openai.com/api/docs/guides/structured-outputs` em
28/09/2026: Chat Completions aceita `response_format` com `json_schema`,
`strict: true`, campos obrigatórios e `additionalProperties: false`; recusa é
uma saída distinta do JSON. O nome do modelo continua configurável.

## Standards

Sem achados bloqueantes. Instruções e pacote ficam em papel `system`; o texto
do comprador fica no papel `user` delimitado. O parser ainda valida o objeto
e os valores de domínio. A chave vem de `env:NOME` no arquivo de configuração
e o cabeçalho de autorização não é copiado em redirecionamentos. O fallback
de contrato inválido é registrado e o motor não executa ações nesse caso.
Testes só usam resposta HTTP falsa; não houve chamada real à OpenAI.

## Spec

AC-019: papéis separados e schema estrito verificados no corpo da requisição.
AC-020: uma resposta inválida seguida de válida gerou duas chamadas e uma
instrução de reparo. AC-021: duas respostas inválidas geraram trace
`model_contract_failed` e nenhuma ação. AC-022: 1000 tokens de entrada e 200
de saída a preços 1/5 por milhão resultaram em custo 0,002. AC-023: os dois
perfis passaram no contrato local e identificaram perfil e modelo. Sem achados
bloqueantes para o contrato local.

Limitações: a API real e suporte do modelo escolhido a Structured Outputs não
foram verificados por ausência de credencial na execução. O teste do perfil
compatível usa servidor falso. A prova de latência registra a duração local da
chamada; não estabelece meta de desempenho externa. EV-059–EV-063 são as
evidências atuais. A regressão final passou com 205 testes e Ruff verde.

Revalidação após TK-012: `cli.py` ganhou apenas opções de `evaluate`; o caminho
`model-check` e o contrato HTTP não mudaram. EV-070–EV-074 reconfirmaram os
cinco ACs com 23 testes do adaptador. Sem novo achado bloqueante.
