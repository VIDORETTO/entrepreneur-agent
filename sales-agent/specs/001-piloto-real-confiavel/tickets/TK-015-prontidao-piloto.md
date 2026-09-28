---
schema: hybrid/ticket
schema_version: 1.0
id: TK-015
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 5
requires: ["TK-003", "TK-004", "TK-005", "TK-012", "TK-013", "TK-014"]
requirement_refs: ["FR-013"]
acceptance_refs: ["AC-038", "AC-039", "AC-040"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/governance.py", "src/sales_agent/cli.py", "tests/test_pilot_readiness.py", "docs/OPERATIONS.md"]
verification_status: passed
---





# TK-015 — Portão de prontidão do piloto baseado em evidências

## Objetivo e limites

O modo piloto só é habilitado com prova atual do modelo, canal, humano e privacidade, ou override auditável do dono. Refs: FR-013; AC-038, AC-039, AC-040.

Não inclui: ativação real (autorização externa); métricas pós-entrega.

## Leitura em ordem

1. `src/sales_agent/governance.py` → `PilotController.configure`, `_evaluation_matches`, `_local_evaluation_evidence`, `inspect` — verificação de evidência existente.
2. `reports/evaluation-latest.json` → `evaluation.candidate`, `thresholds_met` — formato do relatório.
3. `src/sales_agent/cli.py` → `pilot` subcomandos — padrão CLI.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- Requisitos: holdout aprovado do modelo/pacote selecionados com hash atual (não `rules-v1`), `model-check` do perfil, contrato de canal (assinatura timestamped ou legado declarado + teste de eco), `service_hours`, `privacy` configurados, interrupção exercitada.
- `configure(mode='pilot')` chama `readiness`; override exige `--override --reason`, fica no relatório e em `inspect`.
- Liberdade local: formato da lista `missing`.
- Alternativas descartadas: liberar com evidência de `rules-v1` como proxy do modelo real.

## Mapa de alterações

- Existente: `governance.py` → `readiness`.
- Existente: `cli.py` → `pilot readiness`, `--override --reason`.
- Novo: `tests/test_pilot_readiness.py`; docs.

## Contrato técnico

- Entradas: negócio, canal.
- Saídas: `{ready, missing[], evidence[]}`.
- Invariantes: evidência de outro modelo/pacote/hash não conta.
- Erros: `configure pilot` não pronto → código 2.
- Efeitos: registro de override.

## Exemplos de aceite

- **AC-038**: só relatório `rules-v1` → `ready:false`, `missing` inclui `holdout_selected_model`.
- **AC-039**: todas evidências de fixture → `ready:true` com refs.
- **AC-040**: `pilot configure --mode pilot` sem prontidão → código 2; com `--override --reason 'teste interno'` → aceito e visível em `inspect`.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-003, TK-004, TK-005, TK-012, TK-013, TK-014 (status `done`).

- [ ] TK-015.1 Escrever o primeiro caso (AC-038) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [ ] TK-015.2 Implementar o mínimo para green de AC-038; próximo caso só após green.
- [ ] TK-015.3 Implementar o mínimo para green de AC-039; próximo caso só após green.
- [ ] TK-015.4 Implementar o mínimo para green de AC-040; próximo caso só após green.
- [ ] TK-015.5 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [ ] TK-015.6 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_pilot_readiness.py tests/test_channel_pilot_supervisor.py`
- Estado esperado: verde.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: —

## Condição de retorno à planejadora

Retornar se o dono definir critérios de piloto diferentes (SC-005/SC-006). Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-038, AC-039, AC-040), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
