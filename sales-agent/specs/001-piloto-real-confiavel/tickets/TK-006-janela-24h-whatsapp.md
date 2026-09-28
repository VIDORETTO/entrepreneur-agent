---
schema: hybrid/ticket
schema_version: 1.0
id: TK-006
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 11
requires: ["TK-004"]
requirement_refs: ["FR-006"]
acceptance_refs: ["AC-013", "AC-014", "AC-015"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/delivery.py", "src/sales_agent/channel.py", "src/sales_agent/conversation.py", "tests/test_channel_window.py"]
verification_status: passed
last_update: EV-039 revalidou após TK-007; revisão anterior permanece aplicável
---











# TK-006 — Respeitar a janela de 24 h do WhatsApp na entrega e no follow-up

## Objetivo e limites

Nenhuma mensagem livre é enviada fora da janela; o atendente é avisado por nota privada. Refs: FR-006; AC-013, AC-014, AC-015.

Não inclui: templates HSM (roadmap); outras inboxes.

## Leitura em ordem

1. `src/sales_agent/delivery.py` → `DeliveryProcessor.revalidate`, `process_claimed` — ponto de revalidação antes do envio.
2. `src/sales_agent/channel.py` → `ChatwootBinding`, `admit` (registro de `buyer_message`) — origem do instante da última mensagem.
3. `src/sales_agent/conversation.py` → `SellerEngine.revalidate_follow_up`, `_follow_up_eligible` — follow-up.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- `ChatwootBinding.channel_kind` (`whatsapp` | `other`, padrão `other`).
- Instante de referência: último `buyer_message` admitido na conversa; comparado ao relógio no momento da entrega (não do enfileiramento).
- Fora da janela: status `window_closed` (terminal, não reenvia), nota privada 'Resposta não enviada: janela de 24 h encerrada'.
- Liberdade local: texto exato da nota privada.
- Alternativas descartadas: descartar silenciosamente (atendente não saberia).

## Mapa de alterações

- Existente: `delivery.py` → verificação `window_closed`.
- Existente: `channel.py` → `channel_kind`; nota privada via transporte.
- Existente: `conversation.py` → `revalidate_follow_up` consulta janela.
- Novo: `tests/test_channel_window.py`.

## Contrato técnico

- Entradas: item de outbox, `channel_kind`, último instante do comprador, relógio.
- Saídas: `sent` | `window_closed`.
- Invariantes: limite exato 24 h (≤ 86400 s envia).
- Erros: instante ausente em inbox WhatsApp → `window_closed` (falha segura).
- Efeitos: nota privada idempotente por item.

## Exemplos de aceite

- **AC-013**: última 2026-09-27T12:00:01Z, entrega 2026-09-28T12:00:00Z → enviada.
- **AC-014**: última 2026-09-27T11:59:59Z → não enviada, `window_closed`, 1 nota privada.
- **AC-015**: follow-up agendado para 2026-09-29 → `blocked: window_closed`.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-004 (status `done`).

- [x] TK-006.1 Escrever o primeiro caso (AC-013) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [x] TK-006.2 Implementar o mínimo para green de AC-013; próximo caso só após green.
- [x] TK-006.3 Implementar o mínimo para green de AC-014; próximo caso só após green.
- [x] TK-006.4 Implementar o mínimo para green de AC-015; próximo caso só após green.
- [x] TK-006.5 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [x] TK-006.6 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Estado esperado: verde.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: —

## Condição de retorno à planejadora

Retornar se o dono exigir envio por template (decisão de produto nova). Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-013, AC-014, AC-015), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
