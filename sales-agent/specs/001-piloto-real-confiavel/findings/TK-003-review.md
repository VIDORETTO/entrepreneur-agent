# Revisão TK-003

Baseline fixo: `27baee9a78962ff739507753c8cce27e29d9e6ad`.
Escopo: `channel.py`, CLI, testes de contrato e regressão do canal,
`docs/OPERATIONS.md`, EV-005–EV-007. O diff completo, staging vazio,
commits vazios desde o baseline e arquivos novos foram inspecionados.
Alterações pendentes de TK-002 em metadados Python ficaram fora deste eixo.

## Standards

Sem achado bloqueante. O HMAC usa o corpo bruto e comparação em tempo
constante. Autenticação ocorre antes da gravação de evento; o arquivo do
diagnóstico aceita segredo somente por referência de ambiente e não o expõe.
Os testes existentes passaram a assinar pela fórmula publicada, preservando
seus oráculos de admissão, replay e pausa humana.

## Spec

AC-004: assinatura com timestamp admite uma vez e classifica replay.
AC-005: assinatura só do corpo recebe HTTP 401 por padrão, funciona com
`legacy-body` explícito, e `doctor` informa `legacy_signature`.
AC-006: timestamp 301 s antigo recebe HTTP 401 sem admissão e um envio válido
posterior do mesmo evento é admitido. EV-005–EV-007 registram os resultados.
Sem achado bloqueante nesses aceites. A prontidão que bloqueia modo legado
pertence ao TK-015; a detecção operacional de relógio dessincronizado ainda
precisa de integração com o serviço do TK-005.

Regressão: 177 testes passaram; Ruff passou. Não houve contato com o Chatwoot
de produção. A fórmula foi comparada por leitura com o adaptador existente de
`chatwoot-ai` e concorda em `timestamp.raw_body`.
