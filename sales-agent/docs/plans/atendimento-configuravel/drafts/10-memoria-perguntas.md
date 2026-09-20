# 10 — Lembrar respostas e correções sem repetir qualificação

**What to build:** O comprador retoma sua conversa, corrige fatos e avança com somente a pergunta necessária ainda aberta.

**Blocked by:** Nenhum — pode iniciar após aprovação do planejamento.

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_skills_and_configuration.py, tests/test_conversation_contract.py e AC003/AC026. Fatos, correções, lacunas, retomada e avanço direto são observáveis no estado. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US05, US06, US07, US09, US18 da especificação (numeração da lista).

## Acceptance criteria

- [x] Fatos e correções têm procedência por turno e substituição explícita.
- [x] Perguntas abertas e respondidas são observáveis pelo resultado da conversa e pelos turnos seguintes.
- [x] Saudações e confirmações curtas preservam o objetivo existente sem inventar intenção nova.
- [x] Correção que afeta uma cotação invalida o próximo passo antigo antes de nova operação.
- [x] Memória é isolada por negócio/conversa e não exige histórico bruto ilimitado.
- [x] Um pedido pronto continua avançando sem perguntas de marketing.

## TDD

**Seam exercitada:** S1.

**Primeiro red:** Informar quantidade e região, reiniciar a instância e responder o tamanho; a conversa avança sem perguntar os dados anteriores.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Adaptar a ideia de registro de perguntas do projeto antigo; não copiar seu modelo completo de persistência.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
