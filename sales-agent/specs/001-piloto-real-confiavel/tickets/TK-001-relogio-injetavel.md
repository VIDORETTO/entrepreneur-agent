---
schema: hybrid/ticket
schema_version: 1.0
id: TK-001
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 12
requires: []
requirement_refs: ["FR-001"]
acceptance_refs: ["AC-001", "AC-002"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/storage.py", "tests/conftest.py", "tests/test_knowledge_and_configuration.py"]
verification_status: passed
last_update: EV-014 revalidou AC-001 após migração aditiva; revisão anterior permanece aplicável
---












# TK-001 — Relógio injetável e suíte independente da data

## Objetivo e limites

A suíte volta a ficar verde e permanece verde em qualquer data; regras temporais recebem o instante de um relógio injetável. Refs: FR-001; AC-001, AC-002.

Não inclui: migrar de uma vez todos os ~51 usos de `utc_now()` para injeção explícita (fazer só nos módulos tocados por AC-001/AC-002 e deixar a fachada); mudança de Python (TK-002).

## Leitura em ordem

1. `src/sales_agent/storage.py` → `utc_now`, `normalize_iso_datetime`, `StateStore.__init__`, `search_sources` — ponto único de tempo atual.
2. `tests/test_knowledge_and_configuration.py` → `test_farol_manifest_normalizes_offset_dates_and_replaces_previous_generation` — teste que venceu em 22/09/2026.
3. `tests/conftest.py` → fixtures existentes — padrão de fixture a seguir.
4. `specs/001-piloto-real-confiavel/tdd.md` → Fixtures novas → `clock` — contrato da fixture.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- `Clock` com `now() -> str` ISO UTC; `SystemClock` padrão; `FixedClock` para testes.
- `utc_now()` continua existindo e delega ao relógio padrão do processo (compatibilidade).
- Dev extra `time-machine` para AC-002; job CI adicional roda a suíte deslocada +400 dias.
- Liberdade local: nome do módulo do relógio (`clock.py` ou dentro de `storage.py`), forma de passar o relógio a `StateStore`.
- Alternativas descartadas: apenas trocar as datas da fixture por datas futuras (vence de novo).

## Mapa de alterações

- Existente: `src/sales_agent/storage.py` → `utc_now`, `StateStore` — aceitar relógio.
- Existente: `tests/test_knowledge_and_configuration.py` → teste Farol usa `clock` fixo em 2026-09-20T12:00:00Z.
- Novo: `tests/conftest.py` → fixture `clock`.
- Existente: `../.github/workflows/sales-agent-ci.yml` → job `shifted-clock`.
- Fora da fatia: demais módulos (continuam via fachada).

## Contrato técnico

- Entradas: `Clock` opcional nos construtores; ausência = `SystemClock`.
- Saídas: instantes ISO 8601 UTC como hoje.
- Invariantes: produção sem relógio explícito se comporta exatamente como antes.
- Erros: nenhum novo.
- Efeitos: nenhum.
- Compatibilidade: assinatura pública de `StateStore` só ganha parâmetro opcional.

## Exemplos de aceite

- **AC-001**: fixture Farol com vigência 2026-09-19..2026-09-22 + relógio fixo 2026-09-20 → consulta 'política nova' retorna 1 trecho; hoje (relógio real 28/09) retorna [] e falha.
- **AC-002**: `pytest` sob `time_machine.travel('+400d')` → mesma contagem de testes aprovados que sem deslocamento.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: nenhum.

- [x] TK-001.1 Escrever o primeiro caso (AC-001) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [x] TK-001.2 Implementar o mínimo para green de AC-001; próximo caso só após green.
- [x] TK-001.3 Implementar o mínimo para green de AC-002; próximo caso só após green.
- [x] TK-001.4 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [x] TK-001.5 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q && python -m pytest -q --clock-shift-days=400` (opção criada neste ticket em `tests/conftest.py` com `time_machine.travel`)
- Estado esperado: 172 aprovados em ambas as execuções.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: Falha de import de `time_machine` é ambiente, não red.

## Condição de retorno à planejadora

Retornar se algum teste depender semanticamente do relógio real (ex.: expiração medida por `sleep`) de forma que exija mudar contrato público. Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-001, AC-002), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
