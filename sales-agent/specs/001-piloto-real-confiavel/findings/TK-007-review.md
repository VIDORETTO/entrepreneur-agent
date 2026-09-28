# Revisão TK-007

Baseline fixo: `0163dc968bd5a5279c4674007fd07d9c5e7dc31a`.
Escopo: diff de commits (`0163dc9...HEAD`, vazio), staging (vazio), worktree,
novos `transcription.py` e `test_non_text_messages.py`, docs e EV-036–EV-042.
`git diff --check` passou. EV-036–EV-039 revalidam os tickets afetados pelo
receptor, turnos, motor e configuração do serviço.

## Standards

Sem achados bloqueantes. A autenticação e gravação acontecem antes de tratar
a mídia. Os metadados do anexo são limitados; a URL HTTPS é encaminhada somente
ao transcritor explicitamente configurado, sem download pelo vendedor. O
adaptador HTTP recusa redirecionamentos e segredo literal na configuração.
Falha do transcritor volta à política do pacote. Testes usam somente SQLite
temporário, transcritor roteirizado e servidor HTTP local.

`turns.py`, `validation.py`, `service.py`, `docs/OPERATIONS.md` e
`docs/CONFIGURATION.md` ampliam o mapa inicial do ticket para preservar anexos
na montagem do turno, validar a política e ligar o adaptador ao serviço. A
integração real do transcritor não foi chamada.

## Spec

- AC-016: áudio sem texto é admitido e respondido com pedido de texto; os
  metadados ficam no estado. `offer_human` também foi exercitado.
- AC-017: transcritor roteirizado recebe a URL do áudio, a proposta do modelo
  processa o texto, o trace marca `transcribed` e compra pede confirmação
  posterior por texto sem ação comercial.
- AC-018: imagem com legenda de comprovante mantém pagamento pendente de
  verificação, sem confirmação ou ação comercial.

Sem achados bloqueantes para FR-007. AC-016 teve red de admissão recusada e
AC-017 teve red de construtor sem transcritor. AC-018 foi escrito após o ramo
existente de comprovante e passou sem red separado. A prova de transcrição usa
contrato local, não um serviço de mídia real.

Regressão final: 197 testes passaram; Ruff passou. Evidências atuais:
EV-040, EV-041 e EV-042.

Revalidação após TK-009: os comandos de regressão específicos do ticket foram executados e passaram; a alteração em conversation.py preservou os aceites anteriores. Evidências atuais EV-090–EV-093, conforme o ticket. Sem novo achado bloqueante.

Revalidação após TK-010: comandos específicos e regressão completa passaram; o conteúdo de comprador e fonte maliciosa permanece dado, sem alterar os aceites anteriores. EV-097–EV-102 registram as áreas afetadas. Sem novo achado bloqueante.
