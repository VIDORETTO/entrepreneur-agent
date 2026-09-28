---
schema: hybrid/ticket
schema_version: 1.0
id: TK-009
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 10
requires: ["TK-008"]
requirement_refs: ["FR-009"]
acceptance_refs: ["AC-024", "AC-025", "AC-026", "AC-027"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/drafting.py", "src/sales_agent/conversation.py", "schemas/business-package.schema.json", "tests/test_grounded_drafting.py"]
verification_status: passed
last_update: Evidence invalidated after an input changed.
---










# TK-009 — Redação natural opcional com verificador determinístico de alegações

## Objetivo e limites

Com `draft_mode=on`, o comprador recebe texto natural; qualquer valor, prazo, desconto ou link não sustentado derruba para o template seguro. Refs: FR-009; AC-024, AC-025, AC-026, AC-027.

Não inclui: supervisor (T21/T22 continuam); tom/estilo avançado; injeção (TK-010).

## Leitura em ordem

1. `src/sales_agent/conversation.py` → `_decide`, `_result`, `_evidence_answer`, `_topic_label`, `_evidence_covers_topic` — onde nasce o template e os tópicos.
2. `src/sales_agent/governance.py` → `QualitySupervisor._commercial_claims`, `_policy_claims`, `_unsupported_new_claims` — extratores reaproveitáveis.
3. `src/sales_agent/types.py` → `EngineResult` — campos do resultado.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- `ResponseRequirements`: tópicos a cobrir, evidências permitidas, cotação, link de checkout, pergunta necessária, proibições, template.
- `ClaimVerifier`: extrai R$, %, prazos (dias/meses/horas), quantidades, URLs; cada item precisa existir em cotação/evidência/pacote; exige pergunta necessária e cobertura de tópicos.
- Uma regeneração com a lista de violações; depois template. Extratores movidos para `drafting.py` e reutilizados pelo supervisor.
- Liberdade local: heurística de cobertura de tópico (reaproveitar `_evidence_covers_topic`).
- Alternativas descartadas: juiz por modelo como autoridade.

## Mapa de alterações

- Novo: `src/sales_agent/drafting.py`.
- Existente: `conversation.py` → chamar redator quando `draft_mode=on`; trace `draft_accepted`/`claim_unsupported`/`draft_fallback`.
- Existente: `governance.py` → importar extratores de `drafting.py`.
- Existente: schema do pacote → `draft_mode`.
- Novo: `tests/test_grounded_drafting.py`.

## Contrato técnico

- Entradas: requisitos + rascunho.
- Saídas: texto enviado e veredito no trace.
- Invariantes: template continua o caminho quando `draft_mode=off` (padrão).
- Erros: redator indisponível → template.
- Efeitos: até 2 chamadas ao redator.

## Exemplos de aceite

- **AC-024**: cotação 79,90; rascunho 'Fica R$ 79,90 com frete para SP.' → enviado.
- **AC-025**: 'Hoje tem 10% de desconto' ×2 → template, `claim_unsupported`.
- **AC-026**: rascunho sem a pergunta de tamanho exigida → rejeitado.
- **AC-027**: link `https://pague-aqui.example` → rejeitado.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-008 (status `done`).

- [ ] TK-009.1 Escrever o primeiro caso (AC-024) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [ ] TK-009.2 Implementar o mínimo para green de AC-024; próximo caso só após green.
- [ ] TK-009.3 Implementar o mínimo para green de AC-025; próximo caso só após green.
- [ ] TK-009.4 Implementar o mínimo para green de AC-026; próximo caso só após green.
- [ ] TK-009.5 Implementar o mínimo para green de AC-027; próximo caso só após green.
- [ ] TK-009.6 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [ ] TK-009.7 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_grounded_drafting.py tests/test_channel_pilot_supervisor.py`
- Estado esperado: verde; supervisor sem regressão.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: —

## Condição de retorno à planejadora

Retornar se o verificador precisar interpretar semântica que regex não cobre para um AC (decisão de abordagem). Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-024, AC-025, AC-026, AC-027), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
