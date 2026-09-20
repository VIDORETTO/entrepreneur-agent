# 18 — Receber eventos Chatwoot autenticados de forma durável

**What to build:** Eventos válidos do primeiro canal entram uma vez no processamento local, com ACK rápido e isolamento por negócio.

**Blocked by:** Nenhum — pode iniciar após aprovação do planejamento.

**Status:** concluído por contrato local.

**Evidência registrada:** Testes públicos: tests/test_channel_pilot_supervisor.py e contrato ChatwootReceiver. HMAC, binding, persistência antes do ACK, replay e eventos fora do escopo usam somente IDs e fixtures sintéticos. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US39, US40, US48 da especificação (numeração da lista).

## Acceptance criteria

- [x] Contrato de autenticação do Chatwoot selecionado é verificado antes da admissão; falha não cria atendimento.
- [x] Conta, inbox, conversa e contato são mapeados a um negócio autorizado; IDs fictícios do simulador não autenticam eventos reais.
- [x] Entrada é persistida antes do ACK e não depende de modelo ou chamada ao Chatwoot.
- [x] Replay, evento fora do escopo e eventos de autoria da própria IA não causam loops.
- [x] Mensagens privadas e eventos humanos têm tratamento distinto de mensagens públicas do comprador.
- [x] Demonstração usa fixtures sintéticas e servidor de contrato; nenhum webhook de produção é registrado.

## TDD

**Seam exercitada:** S3 e S2.

**Primeiro red:** Entregar o mesmo webhook válido duas vezes, reiniciar o receptor e processar; existe somente um evento efetivo para aquela identidade.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Adaptador fino reutiliza o envelope existente. A ligação com turnos agrupados ocorre no T19.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
