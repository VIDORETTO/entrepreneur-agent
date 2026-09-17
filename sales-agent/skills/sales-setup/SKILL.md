---
name: sales-setup
description: Diagnosticar instalação e declarar capacidades sem coletar segredos.
---

# Sales setup

Leia o plano, contrato, briefing e fontes aprovadas antes de perguntar ao dono.
Produza diagnóstico, dependências, versão do pacote e separação entre arquivos
gerenciados e dados privados. Uma dependência ausente deve desabilitar apenas a
capacidade afetada.

## Saídas

- capacidades `enabled`, `assisted`, `disabled` ou `pending` com motivo;
- checkpoint que pode ser retomado sem histórico bruto;
- nenhum segredo em pacote, exemplos ou logs;
- validação `vendedor doctor` e `vendedor validate`.

## Referências

- `../../references/conversation-contract.md`
- `../../manifest.json`
- `../../briefing-do-negocio.md`
