# 17 — Avaliar o atendimento e o modelo selecionado com evidência reproduzível

**What to build:** O dono compara configurações/modelos por qualidade factual, comportamento, custo e latência, distinguindo simulação de execução real.

**Blocked by:** T12 — Redigir respostas completas com evidência e pergunta necessária; T08 — Inspecionar, simular e promover uma configuração revisada

**Status:** concluído localmente; modelo remoto pendente.

**Evidência registrada:** Evidência: evaluation/golden_set.json, src/sales_agent/evaluation.py, tests/test_cli_and_evaluation.py e reports/evaluation-latest.json. Os 38 casos sintéticos passaram; remoto, Farol upstream e Chatwoot ficam not-executed. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US22, US44, US45, US48 da especificação (numeração da lista).

## Acceptance criteria

- [x] Golden set sintético versionado inclui as quatro regressões, correções, perguntas múltiplas, objeções, isolamento e falhas de contrato.
- [x] Cada caso possui expectativa independente: resposta/abstenção, afirmações proibidas, evidência e operações permitidas.
- [x] Verificação do modelo selecionado é distinta da prova de rejeição de ações adversariais.
- [x] Relatório registra pacote, skills, corpus, modelo, revisão, falhas, latência e custo disponível sem segredos.
- [x] Limiares de avaliação são definidos antes da execução do candidato; falhas críticas impedem elegibilidade.
- [x] Execução externa ausente aparece como não executada, e não como aprovação por fake.

## TDD

**Seam exercitada:** S2.

**Primeiro red:** Selecionar um adaptador externo de contrato e executar a avaliação; o relatório identifica esse adaptador e não apresenta somente a prova adversarial local.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Suite extensível permite adicionar Farol e canal quando estiverem disponíveis, sem bloquear esta entrega no T16.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
