# 06 — Descobrir skills de atendimento e configuração no produto instalado

**What to build:** O developer configurador lista e consulta as skills instaladas e suas referências, em uma instalação independente do checkout.

**Blocked by:** Nenhum — pode iniciar após aprovação do planejamento.

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_skills_and_configuration.py, tests/test_cli_and_evaluation.py e verificação posterior da wheel. O catálogo filtra os dois públicos do produto e diagnostica referências ausentes ou incompatíveis. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US23, US28, US29 da especificação (numeração da lista).

## Acceptance criteria

- [x] Catálogo possui somente os públicos atendimento e configuração, com identidade e versão.
- [x] Listagem e leitura distinguem recurso disponível de mera referência externa declarada.
- [x] Todas as referências necessárias às skills distribuídas funcionam após instalação fora do repositório.
- [x] Skill incompatível, desconhecida ou com recurso ausente gera diagnóstico acionável.
- [x] Descoberta pelo harness tem instruções verificáveis e não depende de instalação global silenciosa.
- [x] Nenhuma skill de programação, arquitetura ou manutenção do código é criada.

## TDD

**Seam exercitada:** S2.

**Primeiro red:** Instalar o pacote em ambiente isolado, listar as skills e abrir a referência de configuração; o recurso deve existir e ser legível.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Evoluir os packs existentes. Não presumir que empacotar arquivos os registra automaticamente no ambiente da IA.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
