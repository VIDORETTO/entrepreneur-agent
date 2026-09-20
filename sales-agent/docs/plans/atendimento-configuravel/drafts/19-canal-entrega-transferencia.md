# 19 — Entregar respostas e confirmar transferência no adaptador Chatwoot

**What to build:** Uma conversa recebida pelo canal percorre o motor e chega a envio ou transferência observáveis, respeitando intervenção humana.

**Blocked by:** T14 — Invalidar respostas pendentes quando a evidência deixa de valer; T18 — Receber eventos Chatwoot autenticados de forma durável; T11 — Agrupar mensagens consecutivas e preservar todas as perguntas

**Status:** concluído por contrato local.

**Evidência registrada:** Testes públicos: tests/test_channel_pilot_supervisor.py, tests/test_delivery_and_governance.py e tests/test_turns_and_profiles.py. O contrato separa mensagem pública, nota/transferência e resultado desconhecido; pedido de transferência só vira `confirmed` após o identificador externo ser confirmado. Chatwoot real não foi executado.


**User Stories:** US10, US39, US40, US43, US48 da especificação (numeração da lista).

## Acceptance criteria

- [x] Entrada durável alimenta turnos e a interface de entrega revalidada.
- [x] Snapshot do canal e estado local são revalidados antes do envio, com limitações residuais do contrato documentadas.
- [x] Nota privada, resposta pública e transferência são ações distintas com escopos e evidências separados.
- [x] Transferência solicitada não é apresentada como confirmada antes da confirmação do canal.
- [x] Resultado desconhecido é conciliado pelos identificadores disponíveis, sem reenvio cego.
- [x] Timeout, takeover, duplicação e retomada são demonstrados via contrato; sem credenciais reais o relatório não afirma integração real.

## TDD

**Seam exercitada:** S3 e S2.

**Primeiro red:** Receber mensagem, preparar resposta e simular atribuição humana antes do envio; o Chatwoot falso não recebe resposta pública.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Portar comportamentos do projeto antigo seletivamente. Não modificar o core do Chatwoot nem importar seu banco.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
