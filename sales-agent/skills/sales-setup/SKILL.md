---
name: sales-setup
description: Diagnosticar instalação e declarar capacidades sem coletar segredos.
version: "1"
---

# Sales setup

Leia o plano, contrato, briefing e fontes aprovadas antes de perguntar ao dono.
Produza diagnóstico, dependências, versão do pacote e separação entre arquivos
gerenciados e dados privados. Uma dependência ausente deve desabilitar apenas a
capacidade afetada.

Depois do diagnóstico, siga com `seller-adapt` para escolher o próximo passo.
Para que o agente de código do projeto tenha estas skills e o `AGENTS.md`, rode
`vendedor skills install`.

## Saídas

- capacidades `enabled`, `assisted`, `disabled` ou `pending` com motivo;
- checkpoint que pode ser retomado sem histórico bruto;
- nenhum segredo em pacote, exemplos ou logs;
- validação `vendedor doctor` e `vendedor validate`.

## Referências

- `../../references/conversation-contract.md`
- `../../manifest.json`
- `../../briefing-do-negocio.md`
