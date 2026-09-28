# Vocabulário compartilhado

Use estes termos com o significado abaixo em todas as dez skills.

| Termo | Significado operacional |
| --- | --- |
| Demanda | Pedido original, com intenção e limites conhecidos. |
| Esforço | Unidade rastreada: projeto, funcionalidade, bug, migração ou mudança pequena. |
| Requisito | Comportamento ou restrição aceito, com ID estável `FR-xxx`. |
| Critério de aceite | Condição observável ligada a `AC-xxx`. |
| Decisão | Escolha com origem, justificativa e efeito sobre o trabalho. |
| Hipótese | Afirmação ainda não comprovada, com impacto e forma de verificar. |
| Module | Algo com Interface e Implementation, de uma função a uma fatia que atravessa níveis. |
| Interface | Tudo que o consumidor precisa saber: entradas, saídas, invariantes, ordem, erros e restrições. |
| Seam | Local em que o comportamento pode variar pela Interface. |
| Adapter | Implementação concreta que ocupa um Seam, inclusive um substituto de teste controlado. |
| Ticket | Fatia verificável, com aceites, dependências e pacote de execução. |
| Tarefa | Passo interno de um ticket; pode citar caminhos e comandos. |
| Gate | Condição para avançar, automática ou dependente de decisão humana. |
| Evidência | Resultado observado, com origem, ambiente e revisão dos insumos. |
| Baseline | Ponto fixo que inicia um escopo de revisão. |
| Checkpoint | Posição persistida e próxima ação válida. |
| Lacuna | Diferença sustentada por evidência entre intenção aceita e estado observado. |

`spec.md` define o que e por quê. `plan.md` define como a solução atende ao contrato. O glossário mantém linguagem; ADR registra decisão durável. Tickets são a fonte canônica da execução no perfil padrão.
