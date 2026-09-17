---
name: sales-knowledge-preparation
description: Preparar fontes documentais com origem, vigência, versão e revogação.
---

# Conhecimento verificável

Separe documentação de preço/benefício das ferramentas que confirmam estoque,
pagamento e agenda. O resultado de uma consulta precisa conter trecho,
`source_id`, versão, locator e negócio. Revogar uma fonte deve removê-la de
consultas futuras, não apenas de uma lista de metadados.

## Comandos

```bash
vendedor knowledge query --business-id exemplo "qual é a condição de acesso"
vendedor farol import --business-id exemplo ./artefato-farol
vendedor knowledge revoke --business-id exemplo --source-id fonte
```

O backend `sqlite-farol-v1` é persistente local. `InMemoryKnowledge` só serve
para testes e nunca deve ser anunciado como RAG de produção.
