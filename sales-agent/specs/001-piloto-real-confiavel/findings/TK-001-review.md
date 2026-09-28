# Revisão TK-001

Baseline fixo: `9abaf956eeaa8459fc237c185c14d4241529063e`.
Escopo inspecionado: diff de trabalho do ticket, arquivo novo `clock.py`,
workflow em `../.github/workflows/sales-agent-ci.yml`; diff de commits e
staging vazios nesta revisão. Estado de referência: EV-001 e EV-002.

## Standards

Sem achados bloqueantes. O teste mantém o exemplo literal de vigência e usa
SQLite temporário real. A dependência `time-machine` fica apenas em `dev`.
O job de CI usa o mesmo comando de deslocamento executado localmente.

## Spec

AC-001: o caso Farol busca a política vigente sob relógio fixo e mantém as
expectativas literais de normalização. AC-002: 172 testes passaram com o
relógio normal e deslocado em 400 dias. Sem achados bloqueantes no escopo do
ticket. A fachada `utc_now()` e outros módulos temporais continuam para os
tickets seguintes, conforme limite expresso do TK-001.

Limite: o job novo ainda não foi executado no GitHub Actions; a prova de
AC-002 é a execução local do mesmo comando e a configuração inspecionada.
