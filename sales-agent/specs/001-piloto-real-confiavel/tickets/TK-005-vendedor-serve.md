---
schema: hybrid/ticket
schema_version: 1.0
id: TK-005
effort: 001-piloto-real-confiavel
type: delivery
status: done
ticket_revision: 11
requires: ["TK-004"]
requirement_refs: ["FR-005"]
acceptance_refs: ["AC-010", "AC-011", "AC-012"]
spec_revision: 2
plan_revision: 2
owned_areas: ["src/sales_agent/service.py", "src/sales_agent/cli.py", "tests/test_service.py", "docs/OPERATIONS.md"]
verification_status: passed
last_update: EV-038 revalidou após TK-007; revisão anterior permanece aplicável
---











# TK-005 — Comando `vendedor serve` com receptor, turnos, entrega e saúde

## Objetivo e limites

Um operador sobe o atendimento com um comando e observa a trajetória completa contra um Chatwoot falso. Refs: FR-005; AC-010, AC-011, AC-012.

Não inclui: TLS/proxy reverso (documentar Nginx), múltiplos processos, autoscaling, janela 24 h (TK-006).

## Leitura em ordem

1. `src/sales_agent/channel.py` → `ChatwootChannelService.receive/process/deliver`, `ChatwootReceiver.wsgi`, `HTTPChatwootTransport` — peças a orquestrar.
2. `src/sales_agent/turns.py` → `TurnAssembler.process_due` — janela de turno.
3. `src/sales_agent/delivery.py` → `DeliveryProcessor.process_once` — ciclo de entrega com lease.
4. `src/sales_agent/governance.py` → `PilotController.inspect` — interrupção para `/readyz`.
5. `src/sales_agent/cli.py` → registro de subcomandos — padrão de parser.

Caminhos relativos a `sales-agent/`; symbols verificados na baseline `9abaf95`.

## Decisões já resolvidas

- `wsgiref.simple_server` em thread + loop de worker (turnos e entrega) com `threading.Event` para parada.
- Config por arquivo JSON `--config` com segredos `env:NOME`; nunca aceita segredo literal.
- SIGTERM: parar de admitir, concluir item em curso até timeout de lease, sair; itens sem ACK ficam para `recover` → `unknown`.
- `/healthz` = processo vivo; `/readyz` = `storage check` ok + canal não interrompido + binding válido.
- Liberdade local: intervalo do loop (padrão 1 s), formato de log (JSON por linha, redigido).
- Alternativas descartadas: FastAPI/uvicorn (dependência nova sem necessidade de volume).

## Mapa de alterações

- Novo: `src/sales_agent/service.py` → `ServiceConfig`, `ChannelServer`.
- Existente: `cli.py` → subcomando `serve`.
- Novo: `tests/test_service.py` (subprocesso + `chatwoot_server`).
- Existente: `docs/OPERATIONS.md` → execução, systemd de exemplo, proxy.

## Contrato técnico

- Entradas: `--config`, `--data-dir`, `--host`, `--port`.
- Saídas: HTTP 2xx/401/400 no webhook; JSON em `/healthz` e `/readyz`.
- Invariantes: ACK antes de modelo/Chatwoot; um processo por data-dir.
- Erros: config com segredo literal → sai com código 2.
- Efeitos: POST ao Chatwoot pelo transporte.
- Idempotência: chaves de outbox existentes.

## Exemplos de aceite

- **AC-010**: webhook válido → 200 em < 200 ms; após janela (relógio de teste) servidor falso recebe 1 POST com a resposta.
- **AC-011**: `/readyz` 200 `{ready:true}`; após `pilot interrupt` → 503 com `reason`.
- **AC-012**: servidor falso segura POST; SIGTERM; reinício → exatamente 1 POST recebido; item `sent` ou `unknown`.

Oráculo: valores literais de `spec.md` e `tdd.md` (casos com expectativa literal), nunca recalculados pelo código de produção.

## Dependências e sequência de execução

Depende de: TK-004 (status `done`).

- [x] TK-005.1 Escrever o primeiro caso (AC-010) na seam indicada em `plan.md`; observar red pelo motivo previsto em `tdd.md`.
- [x] TK-005.2 Implementar o mínimo para green de AC-010; próximo caso só após green.
- [x] TK-005.3 Implementar o mínimo para green de AC-011; próximo caso só após green.
- [x] TK-005.4 Implementar o mínimo para green de AC-012; próximo caso só após green.
- [x] TK-005.5 Executar regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualizar documentação da interface.
- [x] TK-005.6 Registrar evidência (`hybrid.py evidence add --executed`) e checkpoint; não marcar checklist de reviewer.

## Validação

- Diretório: `sales-agent/`
- Comando/procedimento exato: `python -m pytest -q tests/test_service.py`
- Estado esperado: três casos verdes em < 30 s.
- Comando identificado na configuração mas não executado: `ruff check src tests` (configurado em `pyproject.toml`; executar no fim do ticket).
- Distinguir defeito de ambiente: Porta efêmera indisponível ou subprocesso sem `vendedor` no PATH é ambiente (instalar `-e .`).

## Condição de retorno à planejadora

Retornar se o modelo de concorrência SQLite (WAL, busy_timeout) não suportar receptor + worker no mesmo processo. Também retornar se a spec/plan estiverem em revisão diferente da referenciada, se surgir decisão de comportamento nova ou se uma dependência não estiver `done`. Preservar teste e progresso.

## Relatório de saída

Relatar arquivos/símbolos alterados, ACs atendidos (AC-010, AC-011, AC-012), comandos executados e resultados, `EV` refs, pendências, desvios e próxima ação. Não declarar `done` sem verificação `passed` e revisão separada.
