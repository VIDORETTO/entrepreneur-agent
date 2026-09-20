# 13 — Adaptar atendimento ao objetivo sem ampliar autonomia

**What to build:** O developer configura orientação comercial, suporte informativo ou pós-venda, e o comprador recebe uma resposta apropriada ao objetivo.

**Blocked by:** T12 — Redigir respostas completas com evidência e pergunta necessária; T08 — Inspecionar, simular e promover uma configuração revisada

**Status:** concluído localmente; ativação pública continua fora desta execução.

**Evidência registrada:** Testes públicos: tests/test_turns_and_profiles.py e AC031. Suporte/pós-venda, oferta direta, serviço consultivo, resposta a objeção com condição aprovada e transição de preferência configurada têm transições observáveis; descontos, urgência e novas permissões continuam bloqueados pelo estado estruturado.


**User Stories:** US08, US12, US15, US16 da especificação (numeração da lista).

## Acceptance criteria

- [x] Configuração aprovada seleciona comportamentos e condições de transição entre perfis.
- [x] Respostas curtas herdam contexto; ambiguidade não amplia capacidade.
- [x] Objeções usam condições aprovadas e não inventam descontos, garantias ou urgência.
- [x] Financeiro e suporte ficam em explicação/documentação/encaminhamento quando não há conector autorizado.
- [x] Preferência configurada e transição automática têm origem observável.
- [x] Perfis não introduzem novos agentes autônomos nem skills para desenvolvimento.

## TDD

**Seam exercitada:** S1 e S2.

**Primeiro red:** Mudar de intenção de compra para problema pós-compra; a conversa reconhece o novo objetivo sem continuar empurrando checkout.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Manter escopo comercial do produto; não construir helpdesk ou cobrança completos.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
