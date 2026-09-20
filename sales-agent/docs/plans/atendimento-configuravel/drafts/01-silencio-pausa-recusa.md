# 01 — Respeitar pausa humana e recusa também nas respostas pendentes

**What to build:** O comprador que pede uma pessoa ou recusa contato deixa de receber respostas automáticas incompatíveis, inclusive as que já estavam pendentes.

**Blocked by:** Nenhum — pode iniciar após aprovação do planejamento.

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_conversation_contract.py, incluindo pausa, recusa, follow-up e retomada explícita. A fila humana sem capacidade permanece declarada como indisponível. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US10, US11, US39 da especificação (numeração da lista).

## Acceptance criteria

- [x] Pedido de humano cancela respostas comerciais pendentes da conversa e follow-ups, preservando auditoria.
- [x] Eventos posteriores durante a pausa produzem silêncio público e estado consultável; não geram avisos repetitivos.
- [x] Recusa cancela mensagens comerciais pendentes sem afetar outro negócio ou conversa.
- [x] Uma confirmação inicial de encaminhamento só pode refletir uma solicitação efetivamente registrada; fila indisponível é declarada sem promessa falsa.
- [x] Retomada usa regra explícita e não ocorre por agradecimento, saudação ou replay; checkout não é reexecutado.

## TDD

**Seam exercitada:** S1 e S2.

**Primeiro red:** Preparar uma resposta comercial, pedir humano e processar a fila; a resposta anterior não pode ser oferecida para entrega.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Corrige o primeiro trecho do problema de entrega. A corrida depois do claim pertence ao T02. Não acrescentar canal real.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
