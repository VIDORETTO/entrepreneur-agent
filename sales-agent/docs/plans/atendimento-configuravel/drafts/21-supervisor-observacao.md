# 21 — Medir supervisor de qualidade sem alterar o atendimento

**What to build:** O dono compara a avaliação de qualidade com o resultado principal, medindo utilidade, custo e divergência sem mudar a resposta entregue.

**Blocked by:** T17 — Avaliar o atendimento e o modelo selecionado com evidência reproduzível

**Status:** concluído localmente; juiz externo pendente.

**Evidência registrada:** Testes públicos: tests/test_channel_pilot_supervisor.py. O modo desligado/observação preserva a resposta, registra candidato original, evidência, estado, pacote, latência, custo e as dimensões determinísticas de cobertura, repetição, suporte por evidência e tom; a comparação usa o mesmo denominador antes/depois da correção e o juiz externo não foi executado.


**User Stories:** US44, US46, US47 da especificação (numeração da lista).

## Acceptance criteria

- [x] Supervisor nasce desligado; modo observação nunca altera texto, capacidades ou envio.
- [x] Revisão é vinculada ao candidato, evidência, pacote e estado avaliados; candidato diferente invalida associação.
- [x] Avaliação cobre pedido não respondido, repetição, afirmação sem evidência e inadequação de tom.
- [x] Timeout e erro ficam mensurados sem derrubar o atendimento principal no modo observação.
- [x] Relatório compara falhas detectadas, falsos positivos, latência e custo com expectativas revisadas.
- [x] Supervisor não é juiz único nem substituto das validações determinísticas.

## TDD

**Seam exercitada:** S2 e S1.

**Primeiro red:** Supervisor em observação reprova um candidato aprovado pelo motor; a resposta original permanece e a divergência é registrada.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Não depende de piloto público: o golden set e a simulação já permitem demonstrar o benefício.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
