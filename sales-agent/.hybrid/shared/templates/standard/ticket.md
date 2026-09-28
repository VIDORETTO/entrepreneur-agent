---
schema: hybrid/ticket
schema_version: "1.0"
id: TK-001
effort: [EFFORT_ID]
type: delivery
status: draft
ticket_revision: 1
requires: []
requirement_refs: [FR-001]
acceptance_refs: [AC-001]
spec_revision: 1
plan_revision: 1
owned_areas: [src/area, tests/area]
verification_status: not_run
---

# TK-001 — [Título da fatia]

## Objetivo e limites

Entrega um comportamento demonstrável ligado aos refs acima.

Não inclui: [exclusões específicas desta fatia].

## Leitura em ordem

1. `[path]` → `[symbol/section]` — [por que esta leitura é necessária].
2. `[path]` → `[symbol/section]` — [padrão existente a preservar].

## Decisões já resolvidas

- [Abordagem escolhida e motivo curto].
- Liberdade local: [detalhes reversíveis que a executora pode escolher].
- Alternativas descartadas: [somente as relevantes para não reabrir a decisão].

## Mapa de alterações

- Existente: `[path]` → `[symbol]` — [alteração prevista].
- Novo: `[path]` → `[NewSymbol]` — criar neste ticket.
- Fora da fatia: `[path/area]` — não alterar.

## Contrato técnico

- Entradas: [tipos, pré-condições e exemplos]
- Saídas: [tipos e resultado observável]
- Invariantes: [o que permanece verdadeiro]
- Erros: [tipo/resultado e quando ocorre]
- Efeitos: [efeitos observáveis, ordem e idempotência]
- Compatibilidade/concorrência: [quando aplicável]

## Exemplos de aceite

- **AC-001**: estado inicial [x] + entrada [y] → resultado esperado [z]; efeito permitido [a]; efeito proibido [b]. O oráculo vem de [spec/exemplo independente].

## Dependências e sequência de execução

Depende de: [TK IDs ou `nenhum`].

- [ ] TK-001.1 Escrever e executar o primeiro caso comportamental; observar red pelo motivo esperado.
- [ ] TK-001.2 Implementar o mínimo para green de [AC].
- [ ] TK-001.3 Executar regressão definida e conferir efeitos colaterais.
- [ ] TK-001.4 Registrar checkpoint e evidência, sem marcar checklist de reviewer.

## Validação

- Diretório: `[project root or subdirectory]`
- Comando/procedimento exato: `[command]`
- Estado esperado: [resultado observável]
- Comando identificado na configuração mas não executado: [none ou comando + motivo]
- Distinguir defeito de ambiente: [diagnóstico]

## Condição de retorno à planejadora

Pare e devolva evidência focalizada se o contrato ou caminho estiver incompatível, surgir decisão comportamental/arquitetural nova, faltar recurso obrigatório ou a dependência não estiver satisfeita. Preserve o teste e o progresso.

## Relatório de saída

Relate arquivos/símbolos alterados, critérios atendidos, resultados executados, `EV` refs, pendências, desvios e próxima ação. Não declare `done` sem verificação passada e revisão requerida.
