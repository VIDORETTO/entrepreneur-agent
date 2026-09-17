# Plano de execução — Vendedor Adaptável

Este arquivo é o checkpoint de desenvolvimento do produto. O planejamento do produto continua em `plano-ia-de-vendas.md`; aqui ficam a execução, as evidências e as pendências desta implementação.

## Diagnóstico inicial — 17/09/2026

- O repositório continha somente `plano-ia-de-vendas.md`, `contrato-comportamental-vendas.md`, `briefing-do-negocio.md` e `pesquisa-agentes-de-vendas.md`.
- Não havia código, dependências, banco, configuração ou teste executável.
- O Python disponível é 3.9.25; Python 3.12 também está disponível no ambiente de validação.
- O Farol upstream foi localizado na revisão `81d5dcb2e189d00406cdd9b9e671d94e3f23cd58`. O pacote upstream pede Python >=3.11 e seu perfil RAG é opcional; não será fingida uma instalação upstream quando essa dependência não estiver presente.

## Decisões de implementação

1. Entregar primeiro uma aplicação única local, com CLI e SQLite. A interface pública é o CLI e o `SellerEngine.handle`; módulos internos podem evoluir sem duplicar a máquina de estados.
2. Manter as regras comerciais em código e dados estruturados. O adaptador de modelo interpreta texto e propõe fatos; não autoriza efeitos.
3. Usar um backend persistente compatível com o contrato de evidência do Farol, além de um adaptador opcional para artefatos gerados pelo Farol. O backend em memória só aparece em testes.
4. Usar quatro negócios fictícios versionados para demonstrar físico B2C, oferta B2B direta, serviço consultivo e produto digital.
5. Não instalar nem redistribuir Sales-Skills. O manifesto registra Corey/Matt e as revisões indicadas na especificação.

## Marcos e critérios

| Marco | Saída | Critério de conclusão | Estado |
|---|---|---|---|
| M0 | vocabulário, contrato de execução e plano persistente | termos e limites registrados, sem implementação ambígua | concluído |
| M1 | instalação, diagnóstico e configuração retomável | instalação limpa, checkpoint e retomada em nova execução | concluído |
| M2 | motor de conversa e simuladores | quatro modalidades, estado explícito, ações idempotentes e controles críticos | concluído |
| M3 | conhecimento/Farol e pacote versionado | origem/versão, isolamento, revogação e consulta persistente demonstrados | concluído |
| M4 | avaliação e demonstração | casos obrigatórios executados, relatório com contagens e limitações honestas | concluído |

## Evidência exigida antes da conclusão

- `python -m pip install -e .` e `vendedor doctor` em ambiente limpo.
- `pytest` verde, com cenários do contrato e testes de integração do CLI.
- `vendedor demo` reproduzível para os quatro negócios fictícios.
- `vendedor configure` grava e retoma estado sem repetir respostas já confirmadas.
- Consulta de conhecimento retorna conteúdo, fonte, versão e negócio; fonte revogada e negócio diferente não aparecem.
- `vendedor evaluate` grava relatório distinguindo simuladores, backend persistente/Farol e capacidades não validadas.

## Registro de progresso

- 17/09/2026: documentos de especificação lidos; ambiente diagnosticado; Farol upstream consultado na revisão registrada acima.
- 17/09/2026: pacote Python instalável, CLI, schemas, skills e documentação criados; instalação editable verificada em Python 3.9 e 3.12.
- 17/09/2026: wheel construída e instalada em ambiente virtual limpo; `doctor`, exemplos e conversa passaram sem o checkout de desenvolvimento.
- 17/09/2026: configuração persistente retomada e finalizada em processo separado; quatro demonstrações executadas.
- 17/09/2026: `pytest -q` passou com 19 testes, incluindo correção durante/depois de efeito externo e decisão do dono adiada; `vendedor evaluate` passou 38/38 cenários AC; `model-check` rejeitou ação de cobrança inválida.
- 17/09/2026: Farol upstream executou o fixture local na revisão fixada e produziu dois documentos; `vendedor farol import` recuperou conteúdo com locator e negócio. RAG/MCP opcional segue explicitamente não executado.

## Pendências honestas

- Não há credenciais nem canal real autorizados; checkout, pagamento, agenda, envio e transferência são simuladores com contratos reais de estado.
- Nenhum modelo remoto será declarado compatível sem executar o teste de capacidade correspondente.
- A integração upstream com o RAG opcional do Farol depende de Python 3.11+ e de sua dependência opcional; o produto deve continuar instalável e útil sem ela.
