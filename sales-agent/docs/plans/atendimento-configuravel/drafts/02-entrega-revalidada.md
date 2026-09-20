# 02 — Revalidar cada entrega e impedir conclusão por worker obsoleto

**What to build:** O operador processa um ciclo de entrega que verifica o estado vigente antes do envio e distingue confirmação, cancelamento e resultado desconhecido.

**Blocked by:** T01 — Respeitar pausa humana e recusa também nas respostas pendentes

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_delivery_and_governance.py e tests/test_storage_reliability.py. A prova usa RecordingProvider e simuladores, mantém documentada a janela residual entre revalidação e provedor e transforma lease expirado em `unknown`, exigindo conciliação em vez de requeue automático. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US39, US40 da especificação (numeração da lista).

## Acceptance criteria

- [x] A interface pública de um ciclo de entrega revalida responsável, recusa, versão aplicável e autorização imediatamente antes do envio.
- [x] ACK/NACK exige a posse vigente; worker cujo lease expirou não conclui a tentativa reivindicada por outro.
- [x] Falha anterior ao envio permite retry limitado; resultado de envio desconhecido exige conciliação, sem reenvio automático.
- [x] Cancelamento e conciliação ficam consultáveis pela operação pública e sobrevivem a reinício.
- [x] Atualização do armazenamento preserva mensagens existentes e documenta compatibilidade dos comandos de outbox.
- [x] A demonstração usa provedor falso e declara que a janela entre verificação e efeito externo depende do contrato do canal.

## TDD

**Seam exercitada:** S2.

**Primeiro red:** Obter uma tentativa, pausar a conversa antes do envio e executar o ciclo; o provedor falso não recebe a mensagem.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Introduzir uma única interface pública de entrega, exercitada via CLI. Não exigir antecipadamente o adaptador Chatwoot.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
