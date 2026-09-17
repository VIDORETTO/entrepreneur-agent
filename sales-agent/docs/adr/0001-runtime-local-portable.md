# Runtime local portátil com regras estruturadas

**Status: aceito.** O primeiro runtime será uma aplicação Python única, instalada localmente, com SQLite e CLI, mantendo estado, políticas e contratos de efeitos fora do prompt. Essa opção reduz dependências e torna a instalação reproduzível no ambiente disponível; adaptadores de modelo, conhecimento, canal e comércio ficam atrás de seams pequenos para permitir evolução posterior sem prometer equivalência automática entre fornecedores.

## Consequências

O produto será demonstrável sem credenciais externas, mas checkout, pagamento, agenda e transferência continuarão simulados até existir uma integração autorizada. O backend persistente de conhecimento é válido para desenvolvimento/piloto local; o relatório deve distinguir essa prova da integração opcional do RAG upstream do Farol.
