---
schema: hybrid/ticket
schema_version: "1.0"
id: TK-011
effort: 001-piloto-real-confiavel
type: delivery
status: ready
ticket_revision: 1
requires: [TK-001]
requirement_refs: [FR-011]
acceptance_refs: [AC-031, AC-032, AC-033, AC-034]
spec_revision: 2
plan_revision: 2
owned_areas: [src/sales_agent/storage.py, src/sales_agent/knowledge.py, src/sales_agent/evaluation.py, evaluation/retrieval_set.json, tests/test_retrieval.py]
verification_status: not_run
---

# TK-011 — Recuperação BM25 com acentos normalizados e recall medido

## Objetivo e limites

A evidência pertinente vem primeiro, independentemente de acentos, com governança intacta e recall reportado. Refs: FR-011; AC-031, AC-032, AC-033, AC-034.

Não inclui: vetores/embeddings, reranking por modelo (roadmap).

## Leitura em ordem

1. `src/sales_agent/storage.py` → `search_sources` (sobreposição de tokens), migrações, tabela de fontes — implementação atual.
2. `src/sales_agent/knowledge.py` → `PersistentFarolKnowledge.search` — interface pública.
3. `tests/test_knowledge_and_configuration.py` → isolamento/revogação/vigência — regressões.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- Tabela virtual `sources_fts` (FTS5, `unicode61 remove_diacritics 2`) mantida por gatilhos; filtros de negócio/público/escopo/vigência/revogação aplicados no SQL antes de `ORDER BY bm25()`.
- Consulta sanitizada (tokens entre aspas, `OR`), sem sintaxe FTS vinda do comprador.
- Sem FTS5: fallback atual + aviso no `doctor`.
- Liberdade local: pesos por coluna (título vs conteúdo).
- Alternativas descartadas: stemmer próprio de português agora.

## Mapa de alterações

- Existente: `storage.py` → migração FTS + `search_sources`.
- Existente: `cli.py doctor` → `fts5: available`.
- Novo: `evaluation/retrieval_set.json` (≥ 40 perguntas, ≥ 8 sem resposta).
- Existente: `evaluation.py` → métrica recall@5/abstenção.
- Novo: `tests/test_retrieval.py`.

## Contrato técnico

- Entradas: negócio, consulta, filtros.
- Saídas: lista ranqueada como hoje (mesmas chaves).
- Invariantes: nunca retorna revogada/outro negócio/fora de vigência.
- Erros: consulta só com símbolos → lista vazia.
- Efeitos: nenhum.
- Compatibilidade: backfill do índice na migração.

## Exemplos de aceite

- **AC-031**: 'garantía' e 'GARANTIA' → fonte 'garantia de 30 dias'.
- **AC-032**: mesma frase em fonte revogada/outro negócio → não retornada.
- **AC-033**: 5.000 trechos, 100 consultas → p95 < 50 ms.
- **AC-034**: relatório `recall_at_5: {hit: n, total: m}` e `abstention: {...}`.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-001 (status `done`).

- [ ] TK-011.1 Escrever o primeiro caso (AC-031) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [ ] TK-011.2 Implementar o mínimo para green de AC-031; próximo caso só após green.
- [ ] TK-011.3 Implementar o mínimo para green de AC-032; próximo caso só após green.
- [ ] TK-011.4 Implementar o mínimo para green de AC-033; próximo caso só após green.
- [ ] TK-011.5 Implementar o mínimo para green de AC-034; próximo caso só após green.
- [ ] TK-011.6 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [ ] TK-011.7 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_retrieval.py tests/test_knowledge_and_configuration.py`
- Estado esperado: verde; recall reportado.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: SQLite sem FTS5 é ambiente (teste marca skip com motivo).

## Condição de retorno à planejadora

Retornar se recall@5 < 0,9 exigir vetores (vira candidato de roadmap, não ampliar escopo). Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-031, AC-032, AC-033, AC-034), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
