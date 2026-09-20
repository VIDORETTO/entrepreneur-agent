# 16 — Consultar a versão estável do Farol pelo atendimento

**What to build:** O comprador recebe resposta baseada no backend Farol efetivamente executado, com geração e evidência auditáveis.

**Blocked by:** T15 — Importar geração Farol com validação e governança preservadas; T05 — Responder apenas ao que a evidência recuperada sustenta

**Status:** bloqueado externamente.

**Evidência registrada:** Nenhum critério foi marcado. StableFarolAdapter e vendedor farol status registram blocked porque a versão estável e o cliente executável não estão disponíveis. Critérios sem marcação permanecem não demonstrados nesta execução.


**Bloqueio externo:** Publicação da versão estável do Farol anunciada pelo dono e disponibilidade de seu contrato executável.

**User Stories:** US36, US38, US48 da especificação (numeração da lista).

## Acceptance criteria

- [ ] Revisão/tag e contrato suportados são fixados; transporte é escolhido após examinar a versão estável.
- [ ] Consulta usa o KnowledgeBackend existente e mantém negócio, público, escopo e governança.
- [ ] Timeout, indisponibilidade, incompatibilidade e geração obsoleta têm resultados distintos e não inventam evidência.
- [ ] Ambiente Python compatível é isolado quando necessário, preservando instalação local base.
- [ ] Relatório separa teste com transporte falso de execução real do Farol.
- [ ] Conjunto sintético inclui pertinência, versões, revogação e ausência de resposta; geração não autorizada nunca é fallback.

## TDD

**Seam exercitada:** S1 e S2.

**Primeiro red:** Consultar uma condição pelo adaptador real em fixture pública da versão fixada e exigir o trecho esperado com a revisão correta.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Não marcar concluído com base apenas em mocks ou na prova antiga de importação. Enquanto bloqueado, os demais tickets locais seguem a fronteira.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
