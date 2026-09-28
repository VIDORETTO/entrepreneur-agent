---
schema: hybrid/plan
schema_version: "1.0"
effort_id: 001-piloto-real-confiavel
revision: 2
spec_revision: 2
status: ready
---

# Plan: Do alpha local ao primeiro piloto real confiável

## Summary

Evoluir o runtime existente (Python, SQLite, CLI — ADR 0001) sem trocar
infraestrutura: introduzir um relógio injetável, corrigir o contrato Chatwoot,
acrescentar um módulo de serviço fino sobre `ChatwootChannelService`, um
adaptador de modelo com saída estruturada, um redator opcional com verificador
determinístico, BM25 via FTS5, avaliação reservada com repetição, garantias de
acesso humano, privacidade e um portão de prontidão sobre o `PilotController`
existente. Toda autoridade continua no motor (`SellerEngine`) e na entrega
(`DeliveryProcessor`).

## Technical context

- Language/runtime: Python (hoje 3.9.25 local; 3.12 disponível em `/usr/bin/python3.12`); alvo ≥ 3.11 após TK-002.
- Dependencies: nenhuma em runtime (`dependencies = []`); dev: pytest, ruff, build, twine. Dev extra proposto: `time-machine` para AC-002.
- Storage/data: SQLite com migração versionada em `src/sales_agent/storage.py` (`StateStore`).
- Test command: `cd sales-agent && python -m pytest -q` — executado em 28/09/2026: 171 passed, 1 failed (A01).
- Lint: `ruff check src tests` (configurado em `pyproject.toml`; não executado nesta análise).
- Target/platform: Linux, processo único; Chatwoot self-hosted como canal.

## Consumed contract

- Spec: `spec.md`, revision 2 (aceita; Q1 OpenAI, Q2 180 dias, Q3 timestamped).
- Requirements and acceptance refs: FR-001–FR-015; AC-001–AC-048.

## Modules, interfaces, consumers, and seams

| Module | Interface | Consumidores | Seam de teste |
|---|---|---|---|
| Relógio (existente: `storage.utc_now`) | `Clock.now() -> str` injetável em `StateStore`, `SellerEngine`, `TurnAssembler`, `DeliveryProcessor`, `ChatwootReceiver`, `PilotController` | todo módulo temporal | fixture `clock` em `tests/conftest.py` |
| Receptor Chatwoot (existente: `channel.ChatwootReceiver`) | `admit(body, headers, now)` + `wsgi` | serviço, CLI `channel chatwoot-admit` | **S3**: WSGI/HTTP com fixture assinada |
| Ledger de saída (novo em `StateStore`) | `record_outbound(conversation, provider_message_id, content_hash, sent_at)` / `match_outbound(...)` | `ChatwootDeliveryProvider.send`, `ChatwootReceiver._event_kind` | S3 via servidor falso que ecoa |
| Serviço (novo `service.py`) | `ChannelServer(config).serve()`; rotas `/webhooks/chatwoot`, `/healthz`, `/readyz` | CLI `vendedor serve` | **S3**: processo real + servidor Chatwoot falso em `http.server` |
| Janela de canal (novo em `delivery.py`) | `DeliveryProcessor.revalidate` ganha verificação `window_closed` | worker, follow-up | S2/S3 com relógio injetado |
| Adaptador de modelo (existente: `model.HTTPModelAdapter`) | `ModelAdapter.propose` (inalterado) + perfis `openai`/`openai-compatible` + `usage` no `Proposal.raw` | `SellerEngine` | servidor HTTP falso local; **S1** para efeito |
| Redator (novo `drafting.py`) | `Drafter.draft(requirements) -> str`; `ClaimVerifier.verify(draft, requirements) -> Verdict` | `SellerEngine` quando `draft_mode=on` | **S1** com redator falso roteirizado |
| Recuperação (existente: `StateStore.search_sources`) | assinatura inalterada; implementação FTS5 BM25 | `PersistentFarolKnowledge.search` | **S2** `knowledge query` + avaliação |
| Avaliação (existente: `evaluation.EvaluationRunner`) | `--split`, `--repeat`, relatório com pass^k | CLI `evaluate`, `pilot readiness` | **S2** |
| Humano (existente: `SellerEngine._decide`) | política `service_hours` e `loop_policy` no pacote | motor | **S1** |
| Privacidade (novo `privacy.py`) | `export(contact)`, `erase(contact)`, `purge(before)`; `redact(text)` | CLI `vendedor privacy`, relatórios | **S2** |
| Prontidão (existente: `governance.PilotController`) | `readiness(business, channel) -> {ready, missing[], evidence[]}` | CLI `pilot readiness`, `pilot configure` | **S2** |

Seams herdadas do esforço anterior: **S1** `SellerEngine.handle`, **S2** CLI
`vendedor`, **S3** HTTP de canal com servidor falso. Nenhum teste consulta
tabelas SQLite para provar comportamento.

Regra dos dois adaptadores: `Drafter` tem produção (modelo) e teste
(roteirizado); `Transcriber` idem; `Clock` tem sistema e fixo. Não criar
interface para módulos com um único adaptador.

## Chosen approach and alternatives

1. **Relógio**: objeto `Clock` com `now()` passado por construtor, padrão `SystemClock`; `utc_now()` permanece como fachada para compatibilidade. Alternativa rejeitada: só consertar o teste vencido — não resolve os outros 50 pontos nem AC-002.
2. **Assinatura**: calcular HMAC sobre `f"{ts}.".encode() + raw`; modo legado por binding (`signature_mode: "timestamped" | "legacy-body"`). Alternativa rejeitada: aceitar ambos silenciosamente — reabre replay.
3. **Eco**: ledger de saída gravado na mesma transação que o ACK do outbox + registro "envio em curso" antes do POST (content hash). Alternativa rejeitada: exigir token de AgentBot — válido como recomendação operacional, mas não elimina o risco em instalações existentes.
4. **Serviço**: `wsgiref.simple_server` + threads de worker com parada cooperativa; sem framework (mantém zero dependências). Alternativa: FastAPI/uvicorn — rejeitada agora por dependência e porque o volume de um negócio não exige.
5. **Modelo**: manter `urllib`; papéis `system`/`user`; perfil `openai` usa Chat Completions com `response_format: {type: json_schema, json_schema: {strict: true}}` e trata `refusal`; perfil `openai-compatible` usa o mesmo corpo sem depender de `strict` (validação + um reparo). Endpoint padrão `https://api.openai.com/v1/chat/completions`; nome do modelo e preços por configuração. Alternativa: SDK oficial `openai` — rejeitada para manter zero dependências; a Responses API fica como evolução se a Chat Completions deixar de atender. Consultar a documentação atual da OpenAI (Structured Outputs) antes de implementar.
6. **Redação**: modelo recebe `ResponseRequirements` (tópicos, evidências permitidas, cotação, pergunta necessária, proibições) e devolve texto; `ClaimVerifier` extrai R$, %, prazos, números e URLs por regex e exige presença nos fatos permitidos; reaproveita `QualitySupervisor._commercial_claims`. Alternativa: juiz por modelo — rejeitado como autoridade (plano §9.2).
7. **BM25**: tabela virtual FTS5 `tokenize="unicode61 remove_diacritics 2"` espelhando `sources`; filtros de governança aplicados no SQL antes do ranking. Alternativa: vetores — roadmap.
8. **Avaliação**: dividir `evaluation/golden_set.json` em `dev.json` e `holdout.json`; SHA-256 do holdout no relatório; `--repeat k`. Casos novos declarativos (entrada, estado, esperado, proibido) executados por um runner genérico, preservando os 38 casos AC existentes.
9. **Prontidão**: `PilotController.readiness` agrega evidências já produzidas (relatório, model-check, doctor do canal, config) e `configure(mode="pilot")` passa a chamá-lo.

## Data, compatibility, and external dependencies

- Migrações aditivas: `outbound_ledger`, `sources_fts` (+ gatilhos de sincronização), `privacy_audit`, colunas `attachments` em turnos, `channel_kind`/`signature_mode`/`timestamp_tolerance` nos bindings. Leitores antigos continuam funcionando.
- Pacote: campos opcionais `service_hours`, `loop_policy`, `draft_mode`, `non_text_policy`, `privacy.retention_days`; `schemas/business-package.schema.json` atualizado; ausência = padrão seguro.
- Segredos por referência `env:NOME` em config de serviço; nunca no SQLite de pacote.
- Idempotência: envio usa a `idempotency_key` existente; ledger de saída é chave única `(conversation, provider_message_id)`.
- Concorrência: worker e receptor no mesmo processo usam o SQLite com WAL já configurado; testes multiprocesso existentes (`tests/test_multiprocess.py`) servem de regressão.
- Externos: Chatwoot (contrato de webhook com timestamp — docs oficiais; `chatwoot-ai` como segunda referência), provedores de modelo (API compatível OpenAI; Anthropic Messages com tool use). Execução real só com credenciais do dono; relatórios distinguem `contract-local` de `real`.

## Verification strategy

Detalhe dos ciclos, fixtures e oráculos em [tdd.md](tdd.md). Mapa AC → teste:

| AC | Seam | Teste (arquivo → caso) | Oráculo independente |
|---|---|---|---|
| AC-001 | S2 | `tests/test_knowledge_and_configuration.py` → teste Farol existente com `clock` fixo | datas literais da fixture |
| AC-002 | CI | job `pytest` sob `time-machine` +400 dias | mesma contagem de testes |
| AC-003 | CI | `pip install` em 3.10 falha; matriz 3.11/estável | metadado `requires-python` |
| AC-004–006 | S3 | `tests/test_chatwoot_contract.py` → assinatura/timestamp | HMAC calculado na fixture pela fórmula da doc |
| AC-007–009 | S3 | `tests/test_chatwoot_contract.py` → eco | servidor falso devolve `message_id` e ecoa |
| AC-010–012 | S3 | `tests/test_service.py` → subprocesso `vendedor serve` | requisições observadas no servidor falso |
| AC-013–015 | S2/S3 | `tests/test_channel_window.py` | relógio fixo e datas literais |
| AC-016–018 | S3/S1 | `tests/test_non_text_messages.py` | payloads Chatwoot com `attachments` |
| AC-019–023 | S1/HTTP | `tests/test_model_adapter.py` | servidores falsos por perfil; corpo da requisição inspecionado |
| AC-024–027 | S1 | `tests/test_grounded_drafting.py` | rascunhos roteirizados com valores literais |
| AC-028–030 | S1 + avaliação | `tests/test_injection.py` e casos holdout | frases literais proibidas |
| AC-031–034 | S2 | `tests/test_retrieval.py`; `evaluation/retrieval_set.json` | fonte esperada por pergunta, escrita à mão |
| AC-035–037 | S2 | `tests/test_cli_and_evaluation.py` | adaptador falso com sequência de falhas conhecida |
| AC-038–040 | S2 | `tests/test_pilot_readiness.py` | lista literal de requisitos faltantes |
| AC-041–044 | S1 | `tests/test_human_access.py` | horário literal e fatos da fixture |
| AC-045–048 | S2 | `tests/test_privacy.py` | varredura por strings literais de PII |

Comandos por ticket: `python -m pytest -q <arquivo>`; marco: `python -m pytest -q`, `ruff check src tests`, `vendedor doctor`, `vendedor evaluate --output reports/evaluation-latest.json`.

## Change map

| Path | Existing/new | Symbol or section | Purpose | Reference revision |
|---|---|---|---|---|
| `src/sales_agent/storage.py` | existing | `utc_now`, `StateStore`, `search_sources`, migrações | relógio, ledger, FTS5, privacidade | 9abaf95 |
| `src/sales_agent/channel.py` | existing | `ChatwootBinding`, `ChatwootReceiver`, `ChatwootDeliveryProvider`, `ChatwootChannelService` | assinatura, eco, anexos, janela | 9abaf95 |
| `src/sales_agent/service.py` | new | `ChannelServer`, `ServiceConfig` | processo de serviço | — |
| `src/sales_agent/delivery.py` | existing | `DeliveryProcessor.revalidate` | janela 24 h | 9abaf95 |
| `src/sales_agent/model.py` | existing | `HTTPModelAdapter` | perfis, schema, reparo, custo | 9abaf95 |
| `src/sales_agent/drafting.py` | new | `ResponseRequirements`, `Drafter`, `ClaimVerifier` | redação verificada | — |
| `src/sales_agent/conversation.py` | existing | `SellerEngine._decide`, `_result` | redação, injeção, humano, não texto | 9abaf95 |
| `src/sales_agent/evaluation.py` | existing | `EvaluationRunner`, `_golden_set` | split, repetição, pass^k | 9abaf95 |
| `src/sales_agent/governance.py` | existing | `PilotController.configure` | `readiness` | 9abaf95 |
| `src/sales_agent/privacy.py` | new | `PrivacyService`, `redact` | LGPD | — |
| `src/sales_agent/cli.py` | existing | parsers | `serve`, `privacy`, `pilot readiness`, flags | 9abaf95 |
| `schemas/business-package.schema.json` | existing | propriedades opcionais | novos campos de pacote | 9abaf95 |
| `pyproject.toml`, `../.github/workflows/sales-agent-ci.yml` | existing | `requires-python`, matriz | piso 3.11 | 9abaf95 |
| `evaluation/` | existing | `golden_set.json` → `dev.json`, `holdout.json`, `retrieval_set.json` | avaliação | 9abaf95 |

## Derived technical obligations

- **OT-001** → FR-001: nenhum `utc_now()` novo fora da fachada; `ruff` ou teste de arquitetura impede `datetime.now()` em `src/`.
- **OT-002** → FR-003/FR-004: nenhuma mensagem admitida antes da autenticação; ledger de saída gravado antes do ACK do outbox.
- **OT-003** → FR-005: ACK HTTP não espera modelo nem Chatwoot; desligamento respeita leases.
- **OT-004** → FR-008/FR-009/FR-010: texto de comprador e fontes sempre em campo de dado delimitado; nunca concatenado às instruções.
- **OT-005** → FR-011: filtros de governança aplicados antes do ranking; FTS nunca retorna linha revogada.
- **OT-006** → FR-012/FR-013: relatórios carregam hash do holdout, modelo e revisão do pacote; prontidão recusa evidência de outro modelo/pacote.
- **OT-007** → FR-015: toda saída de relatório/log passa por `redact`.
- **OT-008** → todos: documentação (`README.md`, `docs/OPERATIONS.md`, `docs/CONFIGURATION.md`) atualizada no ticket que muda a interface.

## Risks and gates

- R1 — Divergência entre segredo exposto e chave de assinatura (chatwoot#13809). Decisão Q3: `timestamped` padrão; `legacy-body` só opt-in e bloqueia prontidão. Gate: AC-005/AC-039.
- R2 — Modelos variam no suporte a schema estrito. Mitigação: reparo único + fallback; `model-check` por perfil. Gate: AC-023.
- R3 — Verificador por regex pode rejeitar rascunhos corretos (falso positivo) e degradar para template. Aceitável: segurança > naturalidade; medir taxa de fallback no relatório.
- R4 — FTS5 ausente em builds exóticos. Mitigação: fallback atual, sinalizado no `doctor`.
- R5 — `hybrid.py graph` aponta sobreposição de `owned_areas` (`storage.py`, `channel.py`, `conversation.py`, `cli.py`, `evaluation/`, `docs/OPERATIONS.md`). Decisão: **uma executora, em série**, na ordem TK-001 → TK-002 → TK-003 → TK-004 → TK-005 → TK-006 → TK-007 → TK-008 → TK-012 → TK-009 → TK-010 → TK-011 → TK-013 → TK-014 → TK-015. Paralelismo só entre TK-008/TK-011/TK-013/TK-014 e em worktrees separadas, com rebase antes do merge.
- Marcos: **A** base confiável (TK-001–TK-004); **B** serviço executável (TK-005–TK-007); **C** conversa real verificada (TK-008–TK-010, TK-012); **D** recuperação (TK-011); **E** humano e privacidade (TK-013–TK-014); **F** portão do piloto (TK-015).
- G2: aprovado em 28/09/2026 (spec rev. 2 aceita, Q1–Q3 respondidas).
- G3: por ticket, `hybrid.py package` com `ready: true`.
