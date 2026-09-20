# 14 — Invalidar respostas pendentes quando a evidência deixa de valer

**What to build:** Uma resposta preparada com uma fonte posteriormente revogada ou substituída não é enviada ao comprador.

**Blocked by:** T02 — Revalidar cada entrega e impedir conclusão por worker obsoleto; T05 — Responder apenas ao que a evidência recuperada sustenta

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_delivery_and_governance.py, tests/test_conversation_contract.py e tests/test_storage_reliability.py. Outbox, evidência, pacote, estado, capacidade e lease são revalidados antes do provedor. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US31, US33, US39 da especificação (numeração da lista).

## Acceptance criteria

- [x] Outbox preserva referências suficientes de evidência e geração para revalidação.
- [x] Revogação, expiração ou mudança material de escopo cancela o candidato antes do envio.
- [x] Reprocessamento é limitado e usa nova evidência; não reaproveita automaticamente texto antigo.
- [x] Alteração de pacote ou de estado que afeta a resposta invalida a autorização correspondente.
- [x] Decisão e motivo ficam observáveis sem armazenar trecho sensível em logs.
- [x] Com evidência ainda vigente, a entrega válida continua funcionando.

## TDD

**Seam exercitada:** S2.

**Primeiro red:** Preparar resposta documentada, revogar a fonte e processar a entrega; o provedor falso não recebe o texto antigo.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Usar fontes locais primeiro; a mesma regra será aplicada ao adaptador Farol.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
