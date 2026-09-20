# 15 — Importar geração Farol com validação e governança preservadas

**What to build:** O configurador importa uma geração verificável de conhecimento sem aprovar documentos bloqueados nem expor importação parcial.

**Blocked by:** T04 — Consultar somente revisões vigentes e explicitar conflito material

**Status:** concluído localmente; contrato upstream estável pendente.

**Evidência registrada:** Testes públicos: tests/test_delivery_and_governance.py e tests/test_knowledge_and_configuration.py. Manifesto, geração, revisão, hash, caminhos, limites, revogações, datas normalizadas em UTC, substituição de geração e promoção atômica são validados; a integração upstream estável não foi alegada. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US31, US32, US35, US36, US38 da especificação (numeração da lista).

## Acceptance criteria

- [x] Manifesto, revisão/geração, hashes e metadados exigidos pelo contrato suportado são validados antes da promoção.
- [x] Revogações upstream, registros e exclusões pertinentes são respeitados, além das revogações locais.
- [x] Importação prepara uma geração e a promove atomicamente; falha preserva a geração anterior utilizável.
- [x] Trechos mantêm procedência, revisão e localização; ausência de versão não vira revisão genérica aprovada.
- [x] Artefato legado/incompatível recebe diagnóstico explícito e tratamento de migração, sem aprovação silenciosa.
- [x] Limites de tamanho, contagem e caminhos impedem leitura fora do artefato ou promoção parcial.

## TDD

**Seam exercitada:** S2.

**Primeiro red:** Importar artefato cujo registro revoga um documento ainda presente no corpus; consultar nunca retorna esse documento.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Fixar e testar o contrato publicado disponível; suporte à versão futura pertence ao T16 e não é presumido.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
