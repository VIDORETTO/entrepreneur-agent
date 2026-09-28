---
schema: hybrid/ticket
schema_version: 1.0
id: TK-013
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 5
requires: ["TK-001"]
requirement_refs: ["FR-014"]
acceptance_refs: ["AC-041", "AC-042", "AC-043", "AC-044"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/conversation.py", "src/sales_agent/config.py", "schemas/business-package.schema.json", "tests/test_human_access.py"]
verification_status: passed
---





# TK-013 — Acesso humano garantido, horário real e detecção de loop

## Objetivo e limites

O comprador sempre alcança uma pessoa, recebe horário verdadeiro e não repete o que já disse (Decreto 11.034/2022). Refs: FR-014; AC-041, AC-042, AC-043, AC-044.

Não inclui: roteamento por equipe/skill no Chatwoot; SLA.

## Leitura em ordem

1. `src/sales_agent/conversation.py` → `_decide` ramo `human` (~linha 728), `_ask`, trace de fallback — transferência atual.
2. `src/sales_agent/config.py` → validação do pacote — onde validar `service_hours`.
3. `CONTEXT.md` → Impedimento, Pergunta necessária — vocabulário.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- `service_hours`: fuso IANA + intervalos por dia; ausência = 'disponibilidade não informada' (não prometer horário).
- `loop_policy`: 2 fallbacks seguidos ou mesma necessidade sem resposta em 2 turnos ou sinal de frustração ⇒ oferecer/transferir.
- Nunca encerrar automaticamente; estado terminal só por conclusão registrada ou transferência.
- Liberdade local: lista de sinais de frustração.
- Alternativas descartadas: temporizador que encerra conversas inativas.

## Mapa de alterações

- Existente: `conversation.py` → contagem de fallback, `loop_detected`, mensagem de horário.
- Existente: `config.py` + schema → `service_hours`, `loop_policy`.
- Novo: `tests/test_human_access.py`.

## Contrato técnico

- Entradas: evento, pacote com horário, relógio.
- Saídas: resposta + ação `transfer` (`queued`).
- Invariantes: transferência carrega fatos confirmados (T10).
- Erros: `service_hours` inválido → validação do pacote falha.
- Efeitos: transferência idempotente.

## Exemplos de aceite

- **AC-041**: 2 mensagens incompreensíveis → 3ª resposta oferece atendente; `loop_detected`.
- **AC-042**: 23:00 America/Sao_Paulo, horário 9–18 → resposta contém 'amanhã às 9h'; transfer `queued`.
- **AC-043**: 'já falei isso três vezes, quero uma pessoa' → transfer sem pergunta; resumo tem tamanho M e SP.
- **AC-044**: relógio +7 dias sem evento → conversa não encerrada.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-001 (status `done`).

- [ ] TK-013.1 Escrever o primeiro caso (AC-041) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [ ] TK-013.2 Implementar o mínimo para green de AC-041; próximo caso só após green.
- [ ] TK-013.3 Implementar o mínimo para green de AC-042; próximo caso só após green.
- [ ] TK-013.4 Implementar o mínimo para green de AC-043; próximo caso só após green.
- [ ] TK-013.5 Implementar o mínimo para green de AC-044; próximo caso só após green.
- [ ] TK-013.6 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [ ] TK-013.7 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_human_access.py tests/test_conversation_contract.py`
- Estado esperado: verde.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: `zoneinfo` sem tzdata é ambiente (instalar `tzdata`).

## Condição de retorno à planejadora

Retornar se o dono quiser resposta automática diferente para fora do horário com venda (decisão de produto). Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-041, AC-042, AC-043, AC-044), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
