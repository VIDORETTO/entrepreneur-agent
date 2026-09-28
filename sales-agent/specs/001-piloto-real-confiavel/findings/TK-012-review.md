# Revisão TK-012

Baseline fixo: `d829acec5f5383b8c451da5e552c96a95ea0c112`. Inspecionados
commits desde a baseline (vazio), staging (vazio), worktree e arquivos novos
`evaluation/dev.json`, `evaluation/holdout.json`, `evaluation/thresholds.json`,
o relatório reservado e EV-080–EV-082. `git diff --check` e Ruff passaram.

## Standards

Sem achados bloqueantes. O runner executa cada repetição com SQLite temporário;
o modelo é uma interface externa controlável, e o holdout só é aberto no split
reservado. As 38 trajetórias anteriores continuam no dev. Os 42 novos casos
têm entrada, estado inicial, operações permitidas, esperado e proibido
declarados. O relatório mantém observações públicas, trace, custo quando há
usage real do adaptador, latência e falhas por repetição. A distribuição
agregada por categoria foi conferida contra §17.1.

O teste de relógio deslocado expôs um problema no teste HTTP do serviço: o
processo filho não usa o relógio deslocado do pytest. A assinatura do teste
agora usa o relógio real desse processo. Uma falha intermitente do teste
multiprocesso revelou desreferência de ação nula em `commit_event`; o guard
foi corrigido e o caso passou em dez execuções seguidas e na suíte completa.
Ambas as correções foram revistas como regressões locais, fora do mapa inicial
do TK-012.

## Spec

- AC-035: 50 dev + 30 holdout, distribuição combinada 16/12/12/12/12/8/8;
  quatro repetições do holdout produziram pass@1 120/120 e pass^4 30/30.
- AC-036: uma cópia modificada após o relatório anterior marcou
  `holdout_changed: true` e `thresholds_met: false`.
- AC-037: uma falha crítica em uma das quatro execuções produziu 3/4,
  pass^4 0/1 e `thresholds_met: false`.

Sem achados bloqueantes. EV-080–EV-082 registram os aceites atuais. A suíte
normal e a deslocada passaram com 208 testes; Ruff passou. Os relatórios
gerados em `reports/` usam negócios fictícios e adaptador determinístico.
Nenhuma qualidade de modelo remoto foi inferida. `holdout_reference_available`
fica falso no primeiro relatório sem `--previous-report`; um hash só pode ser
comparado quando um relatório anterior aprovado é fornecido.

Revalidação após TK-010: comandos específicos e regressão completa passaram; o conteúdo de comprador e fonte maliciosa permanece dado, sem alterar os aceites anteriores. EV-097–EV-102 registram as áreas afetadas. Sem novo achado bloqueante.
