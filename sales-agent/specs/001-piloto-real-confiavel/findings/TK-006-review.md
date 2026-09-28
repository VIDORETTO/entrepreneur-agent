# Revisão TK-006

Baseline fixo: `907b468f64c28ccfd8468e32c2f804a8449f0e9b`.
Escopo: diff de commits (`907b468...HEAD`, vazio), staging (vazio), worktree,
arquivo novo `tests/test_channel_window.py`, documentação e EV-023–EV-035.
`git diff --check` passou. EV-023–EV-026 revalidam tickets anteriores
afetados pelo binding, armazenamento e entrega.

## Standards

Sem achados bloqueantes. O instante de admissão vem da fila SQLite durável e é
comparado ao relógio injetado na entrega. O status terminal e a intenção de
nota privada são gravados em uma transação, com chave estável para evitar nota
duplicada. Os testes usam SQLite temporário, relógio fixo e transporte Chatwoot
falso; observam outbox público e chamadas do transporte, sem consultar tabelas.

`storage.py` e `governance.py` foram incluídos além do mapa inicial do ticket:
o primeiro fornece consulta persistente e transação atômica da nota; o segundo
permite a nota interna em observação sem permitir envio durante interrupção.
Não houve mudança de schema nem envio externo real.

## Spec

- AC-013: resposta pública enviada com 23h59min59s e no limite de 24h.
- AC-014: 24h+1s e instante ausente encerram o item em `window_closed`; uma
  única nota privada chega ao atendente, inclusive em observação.
- AC-015: follow-up Chatwoot agendado após mensagem válida não é enviado fora
  da janela; a entrega fecha com `window_closed` e a revalidação informa esse
  motivo.

Sem achados bloqueantes para FR-006. A regra não trata templates HSM. O canal
de teste é sintético e não comprova comportamento de uma conta WhatsApp real.

Red esperado foi observado em AC-013 (binding sem `channel_kind`), AC-014
(`cancelled` em vez de `window_closed`) e AC-015 (follow-up marcado `sent` fora
da janela). Depois das correções, 191 testes passaram e Ruff passou.
Evidências atuais: EV-033, EV-034, EV-035.

Revalidação após TK-009: os comandos de regressão específicos do ticket foram executados e passaram; a alteração em conversation.py preservou os aceites anteriores. Evidências atuais EV-090–EV-093, conforme o ticket. Sem novo achado bloqueante.

Revalidação após TK-010: comandos específicos e regressão completa passaram; o conteúdo de comprador e fonte maliciosa permanece dado, sem alterar os aceites anteriores. EV-097–EV-102 registram as áreas afetadas. Sem novo achado bloqueante.
