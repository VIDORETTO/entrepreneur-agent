# Avaliação

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
