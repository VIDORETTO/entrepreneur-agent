---
name: sales-simulate
description: Executar cenários observáveis e registrar trajetória, ações e limitações.
---

# Simulação e avaliação

Julgue perguntas, transições, ferramentas e efeitos, não apenas a frase final.
Inclua os 38 AC, variantes de linguagem e casos de falha. Separe simulador,
backend persistente, integração Farol upstream e modelo remoto.

```bash
vendedor model-check
vendedor evaluate --output reports/evaluation-latest.json
```

O script desta skill é um wrapper para a avaliação local; seus resultados não
são benchmark de conversão.
