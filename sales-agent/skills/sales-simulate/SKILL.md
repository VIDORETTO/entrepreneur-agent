---
name: sales-simulate
description: Executar cenários observáveis e registrar trajetória, ações e limitações.
version: "1"
---

# Simulação e avaliação

Julgue perguntas, transições, ferramentas e efeitos, não apenas a frase final.
Inclua os cenários de contrato, variantes de linguagem e casos de falha. Separe
simulador, backend persistente, integração Farol upstream e modelo remoto.
Para ajustar com método (conjuntos `dev` e reservado, repetição, custo), use
`seller-evaluate-and-tune`.

```bash
vendedor model-check
vendedor evaluate --output reports/evaluation-latest.json
vendedor evaluate --split dev --repeat 4 --output reports/dev.json
```

O script desta skill é um wrapper para a avaliação local; seus resultados não
são benchmark de conversão.
