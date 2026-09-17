---
name: sales-business-discovery
description: Entrevista adaptativa do dono com perguntas por impacto e checkpoint.
---

# Descoberta do negócio

Use uma pergunta decisiva por rodada, até três se independentes. Primeiro
marque fatos de documentos como confirmados, inferidos, conflitantes ou
ausentes. Não transforme inferência em preço, permissão ou promessa.

Conclua quando uma capacidade tiver oferta, fluxo, fonte de verdade, limites de
ação, exceção e testes definidos. O comprador nunca recebe este roteiro.

## Comandos

```bash
vendedor configure start --business-id exemplo --template physical
vendedor configure answer <session-id> "resposta do dono"
vendedor configure status <session-id>
vendedor configure finalize <session-id>
```

## Referências

- `../../briefing-do-negocio.md`
- `../../CONTEXT.md`
- fonte Matt em `../vendor-sources.md`
