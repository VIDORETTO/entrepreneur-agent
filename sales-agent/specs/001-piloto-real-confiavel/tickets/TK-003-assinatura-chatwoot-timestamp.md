---
schema: hybrid/ticket
schema_version: 1.0
id: TK-003
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 5
requires: ["TK-001"]
requirement_refs: ["FR-003"]
acceptance_refs: ["AC-004", "AC-005", "AC-006"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/channel.py", "tests/test_chatwoot_contract.py", "docs/OPERATIONS.md"]
verification_status: passed
last_update: Revisão em findings/TK-003-review.md sem achados bloqueantes para AC-004–006
---





# TK-003 — Assinatura Chatwoot com timestamp e janela anti-replay

## Objetivo e limites

Webhooks reais assinados pelo contrato publicado são admitidos; assinaturas antigas ou corpo-apenas são recusados salvo modo legado explícito. Refs: FR-003; AC-004, AC-005, AC-006.

Não inclui: correlação de eco (TK-004), serviço HTTP (TK-005), rotação de segredo.

## Leitura em ordem

1. `src/sales_agent/channel.py` → `ChatwootBinding`, `ChatwootReceiver._signature_matches`, `_authenticate`, `admit`, `wsgi` — implementação atual (HMAC só do corpo).
2. `tests/test_channel_pilot_supervisor.py` → testes HMAC existentes — regressões a manter ou migrar.
3. `specs/001-piloto-real-confiavel/research.md` → A02 — fonte do contrato (docs Chatwoot, chatwoot-ai).

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- Mensagem assinada: `f"{timestamp}.".encode() + raw_body`; header `X-Chatwoot-Timestamp` (segundos Unix); `X-Chatwoot-Signature: sha256=<hex>`.
- `ChatwootBinding.signature_mode`: `timestamped` (padrão) | `legacy-body`; `timestamp_tolerance_seconds` padrão 300, faixa 60–900.
- Comparação em tempo constante; `X-Chatwoot-Delivery` gravado quando presente.
- Liberdade local: aceitar base64 além de hex apenas se a doc exigir (hoje não exige; preferir remover).
- Alternativas descartadas: aceitar ambos os formatos sem configuração (reabre replay).

## Mapa de alterações

- Existente: `channel.py` → `ChatwootBinding` (novos campos), `_signature_matches`, `_authenticate(now)`.
- Novo: `tests/test_chatwoot_contract.py`.
- Existente: testes antigos que assinam só o corpo passam a declarar `legacy-body` ou a nova fórmula.
- Existente: `docs/OPERATIONS.md` → configuração do binding.

## Contrato técnico

- Entradas: corpo bruto, headers, instante do relógio.
- Saídas: evento admitido ou `ChannelAuthenticationError` (HTTP 401).
- Invariantes: nada persistido antes da autenticação.
- Erros: assinatura ausente/inválida, timestamp ausente, fora da tolerância.
- Efeitos: nenhum em rejeição.
- Compatibilidade: bindings existentes sem `signature_mode` → `timestamped`; doc explica migração.

## Exemplos de aceite

- **AC-004**: ts=1790000000, relógio=1790000010, assinatura pela fórmula → admitido; reenvio idêntico → 1 evento efetivo.
- **AC-005**: HMAC só do corpo → 401 com `timestamped`; aceito com `legacy-body` e `doctor` mostra `legacy_signature`.
- **AC-006**: ts = relógio − 301 → 401, `turn`/`channel` sem evento.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-001 (status `done`).

- [x] TK-003.1 Escrever o primeiro caso (AC-004) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [x] TK-003.2 Implementar o mínimo para green de AC-004; próximo caso só após green.
- [x] TK-003.3 Implementar o mínimo para green de AC-005; próximo caso só após green.
- [x] TK-003.4 Implementar o mínimo para green de AC-006; próximo caso só após green.
- [x] TK-003.5 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [x] TK-003.6 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Estado esperado: novos casos verdes; regressões de canal verdes.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: Porta ocupada no WSGI de teste é ambiente.

## Condição de retorno à planejadora

Q3 decidida: `timestamped` padrão, `legacy-body` só opt-in. Não acessar nem alterar o Chatwoot de produção da VPS. Retornar se a fórmula documentada divergir da usada em `/root/saas/chatwoot-ai/backend/app/api/routes/webhook.py`. Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-004, AC-005, AC-006), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
