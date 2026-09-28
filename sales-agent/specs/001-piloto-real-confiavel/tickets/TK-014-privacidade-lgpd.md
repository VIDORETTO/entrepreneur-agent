---
schema: hybrid/ticket
schema_version: 1.0
id: TK-014
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 5
requires: ["TK-001"]
requirement_refs: ["FR-015"]
acceptance_refs: ["AC-045", "AC-046", "AC-047", "AC-048"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/privacy.py", "src/sales_agent/storage.py", "src/sales_agent/cli.py", "tests/test_privacy.py", "docs/OPERATIONS.md"]
verification_status: passed
---





# TK-014 — Exportação, eliminação, retenção e redação de dados pessoais

## Objetivo e limites

O operador atende pedidos de titular e relatórios/logs nunca expõem telefone, e-mail ou CPF. Refs: FR-015; AC-045, AC-046, AC-047, AC-048.

Não inclui: portal de autoatendimento do titular; DPO workflow.

## Leitura em ordem

1. `src/sales_agent/storage.py` → tabelas de conversa, eventos, efeitos, métricas de piloto — o que contém dado pessoal.
2. `src/sales_agent/evaluation.py` → geração de relatório — ponto de redação.
3. `SECURITY.md` → política — alinhamento.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- Pseudônimo = HMAC do contato com segredo local; efeitos e métricas mantêm pseudônimo.
- `redact` por regex (telefone BR/E.164, e-mail, CPF/CNPJ) aplicada em relatórios, métricas e logs estruturados.
- Retenção `privacy.retention_days` padrão **180** (Q2); `0` desativa o expurgo.
- Liberdade local: formato do JSON de exportação.
- Alternativas descartadas: apagar efeitos (quebraria conciliação e auditoria fiscal).

## Mapa de alterações

- Novo: `src/sales_agent/privacy.py`.
- Existente: `storage.py` → consultas por contato, anonimização, `privacy_audit`.
- Existente: `cli.py` → `privacy export|erase|purge`.
- Novo: `tests/test_privacy.py`; docs.

## Contrato técnico

- Entradas: `--business-id`, `--contact`, `--before`.
- Saídas: JSON; código 0/2.
- Invariantes: outros contatos intocados; métricas agregadas iguais.
- Erros: contato inexistente → JSON vazio, código 0.
- Efeitos: remoção/anonimização auditada.

## Exemplos de aceite

- **AC-045**: dois contatos → export de A não contém mensagens de B.
- **AC-046**: erase A → export vazio; `effects list` mostra pseudônimo; contagem de métricas igual.
- **AC-047**: varredura dos relatórios não encontra '+55 11 91234-5678', 'ana.teste@example.com', '123.456.789-09'.
- **AC-048**: retenção 30 dias, mensagens de 31 dias → removidas; outbox pendente preservado.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-001 (status `done`).

- [ ] TK-014.1 Escrever o primeiro caso (AC-045) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [ ] TK-014.2 Implementar o mínimo para green de AC-045; próximo caso só após green.
- [ ] TK-014.3 Implementar o mínimo para green de AC-046; próximo caso só após green.
- [ ] TK-014.4 Implementar o mínimo para green de AC-047; próximo caso só após green.
- [ ] TK-014.5 Implementar o mínimo para green de AC-048; próximo caso só após green.
- [ ] TK-014.6 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [ ] TK-014.7 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_privacy.py`
- Estado esperado: verde.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: —

## Condição de retorno à planejadora

Retornar se obrigação legal exigir reter conteúdo (decisão jurídica do dono). Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-045, AC-046, AC-047, AC-048), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
