# 12 — Redigir respostas completas com evidência e pergunta necessária

**What to build:** O comprador recebe uma resposta natural que cobre suas perguntas, preserva fatos aprovados e não repete coleta já concluída.

**Blocked by:** T05 — Responder apenas ao que a evidência recuperada sustenta; T09 — Aplicar skills aprovadas na interpretação do atendimento; T11 — Agrupar mensagens consecutivas e preservar todas as perguntas

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_turns_and_profiles.py, tests/test_conversation_contract.py e tests/test_model_adapter.py. A composição mantém fatos, evidências e capacidades estruturadas fora da autoridade do redator. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US01, US02, US03, US08, US09, US13, US14, US47 da especificação (numeração da lista).

## Acceptance criteria

- [x] Requisitos de resposta incluem assuntos a abordar, fatos permitidos, afirmações proibidas e perguntas já respondidas.
- [x] A skill de atendimento orienta tom, objetividade, objeções simples e limites de pergunta na composição.
- [x] Resposta cobre todos os assuntos do turno ou identifica as lacunas específicas.
- [x] Redator não altera preço, prazo, condição operacional nem resultado de operação.
- [x] Saída inválida ou afirmação não sustentada impede aquele candidato de chegar à entrega.
- [x] Erro do modelo tem resultado operacional explícito sem fallback público inventado; modo local permanece identificado.

## TDD

**Seam exercitada:** S1.

**Primeiro red:** Perguntar preço e garantia no mesmo turno com preço conhecido e garantia ausente; responder o preço e explicitar somente a lacuna de garantia.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Aplicar a ideia de requisitos de resposta do projeto antigo. Não acrescentar supervisor neste ticket.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
