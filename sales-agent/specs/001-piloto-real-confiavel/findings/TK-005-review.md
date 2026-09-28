# Revisão TK-005

Baseline fixo: `b016731ad75efd27c6003be9926d6d8130489f8b`.
Escopo: diff de commits (`b016731...HEAD`, vazio), staging (vazio), worktree,
arquivos novos `service.py` e `test_service.py`, documentação e evidências
EV-020–EV-022. `git diff --check` passou. TK-003 recebeu somente revalidação
EV-019 depois de o CLI importar o serviço; sua revisão anterior permanece.

## Standards

Sem achados bloqueantes. O serviço usa o SQLite temporário real nos testes,
segredos `env:NOME` em memória, trava por diretório de dados e o ledger
persistente da entrega. Os testes observam HTTP, POST no servidor falso e a
interface pública do outbox. A falha de integridade é criada somente em banco
temporário. Nenhum serviço de produção foi acessado.

O exemplo systemd e o proxy em `docs/OPERATIONS.md` são instruções para
adaptação; não foram instalados nem executados. O teste de configuração e
exclusividade cobre código de saída 2 e mantém a primeira instância saudável.

## Spec

- AC-010: ACK 200 antes do POST, em menos de 200 ms; uma resposta pública
  chegou ao Chatwoot falso após a janela de turno.
- AC-011: `/readyz` retornou 200 e retornou 503 com motivo para interrupção e
  violação de chave estrangeira; `/healthz` continuou 200.
- AC-012: SIGTERM durante POST cujo retorno foi retido; após reinício, o
  servidor falso registrou exatamente um POST e o outbox ficou `sent` ou
  `unknown`.

Sem achados bloqueantes para FR-005. A prova é local; não atesta Chatwoot real
nem operação systemd/Nginx. O teste de AC-010 teve red de comando inexistente
antes da implementação; AC-011 e AC-012 foram escritos depois da orquestração
inicial e verificados sem ciclo red separado. Essa divergência do fluxo TDD
não altera os oráculos de aceitação executados.

Regressão final: 185 testes passaram; Ruff passou. Evidências atuais:
EV-020, EV-021, EV-022.

Revalidação após TK-012: o teste HTTP em subprocesso passou a assinar com o
relógio real, que é o usado pelo processo filho, mesmo sob o relógio deslocado
do pytest. EV-084 cobre novamente AC-010–AC-012 com cinco testes verdes. A
correção é restrita ao fixture; o serviço de produção não mudou. Sem novo
achado bloqueante.
