# 04 — Consultar somente revisões vigentes e explicitar conflito material

**What to build:** O comprador recebe condições da revisão vigente da oferta correta; divergência material gera impedimento explicável.

**Blocked by:** T03 — Preservar revogação em reimportação e restauração de pacote

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_delivery_and_governance.py, tests/test_knowledge_and_configuration.py e cenário AC012. A seleção usa negócio, público, assunto, escopo, vigência e promoção explícita; linhas de bases antigas recebem `pending_review` durante a migração e só voltam à consulta após revisão explícita auditada. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US29, US33, US34 da especificação (numeração da lista).

## Acceptance criteria

- [x] Seleção de revisão vigente é explícita, por negócio, público, assunto/oferta e período aplicável.
- [x] Atualização mantém histórico; conteúdo diferente não sobrescreve silenciosamente a mesma identidade de revisão.
- [x] Divergência material da mesma fonte é detectada quando não existe promoção que a resolva.
- [x] Preços ou prazos de ofertas/assuntos distintos não produzem falso conflito.
- [x] Conteúdo interno não aparece na consulta destinada ao comprador.
- [x] Dados antigos são migrados ou sinalizados como pendentes de revisão, sem escolha lexicográfica de vigência.

## TDD

**Seam exercitada:** S2 e S1.

**Primeiro red:** Promover duas revisões sucessivas da mesma fonte e perguntar a condição; somente a revisão vigente sustenta a resposta.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Adicionar campos apenas necessários a essa trajetória. Não construir uma taxonomia comercial universal.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
