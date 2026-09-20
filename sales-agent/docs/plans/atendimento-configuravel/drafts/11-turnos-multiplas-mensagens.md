# 11 — Agrupar mensagens consecutivas e preservar todas as perguntas

**What to build:** Mensagens fragmentadas formam um turno coerente sem perder perguntas, com pausa humana imediata e limite de espera.

**Blocked by:** T01 — Respeitar pausa humana e recusa também nas respostas pendentes; T10 — Lembrar respostas e correções sem repetir qualificação

**Status:** concluído localmente.

**Evidência registrada:** Testes públicos: tests/test_turns_and_profiles.py e tests/test_channel_pilot_supervisor.py. A janela é configurável, mensagens são duráveis e ordenadas, duplicatas são deduplicadas e urgência ignora o debounce. Critérios sem marcação permanecem não demonstrados nesta execução.


**User Stories:** US03, US04, US10, US11 da especificação (numeração da lista).

## Acceptance criteria

- [x] Janela e espera máxima são configuráveis; fluxo contínuo não adia atendimento indefinidamente.
- [x] Identificadores e ordem das mensagens são preservados no turno composto.
- [x] Duplicatas não geram nova operação nem nova resposta.
- [x] Perguntas independentes permanecem identificáveis para resposta posterior.
- [x] Recusa e solicitação de humano interrompem a espera e obedecem à pausa.
- [x] Reinício antes do vencimento mantém as mensagens duráveis e processáveis.

## TDD

**Seam exercitada:** S2 e S1.

**Primeiro red:** Enviar oferta, tamanho e região em mensagens curtas durante a janela e processar o turno; uma única trajetória usa os três dados.

A aceitação foi verificada nas seams públicas indicadas e nas regressões pertinentes; critérios sem marcação permanecem fora da evidência atual. Não escrever toda a bateria antes da implementação. Doubles apenas em dependências externas, relógio ou aleatoriedade; SQLite de teste real. Resultado esperado vem dos critérios acima, não do algoritmo implementado.

## Limites e demonstração

Sem dependência do canal real; usar entrada local/CLI e reutilizar a pausa definida no T01. Não depende de envio externo.

Demonstrar os critérios pelas interfaces públicas propostas e registrar quais provas foram locais, de contrato ou externas. Não consultar tabelas para provar comportamento nem testar helpers privados. Atualizar documentação operacional relevante e executar regressões proporcionais à mudança. Refatoração, se necessária, pertence à revisão.
