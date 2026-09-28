# Avaliação

`vendedor evaluate --split dev --repeat 4 --output reports/evaluation-latest.json`
executa os 38 cenários de contrato e 12 casos declarativos. O conjunto reservado
é executado apenas com `--split holdout` e contém 30 casos. Juntos, os 80 casos
seguem a distribuição do plano §17.1. Cada repetição usa SQLite temporário e
registra resultado, custo observado do adaptador e duração. O relatório traz
pass@1 (acertos entre todas as execuções), pass^k (casos que passaram em todas
as repetições), numerador e denominador por caso e agregados, p95, falhas
críticas e limiares de `evaluation/thresholds.json`.

Para conferir se o reservado mudou desde um relatório aprovado, execute
`vendedor evaluate --split holdout --repeat 4 --previous-report caminho/do/relatorio.json
--output reports/holdout-latest.json`. O SHA-256 do arquivo reservado aparece
somente no relatório do split `holdout`. Uma mudança marca `holdout_changed`
e impede `thresholds_met`. Sem `--previous-report`, o relatório não dispõe de
uma referência anterior para afirmar mudança. O arquivo reservado não é lido
na execução `dev`. `--model-config` aceita o mesmo JSON `env:NOME` usado por
`model-check`; a credencial é resolvida em memória. `--split contract` preserva
o relatório histórico de 38 cenários.

O conjunto reservado inclui tentativas de trocar preço e declarar aceitação
contratual, instrução escondida em fonte aprovada e pedido de revelar prompt
ou skills. Esses casos verificam cotação, resposta e trace, sem executar
qualquer ação externa. Ao acrescentar casos ao holdout, o SHA-256 muda; o
relatório anterior não serve como prova da versão nova.

`vendedor evaluate` executa os 38 cenários AC do contrato e emite JSON com caso,
status, criticidade, backend, adaptador de modelo, limitações, versão do pacote,
runtime e revisão Git quando disponível. `run.source.dirty: true` indica que o
relatório inclui mudanças ainda não representadas pelo commit registrado. O relatório
executado no ambiente atual deve ser gerado com:

```bash
vendedor evaluate --output reports/evaluation-latest.json
```

O conjunto usa negócios fictícios, simulador de comércio e backend SQLite
persistente. Isso prova invariantes de software e rastreabilidade local, não
conversão, disponibilidade de um provedor externo ou equivalência entre
modelos. A integração opcional do RAG upstream do Farol é uma capacidade
separada e permanece `not-executed` se Python/dependências não estiverem
instalados.

Os testes também exercitam deduplicação persistente, correção de cotação,
isolamento e revogação de fontes, transferência, follow-up, retomada,
restauração e rejeição de proposta de modelo incapaz.

O `evaluation/retrieval_set.json` contém 40 perguntas versionadas (32 respondíveis e 8 sem resposta). A avaliação `dev` e `holdout` informa `evaluation.retrieval.recall_at_5` (`hit`, `total`, `rate`) e `evaluation.retrieval.abstention` (`correct`, `total`, `rate`). Essas métricas usam a recuperação SQLite local e não medem o modelo remoto.

O conjunto reservado tem um checksum em `evaluation/holdout.sha256`. Somente `evaluate --split holdout` lê os casos de `holdout.json` e verifica esse checksum antes de executar. `pilot readiness` lê o checksum publicado e os metadados do arquivo reservado, sem ler seus casos; exige que ambos correspondam ao relatório apresentado. Um relatório gerado em outra instalação precisa ser reexecutado no ambiente do piloto.

O `evaluation/golden_set.json` acompanha a distribuição e mantém casos
sintéticos de pertinência, versões, revogação, intervenção humana, canal,
correção e segurança do modelo. Relatórios de instalação usam a cópia em
`share/vendedor-adaptavel/evaluation` quando o checkout não está disponível.

A versão atual do golden set contém 38 casos AC, cada um com expectativa,
afirmações proibidas, evidência e operações permitidas. O relatório marca
`golden_set_complete` e separa a verificação adversarial do modelo da avaliação
do atendimento. Custos ficam nulos para o adaptador determinístico local; isso
não é uma estimativa de um modelo remoto. A elegibilidade também exige zero
falhas críticas, 100% de aprovação do golden set e latência máxima abaixo do
limite registrado em `evaluation.thresholds`; o modelo, backend, canal e
geração de corpus selecionados ficam no mesmo relatório.
