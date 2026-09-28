---
schema: hybrid/ticket
schema_version: 1.0
id: TK-007
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 11
requires: ["TK-004"]
requirement_refs: ["FR-007"]
acceptance_refs: ["AC-016", "AC-017", "AC-018"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/channel.py", "src/sales_agent/conversation.py", "src/sales_agent/transcription.py", "schemas/business-package.schema.json", "tests/test_non_text_messages.py"]
verification_status: passed
last_update: EV-058 revalidou após TK-008; revisão anterior aplicável
---











# TK-007 — Tratar áudio, imagem e documento sem descartar nem inventar

## Objetivo e limites

Comprador que manda áudio/imagem recebe resposta coerente; transcrição opcional é marcada; comprovante segue pendente. Refs: FR-007; AC-016, AC-017, AC-018.

Não inclui: OCR de imagem; transcritor real (só interface + adaptador HTTP opcional sem execução real).

## Leitura em ordem

1. `src/sales_agent/channel.py` → `ChatwootReceiver._message`, `admit` — payload de `attachments` (file_type audio/image/file).
2. `src/sales_agent/conversation.py` → ramo `payment_proof` em `_decide` — comportamento de comprovante a preservar.
3. `schemas/business-package.schema.json` → raiz — onde declarar `non_text_policy`.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- Evento ganha `attachments: [{type, mime, size}]` (sem baixar conteúdo por padrão).
- `non_text_policy`: `ask_text` (padrão) | `offer_human`.
- `Transcriber.transcribe(url) -> text`; texto marcado `transcribed`; efeitos de checkout exigem confirmação textual posterior.
- Liberdade local: texto padrão de `ask_text`.
- Alternativas descartadas: ignorar anexos (comprador fica sem resposta).

## Mapa de alterações

- Existente: `channel.py` → extrair anexos.
- Existente: `conversation.py` → ramo não textual antes da interpretação.
- Novo: `src/sales_agent/transcription.py` → `Transcriber` (protocolo) + `HTTPTranscriber` opcional.
- Existente: schema do pacote.
- Novo: `tests/test_non_text_messages.py`.

## Contrato técnico

- Entradas: evento com `text` vazio e `attachments`.
- Saídas: resposta de política ou turno transcrito.
- Invariantes: nenhum fato inventado a partir de mídia.
- Erros: transcrição falha → política configurada.
- Efeitos: nenhum efeito comercial só com texto transcrito.

## Exemplos de aceite

- **AC-016**: áudio, sem transcritor → resposta pede texto; `state` registra anexo audio.
- **AC-017**: transcritor roteirizado 'quero a camiseta M' → proposta processada, trace `transcribed`, checkout não preparado sem confirmação textual.
- **AC-018**: imagem + 'segue o comprovante' → `payment_proof` pendente; resposta não diz 'confirmado'.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-004 (status `done`).

- [x] TK-007.1 Escrever o primeiro caso (AC-016) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [x] TK-007.2 Implementar o mínimo para green de AC-016; próximo caso só após green.
- [x] TK-007.3 Implementar o mínimo para green de AC-017; próximo caso só após green.
- [x] TK-007.4 Implementar o mínimo para green de AC-018; próximo caso só após green.
- [x] TK-007.5 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [x] TK-007.6 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_non_text_messages.py tests/test_conversation_contract.py`
- Estado esperado: verde.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: —

## Condição de retorno à planejadora

Retornar se o dono quiser que transcrição autorize checkout sem confirmação (mudança de política). Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-016, AC-017, AC-018), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
