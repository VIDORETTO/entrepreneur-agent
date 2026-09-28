---
schema: hybrid/ticket
schema_version: 1.0
id: TK-002
effort: 001-piloto-real-confiavel
type: delivery
status: implemented
ticket_revision: 5
requires: ["TK-001"]
requirement_refs: ["FR-002"]
acceptance_refs: ["AC-003"]
spec_revision: 2
plan_revision: 2
owned_areas: ["pyproject.toml", "../.github/workflows/sales-agent-ci.yml", "docs/INSTALLATION.md", "README.md"]
verification_status: stale
last_update: Evidence invalidated after an input changed.
---





# TK-002 — Piso Python 3.11 e matriz de CI atualizada

## Objetivo e limites

O pacote declara Python ≥ 3.11 e o CI prova 3.11 e a versão estável mais recente. Refs: FR-002; AC-003.

Não inclui: usar recursos novos da linguagem em massa; integrar Farol upstream (roadmap).

## Leitura em ordem

1. `pyproject.toml` → `requires-python`, `[tool.ruff] target-version`, classifiers — metadados atuais (>=3.9, py39).
2. `../.github/workflows/sales-agent-ci.yml` → `matrix.python-version` — matriz 3.9/3.12.
3. `docs/INSTALLATION.md` → requisitos — texto a atualizar.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- 3.9 está fora de suporte desde out/2025; Farol upstream exige 3.11.
- Matriz: 3.11 e a estável mais recente disponível no runner (ex.: 3.13/3.14).
- `ruff target-version = py311`; corrigir só o que o lint exigir.
- Liberdade local: adotar `datetime.UTC` ou manter `timezone.utc`.
- Alternativas descartadas: manter 3.9 por compatibilidade com o ambiente local (3.12 já disponível).

## Mapa de alterações

- Existente: `pyproject.toml` → `requires-python = ">=3.11"`, classifiers, ruff target.
- Existente: workflow CI → matriz e passo que confirma recusa em 3.10.
- Existente: `README.md`, `docs/INSTALLATION.md`, `AGENTS.md` (comandos com `python3.12`).

## Contrato técnico

- Entradas: nenhuma.
- Saídas: metadado de pacote.
- Invariantes: zero dependências de runtime.
- Erros: pip recusa instalação < 3.11.
- Efeitos: nenhum.
- Compatibilidade: SQLite de usuários existentes intocado.

## Exemplos de aceite

- **AC-003**: `python3.10 -m pip install .` → erro `requires a different Python`; matriz 3.11 e estável → `pytest` verde.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-001 (status `done`).

- [ ] TK-002.1 Escrever o primeiro caso (AC-003) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md` (red observado manualmente no instalador; caso de CI ainda não executado).
- [x] TK-002.2 Implementar o mínimo para green de AC-003; próximo caso só após green.
- [x] TK-002.3 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [ ] TK-002.4 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python3.12 -m pip install -e '.[dev]' && python3.12 -m pytest -q && python3.12 -m build && twine check dist/*`
- Estado esperado: suíte verde em 3.12; CI verde em 3.11 e estável.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: Ausência local de 3.11 não impede: CI é a prova; registrar `not_run` local para 3.11.

## Condição de retorno à planejadora

Retornar se alguma dependência dev não suportar a versão estável. Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-003), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
