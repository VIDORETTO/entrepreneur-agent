---
name: sales-business-discovery
description: Entrevista adaptativa do dono com perguntas por impacto e checkpoint.
version: "1"
---

# Descoberta do negócio

Use uma pergunta decisiva por rodada, até três se independentes. Primeiro
marque fatos de documentos como confirmados, inferidos, conflitantes ou
ausentes. Não transforme inferência em preço, permissão ou promessa.

Conclua quando uma capacidade tiver oferta, fluxo, fonte de verdade, limites de
ação, exceção e testes definidos. O comprador nunca recebe este roteiro.

Postura de venda: pergunte por cenário, nunca por rótulo ("passivo ou
ativo?"). A pergunta opcional `posture` mostra três respostas para o mesmo
pedido de preço: (A) só o preço, (B) preço e complemento, (C) preço e "quer
que eu já separe o seu?". A resposta vira `package.sales_posture.initiative`;
quais ofertas se complementam (`cross_sell`) é decisão explícita do dono,
nunca inferida. Sem resposta, o vendedor só responde.

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
