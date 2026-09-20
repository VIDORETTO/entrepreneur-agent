# 07 — Configurar uma capacidade por checkpoint orientado a impedimentos

**What to build:** O developer com IA conduz a configuração de uma oferta com decisões do dono, aproveitando material aprovado e retomando sem repetir perguntas.

**Blocked by:** T06 — Descobrir skills de atendimento e configuração no produto instalado

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_skills_and_configuration.py, tests/test_knowledge_and_configuration.py e AC026–AC031. Checkpoints, fatos, adiamento, priorização por capacidade e rascunho seguro são persistentes. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US15, US16, US17, US18, US19 da especificação (numeração da lista).

## Acceptance criteria

- [x] A skill de configuração orienta oferta, próximo passo, fonte de verdade, autonomia e exceções para a capacidade escolhida.
- [x] Fatos confirmados, inferidos, conflitantes e ausentes permanecem distintos.
- [x] Perguntas priorizam o impedimento da capacidade e permitem adiar decisões não críticas.
- [x] Checkpoint retoma decisões e lacunas sem depender do histórico bruto da IA.
- [x] Finalização produz pacote comercial de rascunho sem preço, estoque ou permissão inventados.
- [x] Uma trajetória física direta e uma consultiva demonstram adaptação real do fluxo.

## TDD

**Seam exercitada:** S2.

**Primeiro red:** Iniciar configuração com uma decisão aprovada, retomar em outro processo e confirmar que a próxima pergunta aborda uma lacuna diferente.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Entrevista do dono nunca é carregada como roteiro de qualificação do comprador.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
