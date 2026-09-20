# Plano e registro de execução — atendimento configurável

Data: 20/09/2026. Estado: implementação local concluída nas fatias demonstráveis; não publicada em tracker e sem ativação externa.

## Escopo

Somente duas famílias de skills: atendimento ao comprador e configuração do negócio pelo developer com IA. O developer deve conseguir descobrir as skills internas, inspecionar e adaptar o pacote comercial, validar e simular o resultado. Não criar skills para desenvolver ou manter o software.

A especificação, os tickets verticais, os critérios de aceite e a estratégia TDD continuam registrados aqui. A execução local também implementou as fatias possíveis, adicionou testes e atualizou a evidência. Nenhuma alteração em produção, deploy ou ativação pública faz parte desta entrega.

## Documentos

- [Especificação](spec.md): problema, solução, 48 histórias, decisões, testes e exclusões.
- [Estratégia TDD](tdd.md): seams propostas, casos, evidência e critérios de conclusão.
- [Matriz de rastreabilidade](TRACEABILITY.md): ticket, seam, implementação,
  teste e limite de evidência.
- Os 22 rascunhos abaixo: um documento por ticket, com resultado demonstrável, bloqueios, critérios de aceite e primeiro red.

## Seams para confirmação

1. **S1 — Atendimento:** SellerEngine.handle, observando resposta/silêncio, estado, evidências e operações por turnos.
2. **S2 — CLI:** configuração, fontes, skills, simulação, avaliação e ciclo de entrega/worker; retomada em outro processo e instalação sem checkout.
3. **S3 — Canal externo:** entrada HTTP autenticada e entrega observada por servidor falso Chatwoot. Introduzida apenas nos tickets de canal.

Conhecimento continua substituível pelo adaptador existente; os testes de aceitação observam seu efeito por S1/S2. A entrada e a entrega de Chatwoot usam S3 com fixtures e transporte falso. As seams foram exercitadas pelas interfaces públicas; os drafts registram, ticket a ticket, os critérios marcados e as lacunas restantes.

## Tickets e estado atual

Os 22 drafts permanecem como registro de critérios e dependências. O estado
abaixo distingue evidência local de contratos externos ainda não executados:

| Faixa | Estado |
|---|---|
| T01–T15 | Implementados localmente; dados antigos de T04 ficam `pending_review` até revisão explícita e o contrato upstream estável continua separado no T16. |
| T16 | Bloqueado: versão estável e cliente executável do Farol não disponíveis. |
| T17 | Implementado com golden set sintético; modelo remoto não executado. |
| T18–T19 | Implementados por contrato local com fixtures; Chatwoot real não executado. |
| T20 | Controle local e plano operacional implementados; ativação pública depende de autorização, coorte e limites definidos externamente. |
| T21 | Supervisor local implementado com dimensões determinísticas; juiz externo não executado. |
| T22 | Política, comparação, uma correção seletiva e revalidação implementadas; adoção pública depende de critérios externos. |

Cada draft marca somente critérios sustentados pela implementação e pelos testes
disponíveis. Critérios sem marcação continuam pendentes.

1. **[T01 — Respeitar pausa humana e recusa também nas respostas pendentes](drafts/01-silencio-pausa-recusa.md)**
   - Bloqueado por: nenhum ticket.
   - Entrega: O comprador que pede uma pessoa ou recusa contato deixa de receber respostas automáticas incompatíveis, inclusive as que já estavam pendentes.

2. **[T02 — Revalidar cada entrega e impedir conclusão por worker obsoleto](drafts/02-entrega-revalidada.md)**
   - Bloqueado por: T01.
   - Entrega: O operador processa um ciclo de entrega que verifica o estado vigente antes do envio e distingue confirmação, cancelamento e resultado desconhecido.

3. **[T03 — Preservar revogação em reimportação e restauração de pacote](drafts/03-revogacao-persistente.md)**
   - Bloqueado por: nenhum ticket.
   - Entrega: Uma fonte revogada continua indisponível após reimportar o mesmo pacote ou restaurar uma configuração anterior.

4. **[T04 — Consultar somente revisões vigentes e explicitar conflito material](drafts/04-vigencia-escopo-conflito.md)**
   - Bloqueado por: T03.
   - Entrega: O comprador recebe condições da revisão vigente da oferta correta; divergência material gera impedimento explicável.

5. **[T05 — Responder apenas ao que a evidência recuperada sustenta](drafts/05-evidencia-pertinente.md)**
   - Bloqueado por: T04.
   - Entrega: O comprador recebe a condição perguntada ou uma lacuna explícita, em vez do primeiro documento vagamente relacionado.

6. **[T06 — Descobrir skills de atendimento e configuração no produto instalado](drafts/06-catalogo-skills.md)**
   - Bloqueado por: nenhum ticket.
   - Entrega: O developer configurador lista e consulta as skills instaladas e suas referências, em uma instalação independente do checkout.

7. **[T07 — Configurar uma capacidade por checkpoint orientado a impedimentos](drafts/07-descoberta-configuracao.md)**
   - Bloqueado por: T06.
   - Entrega: O developer com IA conduz a configuração de uma oferta com decisões do dono, aproveitando material aprovado e retomando sem repetir perguntas.

8. **[T08 — Inspecionar, simular e promover uma configuração revisada](drafts/08-inspecao-promocao.md)**
   - Bloqueado por: T03, T07.
   - Entrega: O developer configurador vê a configuração efetiva, explica bloqueios, compara uma proposta e demonstra seu atendimento antes da promoção.

9. **[T09 — Aplicar skills aprovadas na interpretação do atendimento](drafts/09-skills-runtime.md)**
   - Bloqueado por: T06.
   - Entrega: O atendimento usa as orientações elegíveis do pacote e permite verificar quais skills participaram da decisão.

10. **[T10 — Lembrar respostas e correções sem repetir qualificação](drafts/10-memoria-perguntas.md)**
   - Bloqueado por: nenhum ticket.
   - Entrega: O comprador retoma sua conversa, corrige fatos e avança com somente a pergunta necessária ainda aberta.

11. **[T11 — Agrupar mensagens consecutivas e preservar todas as perguntas](drafts/11-turnos-multiplas-mensagens.md)**
   - Bloqueado por: T01, T10.
   - Entrega: Mensagens fragmentadas formam um turno coerente sem perder perguntas, com pausa humana imediata e limite de espera.

12. **[T12 — Redigir respostas completas com evidência e pergunta necessária](drafts/12-resposta-completa.md)**
   - Bloqueado por: T05, T09, T11.
   - Entrega: O comprador recebe uma resposta natural que cobre suas perguntas, preserva fatos aprovados e não repete coleta já concluída.

13. **[T13 — Adaptar atendimento ao objetivo sem ampliar autonomia](drafts/13-perfis-objecoes.md)**
   - Bloqueado por: T12, T08.
   - Entrega: O developer configura orientação comercial, suporte informativo ou pós-venda, e o comprador recebe uma resposta apropriada ao objetivo.

14. **[T14 — Invalidar respostas pendentes quando a evidência deixa de valer](drafts/14-revalidar-evidencia-envio.md)**
   - Bloqueado por: T02, T05.
   - Entrega: Uma resposta preparada com uma fonte posteriormente revogada ou substituída não é enviada ao comprador.

15. **[T15 — Importar geração Farol com validação e governança preservadas](drafts/15-importacao-farol-governada.md)**
   - Bloqueado por: T04.
   - Entrega: O configurador importa uma geração verificável de conhecimento sem aprovar documentos bloqueados nem expor importação parcial.

16. **[T16 — Consultar a versão estável do Farol pelo atendimento](drafts/16-farol-estavel.md)**
   - Bloqueado por: T15, T05; também há bloqueio externo descrito no ticket.
   - Entrega: O comprador recebe resposta baseada no backend Farol efetivamente executado, com geração e evidência auditáveis.

17. **[T17 — Avaliar o atendimento e o modelo selecionado com evidência reproduzível](drafts/17-avaliacao-modelo-atendimento.md)**
   - Bloqueado por: T12, T08.
   - Entrega: O dono compara configurações/modelos por qualidade factual, comportamento, custo e latência, distinguindo simulação de execução real.

18. **[T18 — Receber eventos Chatwoot autenticados de forma durável](drafts/18-entrada-chatwoot.md)**
   - Bloqueado por: nenhum ticket.
   - Entrega: Eventos válidos do primeiro canal entram uma vez no processamento local, com ACK rápido e isolamento por negócio.

19. **[T19 — Entregar respostas e confirmar transferência no adaptador Chatwoot](drafts/19-canal-entrega-transferencia.md)**
   - Bloqueado por: T14, T18, T11.
   - Entrega: Uma conversa recebida pelo canal percorre o motor e chega a envio ou transferência observáveis, respeitando intervenção humana.

20. **[T20 — Operar observação, assistência e piloto com interrupção e métricas](drafts/20-piloto-controlado.md)**
   - Bloqueado por: T19, T17, T13; também há bloqueio externo descrito no ticket.
   - Entrega: O dono observa o atendimento, habilita assistência e autoriza um piloto limitado com meios de interrompê-lo e auditar seus resultados.

21. **[T21 — Medir supervisor de qualidade sem alterar o atendimento](drafts/21-supervisor-observacao.md)**
   - Bloqueado por: T17.
   - Entrega: O dono compara a avaliação de qualidade com o resultado principal, medindo utilidade, custo e divergência sem mudar a resposta entregue.

22. **[T22 — Aplicar revisão seletiva com uma correção e revalidação](drafts/22-supervisor-seletivo.md)**
   - Bloqueado por: T21, T14; também há bloqueio externo descrito no ticket.
   - Entrega: Somente cenários configurados usam revisão ativa, com uma correção máxima e preservação das condições autorizadas.

## Fronteira e marcos

Na execução atual, os bloqueios internos foram atendidos nas fatias locais. A
independência lógica não autorizou agentes paralelos, deploy ou implantação; o
único bloqueio técnico externo mantido é T16, além das autorizações de uso
público descritas em T20 e T22.

| Marco | Resultado | Tickets |
|---|---|---|
| A | Silêncio, entrega revalidada, revogação e resposta pertinente | T01–T05, T14 |
| B | Skills acessíveis, checkpoint, diff e promoção | T06–T09 |
| C | Memória, turnos, respostas completas e perfis avaliados | T10–T13, T17 |
| D | Importação governada e Farol real comprovado | T15–T16 |
| E | Entrada, entrega e transferência no canal | T18–T19 |
| F | Modos graduais, interrupção e métricas | T20 |
| G | Supervisor medido e revisão seletiva | T21–T22 |

Os marcos não acrescentam bloqueios ocultos. T20 pode usar backend local validado: T16 só o bloqueia se Farol for escolhido para o piloto. O supervisor não bloqueia o primeiro piloto.

## Dependências externas

- T16: versão estável do Farol publicada pelo dono e seu contrato executável.
- Provas reais de modelo/canal: ambiente e credenciais apropriados, tratados por referências externas. Fixtures de contrato não são prova de integração real.
- T20: autorização específica de ativação pública, coorte e limites operacionais definidos.
- T22: evidência de benefício do supervisor e configuração explícita para ativação.
- Publicação: tracker configurado e confirmação das seams/divisão.

## Tamanho e prefatoração

Cada ticket entrega uma trajetória através das camadas necessárias; não abrir tickets horizontais de banco, prompt ou testes. Critérios TDD representam ciclos sucessivos, não uma bateria antecipada.

Não foi identificada prefatoração ampla obrigatória. T02 introduz entrega revalidada já demonstrável; T06 introduz catálogo já utilizável. Se surgir migração incompatível ampla, propor expand–contract e revisar bloqueios antes de ampliar escopo.

Se uma fatia não couber em um contexto novo, dividi-la por comportamento independente, preservando demonstração e estado consistente, nunca apenas por camada.

## Publicação após revisão

Não foi encontrada configuração de tracker ou vocabulário de triagem no
projeto. Os drafts não escolhem tracker por inferência do remote Git. A
publicação continua uma atividade separada: quando houver destino configurado,
usar o fluxo de triagem acordado, preservar as dependências e publicar os
critérios sem converter a evidência local em aprovação externa.

## Revisão solicitada

S1/S2/S3 foram exercitadas. A revisão atual deve avaliar a evidência marcada
nos 22 drafts, manter T16 bloqueado e decidir separadamente sobre a ativação
pública de T20/T22. Não há nova entrevista de produto neste registro.

## Evidência de origem

- sales-agent: 30b9cf96d4dcf3edaf7af901a71f79eb2a1d92c1.
- Análise anterior: 74 testes e 38 cenários aprovados, além das quatro lacunas reproduzidas.
- chatwoot-ai: 783f41927c7fe1652d6bf78933c51bdde31ab751, inspeção de código e testes.
- Farol público observado: 2ff00fcfc581147ba9367b6a2a84dc1b1d6cbab5, distinto da versão estável futura.
- Nesta execução: 172 testes passaram em Python 3.9 e 3.12; avaliação local executou 38/38 cenários; `ruff check .`, `git diff --check`, `python -m build` e `twine check dist/*` passaram. A wheel foi instalada fora do checkout e executou `skills doctor`, `doctor` e avaliação. O relatório registra modelo remoto, Farol upstream e Chatwoot como `not-executed`; `run.source.dirty=true` é esperado porque não foi criado commit.
