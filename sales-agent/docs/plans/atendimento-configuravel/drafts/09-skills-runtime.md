# 09 — Aplicar skills aprovadas na interpretação do atendimento

**What to build:** O atendimento usa as orientações elegíveis do pacote e permite verificar quais skills participaram da decisão.

**Blocked by:** T06 — Descobrir skills de atendimento e configuração no produto instalado

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_skills_and_configuration.py e tests/test_model_adapter.py. O trace separa declarada, selecionada e aplicada; orçamento, versão e público são verificados antes do adaptador. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US23, US29, US47 da especificação (numeração da lista).

## Acceptance criteria

- [x] Seleção respeita negócio, público, gatilho, versão e orçamento de contexto.
- [x] O adaptador de interpretação recebe somente orientações de atendimento elegíveis; configuração interna não entra nesse contexto.
- [x] Trace público de diagnóstico distingue declarada, selecionada e aplicada, sem expor conteúdo sensível ao comprador.
- [x] Skill ausente/incompatível bloqueia a capacidade dependente ou informa degradação explícita.
- [x] Uma instrução de skill para executar ação proibida não vence as capacidades estruturadas.
- [x] Modo determinístico continua disponível e declara honestamente quais orientações consegue aplicar.

## TDD

**Seam exercitada:** S1 e S2.

**Primeiro red:** Selecionar uma skill de atendimento em um pacote e executar uma conversa pelo adaptador de modelo de contrato; o contexto permitido contém sua orientação e o resultado registra a versão aplicada.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

A redação final orientada por skill pertence ao T12; este ticket conclui o caminho de seleção até interpretação observável.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
