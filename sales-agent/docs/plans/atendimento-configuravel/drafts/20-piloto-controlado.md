# 20 — Operar observação, assistência e piloto com interrupção e métricas

**What to build:** O dono observa o atendimento, habilita assistência e autoriza um piloto limitado com meios de interrompê-lo e auditar seus resultados.

**Blocked by:** T19 — Entregar respostas e confirmar transferência no adaptador Chatwoot; T17 — Avaliar o atendimento e o modelo selecionado com evidência reproduzível; T13 — Adaptar atendimento ao objetivo sem ampliar autonomia

**Status:** concluído localmente; ativação pública pendente.

**Evidência registrada:** Testes públicos: tests/test_channel_pilot_supervisor.py e src/sales_agent/governance.py. Observação, assistência, coorte, limites, interrupção, métricas e o plano local de validação/reversão/retenção são estruturados; ativação pública e parâmetros operacionais do dono continuam externos.


**Bloqueio externo:** Ambiente de canal para validação real e autorização específica do dono antes de ativar envio público; limites de custo/latência e coorte definidos.

**User Stories:** US41, US42, US44, US48 da especificação (numeração da lista).

## Acceptance criteria

- [x] Modo padrão não envia publicamente; promoção entre modos é explícita por escopo.
- [x] Piloto exige versão avaliada, coorte e limites por período; expansão não ocorre automaticamente.
- [x] Interrupção por negócio/canal impede novas entregas elegíveis e é revalidada antes de cada envio.
- [x] Métricas incluem fila, cancelamentos, handoff, ausência de evidência, falhas, latência e custo sem texto bruto ou credenciais.
- [x] Plano de validação, reversão e retenção está disponível ao operador.
- [x] Relatório identifica exatamente backend/modelo/canal executados; se escolhido Farol, T16 é pré-requisito adicional para esse piloto.

## TDD

**Seam exercitada:** S2 e S3.

**Primeiro red:** Configurar modo observação e receber uma mensagem elegível; métricas e decisão aparecem sem envio público.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Implementação do controle é trabalho local; deploy e ativação pública permanecem ações separadas. Não criar painel como requisito.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
