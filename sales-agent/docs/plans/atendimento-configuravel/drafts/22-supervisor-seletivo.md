# 22 — Aplicar revisão seletiva com uma correção e revalidação

**What to build:** Somente cenários configurados usam revisão ativa, com uma correção máxima e preservação das condições autorizadas.

**Blocked by:** T21 — Medir supervisor de qualidade sem alterar o atendimento; T14 — Invalidar respostas pendentes quando a evidência deixa de valer

**Status:** concluído localmente; adoção pública pendente.

**Evidência registrada:** Testes públicos: tests/test_channel_pilot_supervisor.py e src/sales_agent/governance.py. Uma correção é revalidada e registrada como resultado do candidato original, alegações comerciais novas são bloqueadas, a política opcional/obrigatória trata indisponibilidade do revisor e o relatório compara a linha de base determinística com custo/latência do supervisor usando denominadores comuns; adoção pública ainda exige decisão externa.


**Bloqueio externo:** Critérios de adoção definidos a partir da avaliação do supervisor; ativação por configuração explícita do dono.

**User Stories:** US16, US46, US47 da especificação (numeração da lista).

## Acceptance criteria

- [x] Política distingue revisão opcional e obrigatória, com falha de provedor tratada conforme o modo.
- [x] No máximo uma correção é tentada; nova reprovação produz bloqueio ou encaminhamento permitido.
- [x] Texto revisado passa novamente por cobertura de evidência, requisitos e autorização.
- [x] Mudança de estado, evidência ou pacote invalida revisão anterior antes do envio.
- [x] Revisor não executa ferramentas operacionais e aprovação não supera validação determinística.
- [x] Efeito na qualidade e custo é comparável ao modo sem supervisor e pode ser desativado sem migrar conversas.

## TDD

**Seam exercitada:** S1 e S2.

**Primeiro red:** Revisor sugere condição comercial não autorizada; o candidato revisado é bloqueado antes da entrega.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Entrega posterior; não é pré-requisito para primeiro piloto nem justificativa para corrigir por modelo uma política defeituosa.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
