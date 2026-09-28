---
schema: hybrid/ticket
schema_version: 1.0
id: TK-004
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 24
requires: ["TK-003"]
requirement_refs: ["FR-004"]
acceptance_refs: ["AC-007", "AC-008", "AC-009"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/channel.py", "src/sales_agent/storage.py", "tests/test_chatwoot_contract.py"]
verification_status: passed
last_update: Evidence invalidated after an input changed.
---
























# TK-004 — Reconhecer eco das próprias mensagens sem pausar a conversa

## Objetivo e limites

Mensagens enviadas pelo vendedor e ecoadas pelo webhook são `self_authored`; só mensagens de atendente pausam. Refs: FR-004; AC-007, AC-008, AC-009.

Não inclui: mudanças no Chatwoot core; exigir AgentBot token (fica como recomendação em docs).

## Leitura em ordem

1. `src/sales_agent/channel.py` → `ChatwootReceiver._event_kind`, `admit`, `ChatwootDeliveryProvider.send`, `HTTPChatwootTransport._provider_result` — classificação e retorno do provedor.
2. `src/sales_agent/storage.py` → `record_channel_event`, `ack_outbox`, migrações — onde gravar o ledger.
3. `src/sales_agent/delivery.py` → `DeliveryProcessor.process_claimed` — ordem envio → ACK.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- Ledger de saída `(business, conversation, provider_message_id, content_sha256, state, sent_at)`; estado `in_flight` gravado antes do POST, `sent` com id após resposta.
- Classificação: id no ledger → `self_authored`; sem id mas `in_flight` com mesmo hash e conversa ≤ 120 s → `self_authored` (`echo_by_content`); senão regra atual.
- Migração aditiva.
- Liberdade local: nome da tabela e do método de consulta.
- Alternativas descartadas: ignorar todo `outgoing` de `sender.type=user` (perderia pausa humana real).

## Mapa de alterações

- Existente: `storage.py` → migração + `record_outbound`, `match_outbound`.
- Existente: `channel.py` → `_event_kind` consulta ledger; `ChatwootDeliveryProvider.send` grava `in_flight`/`sent`.
- Novo: casos em `tests/test_chatwoot_contract.py` com `chatwoot_server` modo `echo`.

## Contrato técnico

- Entradas: webhook outgoing com `message.id`, `content`, `conversation.id`.
- Saídas: `self_authored` ou `human_message`.
- Invariantes: atendente com id desconhecido e texto diferente sempre pausa.
- Erros: nenhum novo.
- Efeitos: ledger atualizado na mesma transação do ACK.
- Concorrência: eco pode chegar antes do ACK (AC-009).

## Exemplos de aceite

- **AC-007**: envio → servidor falso responde id 42 → eco `sender.type=user`, id 42 → `status` continua `active`.
- **AC-008**: webhook outgoing id 99 'Oi, sou a Carla' → `human_paused`.
- **AC-009**: servidor ecoa antes de responder ao POST → eco classificado `self_authored` por conteúdo; sem pausa.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-003 (status `done`).

- [x] TK-004.1 Escrever o primeiro caso (AC-007) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [x] TK-004.2 Implementar o mínimo para green de AC-007; próximo caso só após green.
- [x] TK-004.3 Implementar o mínimo para green de AC-008; próximo caso só após green.
- [x] TK-004.4 Implementar o mínimo para green de AC-009; próximo caso só após green.
- [x] TK-004.5 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [x] TK-004.6 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Estado esperado: verde; T01 (pausa humana) preservado.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: Timeout do servidor falso em thread é ambiente.

## Condição de retorno à planejadora

Retornar se o payload real não trouxer `message.id` no eco (exigiria outra chave de correlação). Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-007, AC-008, AC-009), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
