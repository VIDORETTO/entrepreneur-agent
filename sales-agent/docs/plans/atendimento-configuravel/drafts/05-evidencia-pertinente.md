# 05 — Responder apenas ao que a evidência recuperada sustenta

**What to build:** O comprador recebe a condição perguntada ou uma lacuna explícita, em vez do primeiro documento vagamente relacionado.

**Blocked by:** T04 — Consultar somente revisões vigentes e explicitar conflito material

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_delivery_and_governance.py e tests/test_turns_and_profiles.py. A resposta distingue ausência, cobertura parcial e conflito, registra evidência e deixa confirmação operacional separada. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US01, US02, US36, US37 da especificação (numeração da lista).

## Acceptance criteria

- [x] A pergunta de garantia sem evidência correspondente não devolve preço/tamanhos como resposta suficiente.
- [x] Com uma política de garantia aprovada, a resposta informa a condição e registra o trecho e sua origem.
- [x] Cobertura parcial e conflito são distinguíveis de ausência total de resultados.
- [x] Cada afirmação factual usada tem suporte autorizado e relevante no mesmo escopo.
- [x] Não prometer transferência quando o resultado é apenas uma pendência local.
- [x] Documentação de pagamento ou estoque não substitui confirmação operacional.

## TDD

**Seam exercitada:** S1.

**Primeiro red:** Perguntar garantia com apenas um catálogo de preço e entrega disponível; a resposta declara ausência de garantia documentada.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Começar pelo backend local e por casos definidos; não depender de embeddings nem de modelo remoto para corrigir a falha.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
