# Revisão TK-004

Baseline fixo: `88a41c20d7531b252a7ebba63ff162213296d8ca`.
Escopo: diff de trabalho em `storage.py`, `channel.py`, `delivery.py`,
`tests/test_chatwoot_contract.py`, `docs/OPERATIONS.md`, evidências
EV-008–EV-010/EV-013/EV-015 e arquivos novos. Diff de commits e staging vazios
no início da revisão; `git diff --check` limpo.

## Standards

Sem achados bloqueantes. O ledger persiste no SQLite real e guarda hash do
conteúdo, sem texto. O registro `in_flight` acontece antes do POST ao servidor
Chatwoot falso; o ID do provedor é gravado na mesma transação que o ACK do
outbox. Os testes observam HTTP, resposta do receptor e estado público, sem
consultar tabelas diretamente.

## Spec

AC-007: o ID 42, devolvido pelo servidor falso, é reconhecido após reabrir a
base e não causa pausa. AC-008: ID 99 com conteúdo diferente pausa a conversa.
AC-009: o servidor falso ecoa antes de responder ao POST; o receptor identifica
o hash na mesma conversa durante o envio, e após 121 s classifica conteúdo
idêntico como intervenção humana. Sem achados bloqueantes nesses aceites.

Limite: a prova usa contrato HTTP local; nenhum webhook ou envio real foi
executado. O tratamento de outcome desconhecido e restart durante envio ainda
recebe teste de serviço específico em TK-005/AC-012.

Regressão executada: 181 testes passaram e Ruff passou. A migração aditiva
elevou o schema SQLite de 10 para 11; a suíte de migração existente passou.
