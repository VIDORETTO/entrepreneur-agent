---
schema: hybrid/ticket
schema_version: 1.0
id: TK-012
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 8
requires: ["TK-008"]
requirement_refs: ["FR-012"]
acceptance_refs: ["AC-035", "AC-036", "AC-037"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/evaluation.py", "evaluation/", "src/sales_agent/cli.py", "tests/test_cli_and_evaluation.py", "docs/EVALUATION.md"]
verification_status: passed
last_update: Evidence invalidated after an input changed.
---








# TK-012 — Avaliação com 80 casos, holdout protegido e pass^k

## Objetivo e limites

O dono compara modelos com casos reservados, repetidos, com custo/latência, sem se enganar com média. Refs: FR-012; AC-035, AC-036, AC-037.

Não inclui: simulador de comprador por LLM (roadmap); tuning de prompt.

## Leitura em ordem

1. `src/sales_agent/evaluation.py` → `EvaluationRunner.run`, `_golden_set`, `_golden_verification`, `_case_ac0xx` — estrutura atual (38 casos codificados).
2. `evaluation/golden_set.json` → `version`, `cases` — formato atual.
3. `plano-ia-de-vendas.md` → §17.1–§17.2 — distribuição e critérios.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- Casos novos declarativos (mensagens, estado inicial, esperado, proibido, operações permitidas, crítico?) executados por runner genérico; 38 AC atuais preservados no dev.
- `dev.json` ≥ 50 e `holdout.json` ≥ 30, distribuição §17.1; hash SHA-256 do holdout no relatório.
- `--repeat k`: pass@1 = média; pass^k = todas as k passaram; crítico falho em qualquer repetição ⇒ `thresholds_met=false`.
- Limiares em `evaluation/thresholds.json`.
- Liberdade local: formato exato do JSON de caso.
- Alternativas descartadas: gerar casos automaticamente pelo próprio modelo avaliado.

## Mapa de alterações

- Existente: `evaluation.py` → split, repeat, pass^k, hash, custo/latência por caso.
- Novo: `evaluation/dev.json`, `evaluation/holdout.json`, `evaluation/thresholds.json`.
- Existente: `cli.py` → `evaluate --split --repeat --model-config`.
- Existente: `tests/test_cli_and_evaluation.py`; `docs/EVALUATION.md`.

## Contrato técnico

- Entradas: split, k, adaptador.
- Saídas: relatório JSON com contagens, pass@1, pass^k, hash, custo, latência p95.
- Invariantes: holdout só lido em `--split holdout`.
- Erros: split inexistente → código 2.
- Efeitos: arquivo de relatório.

## Exemplos de aceite

- **AC-035**: adaptador falso determinístico → pass@1=1,0 e pass^4=1,0 com `n/m` por caso; ≥ 80 casos contados.
- **AC-036**: holdout alterado em cópia → `holdout_changed: true`.
- **AC-037**: caso crítico falha em 1 de 4 → pass^4 0 nesse caso e `thresholds_met: false`.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-008 (status `done`).

- [ ] TK-012.1 Escrever o primeiro caso (AC-035) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [ ] TK-012.2 Implementar o mínimo para green de AC-035; próximo caso só após green.
- [ ] TK-012.3 Implementar o mínimo para green de AC-036; próximo caso só após green.
- [ ] TK-012.4 Implementar o mínimo para green de AC-037; próximo caso só após green.
- [ ] TK-012.5 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [ ] TK-012.6 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_cli_and_evaluation.py && vendedor evaluate --split dev --output reports/evaluation-latest.json`
- Estado esperado: verde; relatório com 38+ casos dev.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: —

## Condição de retorno à planejadora

Retornar se a distribuição §17.1 não couber nos quatro negócios fictícios (exigiria novo exemplo). Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-035, AC-036, AC-037), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
