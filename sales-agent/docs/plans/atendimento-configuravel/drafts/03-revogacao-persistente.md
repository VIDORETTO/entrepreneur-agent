# 03 — Preservar revogação em reimportação e restauração de pacote

**What to build:** Uma fonte revogada continua indisponível após reimportar o mesmo pacote ou restaurar uma configuração anterior.

**Blocked by:** Nenhum — pode iniciar após aprovação do planejamento.

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_delivery_and_governance.py e tests/test_knowledge_and_configuration.py. Reimportação, reinício, reaprovação auditada e restauração passam pelo estado persistente de governança. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US21, US31, US32 da especificação (numeração da lista).

## Acceptance criteria

- [x] Revogação por fonte e por revisão tem escopos distintos e persistentes.
- [x] Reimportação idempotente não remove a decisão de revogação.
- [x] Restauração de pacote comercial respeita a governança atual.
- [x] Reaprovação é operação explícita, auditada e limitada ao escopo autorizado; importar conteúdo não a equivale.
- [x] Negócio diferente e fontes não revogadas continuam consultáveis após reinício.

## TDD

**Seam exercitada:** S2.

**Primeiro red:** Revogar uma fonte, reimportar o pacote que a aprova e consultar; nenhum trecho revogado deve voltar.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Usar a revisão existente como identificador inicialmente; seleção temporal e imutabilidade adicionais pertencem ao T04.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
