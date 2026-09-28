---
schema: hybrid/ticket
schema_version: 1.0
id: TK-008
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 22
requires: ["TK-001"]
requirement_refs: ["FR-008"]
acceptance_refs: ["AC-019", "AC-020", "AC-021", "AC-022", "AC-023"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/model.py", "src/sales_agent/cli.py", "tests/test_model_adapter.py", "docs/CONFIGURATION.md"]
verification_status: passed
last_update: Evidence invalidated after an input changed.
---






















# TK-008 — Adaptador de modelo real com saída estruturada, reparo, custo e fallback

## Objetivo e limites

O dono conecta um modelo real que interpreta mensagens dentro de contrato estrito, com custo e falhas visíveis. Refs: FR-008; AC-019, AC-020, AC-021, AC-022, AC-023.

Não inclui: redação de resposta (TK-009); perfil Anthropic (CAND-007); execução real sem `OPENAI_API_KEY`.

## Leitura em ordem

1. `src/sales_agent/model.py` → `ModelAdapter`, `HTTPModelAdapter.__init__/_send/propose`, `allowed_intents` — contrato atual.
2. `src/sales_agent/types.py` → `Proposal` — campos da proposta.
3. `tests/test_model_adapter.py` → casos existentes — regressões de endpoint seguro/limites.
4. `src/sales_agent/cli.py` → `model-check` — comando a estender.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- Perfis `openai` (padrão; `https://api.openai.com/v1/chat/completions`, `response_format` `json_schema` com `strict: true`, tratar `refusal`) e `openai-compatible` (mesmo corpo, sem depender de `strict`). Nome do modelo por `SELLER_MODEL_NAME`; chave por `env:OPENAI_API_KEY`; preços por config.
- Mensagens: `system` = contrato + pacote resumido + skills do comprador; `user` = texto do comprador em bloco delimitado `<buyer_message>` tratado como dado.
- Um reparo com o erro de validação; depois fallback configurável `rules` | `assist`.
- Custo = tokens × tabela `prices` da config; métricas sem conteúdo.
- Liberdade local: formato interno do JSON Schema; nome do campo de config.
- Alternativas descartadas: SDKs oficiais (dependências).

## Mapa de alterações

- Existente: `model.py` → perfis, schema, reparo, usage.
- Existente: `types.py` → `Proposal.raw` inclui `usage`/`latency_ms` (sem conteúdo).
- Existente: `conversation.py` → trace `model_contract_failed`/`model_timeout` e fallback.
- Existente: `cli.py` → `model-check --adapter http --profile`.
- Existente: `tests/test_model_adapter.py`.

## Contrato técnico

- Entradas: texto, pacote, estado.
- Saídas: `Proposal` validada.
- Invariantes: modelo nunca executa efeito; intents fora do contrato rejeitados.
- Erros: HTTP, timeout, schema.
- Efeitos: 1–2 chamadas HTTP por turno.
- Compatibilidade: variáveis `SELLER_MODEL_*` atuais continuam válidas (perfil `openai-compatible`).

## Exemplos de aceite

- **AC-019**: corpo recebido pelo servidor falso tem `messages[0].role == 'system'` e o texto do comprador só dentro de `<buyer_message>`.
- **AC-020**: script [inválido, válido] → proposta aceita, 2 chamadas.
- **AC-021**: script [inválido, inválido] → nenhuma ação, trace `model_contract_failed`, resposta do fallback.
- **AC-022**: usage 1000/200 e preço 1/5 por 1M → custo 0,002 registrado.
- **AC-023**: mesmo caso passa nos perfis `openai` e `openai-compatible`; relatório mostra perfil e modelo.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-001 (status `done`).

- [x] TK-008.1 Escrever o primeiro caso (AC-019) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [x] TK-008.2 Implementar o mínimo para green de AC-019; próximo caso só após green.
- [x] TK-008.3 Implementar o mínimo para green de AC-020; próximo caso só após green.
- [x] TK-008.4 Implementar o mínimo para green de AC-021; próximo caso só após green.
- [x] TK-008.5 Implementar o mínimo para green de AC-022; próximo caso só após green.
- [x] TK-008.6 Implementar o mínimo para green de AC-023; próximo caso só após green.
- [x] TK-008.7 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [x] TK-008.8 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_model_adapter.py && vendedor model-check`
- Estado esperado: verde; `model-check` com rules-v1 continua aprovado.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: Sem credencial real: execução real `not_run`.

## Condição de retorno à planejadora

Retornar se a documentação atual da OpenAI indicar que Chat Completions não suporta mais Structured Outputs para o modelo configurado (decidir migração para Responses API). Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-019, AC-020, AC-021, AC-022, AC-023), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
