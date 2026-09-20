# 08 — Inspecionar, simular e promover uma configuração revisada

**What to build:** O developer configurador vê a configuração efetiva, explica bloqueios, compara uma proposta e demonstra seu atendimento antes da promoção.

**Blocked by:** T03 — Preservar revogação em reimportação e restauração de pacote; T07 — Configurar uma capacidade por checkpoint orientado a impedimentos

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_skills_and_configuration.py, tests/test_knowledge_and_configuration.py e tests/test_cli_and_evaluation.py. Inspeção, diff, simulação isolada, promoção versionada e restauração passam pela validação estruturada. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US20, US21, US22, US24, US25, US26, US27, US30 da especificação (numeração da lista).

## Acceptance criteria

- [x] Inspeção mostra versão, capacidades e motivos, fontes e skills declaradas/disponíveis; aplicação em runtime é indicada somente quando observada.
- [x] Diff destaca mudanças comerciais, público, fontes e autonomia sem revelar segredos.
- [x] Simulação usa estado isolado e não modifica estoque, conversas ou efeitos ativos.
- [x] Promoção exige versão nova, validação e decisões estruturadas aprovadas; texto livre não concede capacidade.
- [x] Restauração é nova promoção e mantém governança atual de fontes.
- [x] A skill de configuração permite realizar o fluxo sem editar o código do produto.

## TDD

**Seam exercitada:** S2.

**Primeiro red:** Simular um rascunho alterado e verificar que a consulta da versão ativa continua mostrando as condições anteriores.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Preservar a reaprovação explícita definida no T03 quando o mecanismo for usado. O ticket não depende de um painel visual.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
