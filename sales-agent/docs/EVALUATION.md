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
