# Pesquisa para o Vendedor Adaptável

**Consulta:** 17/09/2026. **Objetivo:** encontrar componentes reaproveitáveis e falhas reais que possam virar requisitos. Esta pesquisa apoia o planejamento; não é benchmark de conversão nem auditoria completa dos projetos.

**Atualização de seleção:** na revisão 3 do plano, Corey é a fonte comercial direta e Matt é a fonte direta de entrevista. Sales-Skills foi retirado da seleção; R03 preserva apenas o histórico da investigação. R04 e R06 não são dependências do pacote inicial. Não foi realizada auditoria de parentesco/autoria entre repositórios.

## 1. Como interpretar a evidência

Foram consultados repositórios, publicações de fornecedores que constroem agentes, discussões no Reddit e tópicos no fórum n8n. Os repositórios selecionados foram inspecionados localmente em revisões identificadas. Não foram instalados no harness nem executados como vendedores.

Distinguimos: **artefato verificável** (código/instruções existentes), **relato de implementação** (autor descreve sua experiência), **sugestão de participante** (solução proposta sem reprodução) e **publicação de fornecedor** (fonte primária sobre seu próprio produto, com interesse comercial). Um relato detalhado pode revelar um caso de teste útil sem provar a eficácia da solução sugerida.

A amostra é intencional, concentrada em problemas de conversa, operação e configuração. Não representa todo o mercado. As datas relativas de algumas páginas variaram entre resultados e página aberta; nesses casos registramos a data de consulta e não inferimos uma data exata. Métricas promocionais não foram incorporadas como metas ou promessas do nosso produto.

Context7 e o MCP de conhecimento local não estavam disponíveis. Foram usados código público e páginas acessíveis. Uma página de Marauder Labs apareceu na busca, mas seu conteúdo completo não foi recuperado de modo suficiente; ela não fundamenta as conclusões abaixo.

## 2. Experiências e problemas observados

### E01 — Loja de roupas: reiniciar a descoberta durante o pedido

**Fonte:** [relato de construção de um agente de WhatsApp para loja familiar](https://www.reddit.com/r/n8n/comments/1s3hejk/i_spent_2_months_building_a_whatsapp_ai_sales/). Tipo: relato do autor, Reddit; publicado em março de 2026 segundo o resultado indexado.

O autor descreve falta de memória, perguntas antecipadas de cadastro e roteamento inadequado de clientes que já estavam comprando. Passou a guardar status e separar o atendimento inicial do registro de pedido. Nos comentários, também identifica atualização de estoque como dificuldade do negócio. Não apresenta demonstração independente de aumento de vendas.

**Decisão nossa:** manter fatos estruturados e permitir entrada direta na compra. Uma alteração de assunto não reinicia a jornada. A responsabilidade por atualizar catálogo/estoque precisa ser definida na configuração.

**Teste derivado:** cliente retorna no dia seguinte com “quero fechar aquele azul”; recuperar o item de forma segura ou esclarecer qual item, sem repetir nome, necessidade e orçamento.

### E02 — Loja de pneus: duas autoridades sobre o estado

**Fonte:** [agente central, ferramentas e máquina de estados](https://www.reddit.com/r/n8n/comments/1vfh681/built_a_whatsapp_sales_agent_in_n8n_central_ai/). Tipo: relato técnico, Reddit.

O autor mantém estado no banco, mas deixa o modelo escolher livremente o próximo passo. Relata inconsistências, mudanças de preço condicionado à quantidade e dificuldade quando o cliente troca o meio de pagamento. Também descreve um protótipo de cadeia de agentes mais previsível, porém mais caro e lento. Isso é experiência declarada, não comparação controlada.

**Decisão nossa:** uma autoridade de estado e transições. O modelo interpreta e propõe; o motor valida. Quantidade, oferta ou pagamento alterados invalidam a cotação correspondente. Não adotar uma cadeia fixa de agentes por mensagem.

**Teste derivado:** depois de cotar quatro itens no Pix, mudar para dois parcelados; recalcular antes de enviar resumo ou confirmação.

### E03 — Pagamento: uma instrução no prompt não garantiu pré-requisito

**Fonte:** [relato de perda de vendas após o agente pular consulta ao banco](https://www.reddit.com/r/n8n/comments/1t1yxmp/i_lost_a_client_2_sales_because_my_ai_agent/). Tipo: relato com divulgação de componente próprio.

O autor diz que o agente às vezes omitia a consulta do cliente antes de criar um link e utilizava uma identificação inventada. Descreve tentativas de corrigir somente o prompt e propõe restringir a sequência de ferramentas. As perdas e frequências informadas não foram auditadas.

**Decisão nossa:** tornar os pré-requisitos de checkout verificáveis em código. O conector pode executar toda a sequência interna sem delegar cada passo ao modelo. Não dependemos do plugin promovido pelo autor.

**Teste derivado:** uma chamada para criar checkout com identificação ausente ou não verificada é rejeitada; a IA não envia um link fabricado.

### E04 — Encerramento: o agente continua falando

**Fonte:** [como parar o chatbot depois de uma condição](https://www.reddit.com/r/n8n/comments/1wd8gpf/how_to_stop_chatbot_from_replying_after_certain/). Tipo: pergunta e sugestões de comunidade.

A discussão contrapõe depender de uma palavra de encerramento produzida pelo modelo e verificar campos/status persistidos. Participantes levantam eventos duplicados, corrida entre leitura e gravação e preenchimento inválido de campos. Não há validação única de todas as soluções sugeridas.

**Decisão nossa:** conclusão é transição persistida, com emissão deduplicada da mensagem final. Estado encerrado não significa banir futuras solicitações: “obrigado” não reabre a venda; “quero comprar outro” pode iniciar nova oportunidade.

**Teste derivado:** dois eventos simultâneos completam o pedido uma única vez; uma nova compra posterior continua possível.

### E05 — Histórico existente, continuidade insuficiente

**Fonte:** [fluxo conversacional de múltiplos turnos no fórum n8n](https://community.n8n.io/t/help-request-ai-agent-in-n8n-how-to-achieve-a-fully-conversational-multi-turn-flow/96818). Tipo: pergunta de implementação e propostas; tópico iniciado em 04/04/2025.

O autor já possuía memória e consulta de produtos, mas relatava turnos desconectados. Outro participante descreve um agente que despeja todas as perguntas de uma vez. As sugestões incluem rastrear campos e estado fora da conversa.

**Decisão nossa:** separar histórico, dados confirmados e pendências da próxima ação. Não adotamos a sugestão de coletar sempre todos os campos em uma ordem rígida: isso contrariaria o cliente que já sabe o que quer.

**Teste derivado:** uma mensagem que informa produto, quantidade e cidade preenche os três campos; a próxima pergunta trata apenas do dado indispensável ausente.

### E06 — Identidade de sessão incorreta faz o agente esquecer

**Fonte:** [Chatbot CANT access Chat Memory History](https://community.n8n.io/t/chatbot-cant-access-chat-memory-history/70699). Tipo: problema de implementação e discussão, iniciado em 15/01/2025.

O usuário relata que cada mensagem de WhatsApp inicia uma conversa sem contexto. A discussão se concentra na identificação da sessão e em armazenar mensagens. Isso demonstra um problema concreto de integração, não prova que uma memória ilimitada seria a solução.

**Decisão nossa:** identidade composta por negócio, canal, contato e oportunidade/conversa; histórico persistido e resumo seletivo. Não unir clientes entre canais somente por nome.

**Teste derivado:** dois negócios atendem o mesmo telefone sem compartilhar dados; o retorno do cliente ao mesmo negócio recupera o contexto pertinente.

### E07 — Webhooks duplicados produzem respostas duplicadas

**Fonte:** [discussão sobre chatbot de WhatsApp com base documental](https://www.reddit.com/r/n8n_ai_agents/comments/1rwuqmy/i_recently_built_a_whatsapp_ai_chatbot_using_n8n/). Tipo: publicação de projeto; o alerta relevante vem de um comentário de participante.

Um participante relata problemas com repetição de notificações e recomenda idempotência, além de memória recente separada da recuperação documental. O tópico também contém divulgação e pedidos de acesso; não foi tratado como validação do produto anunciado.

**Decisão nossa:** deduplicar entrada e efeitos de saída; distinguir mensagem do cliente de confirmação de entrega; revalidar a versão da conversa antes do envio.

**Teste derivado:** receber o mesmo evento duas vezes não duplica pergunta, checkout, reserva ou retorno agendado.

### E08 — Transferência perde contexto ou acontece tarde

**Fonte:** [discussão sobre passagem de agentes para representantes humanos](https://www.reddit.com/r/AI_Agents/comments/1wcxq0j/how_are_you_handling_ai_agent_handoffs_to_human/). Tipo: relatos e sugestões da comunidade.

Participantes descrevem resumo acompanhado do histórico completo, transferência após repetidas falhas e respeito ao pedido direto por humano. São práticas relatadas; não medimos seus resultados.

**Decisão nossa:** enviar objetivo, fatos confirmados, ações e pendência, com histórico acessível. Pausar o vendedor e retornos enquanto o humano assume. Um resumo da IA não substitui a evidência original.

**Teste derivado:** “já falei isso, quero uma pessoa” dispara encaminhamento sem outra rodada de qualificação.

### E09 — Operação posterior à demonstração

**Fonte:** [relato sobre limites da automação integral em recepcionistas](https://www.reddit.com/r/VoiceAutomationAI/comments/1tz5l2p/ive_built_ai_receptionists_for_dozens_of/). Tipo: experiência declarada de prestador, com contexto comercial.

O autor descreve diferenças entre demandas rotineiras e situações complexas, loops de esclarecimento e problemas que aparecem depois do início da operação. O caso é principalmente de voz; não transferimos conclusões sobre latência de áudio para texto.

**Decisão nossa:** definir responsável por catálogo, exceções e revisão contínua. Uma demonstração bem-sucedida não encerra a avaliação.

**Teste derivado:** mudança de horário e indisponibilidade do responsável alteram a resposta e o encaminhamento sem inventar atendimento imediato.

### E10 — Email não deve herdar cegamente o estilo do chat

**Fonte:** [Intercom: como construíram Fin por email](https://www.intercom.com/blog/fin-over-email-how-we-built/), 17/10/2024. Tipo: relato técnico do fornecedor sobre seu próprio produto.

A equipe descreve diferenças de formato, múltiplas perguntas na mesma mensagem, assinaturas irrelevantes e emails automáticos. Também relata desenvolvimento gradual com feedback. As métricas comerciais da publicação não foram adotadas.

**Decisão nossa:** concisão é proporcional à tarefa e ao canal. No chat, mensagens breves; numa solicitação B2B de proposta, responder todos os pontos necessários. Não impor universalmente uma pergunta e duas frases a qualquer interação.

**Teste derivado:** email com três perguntas recebe cobertura das três, sem três respostas separadas nem texto de chat fragmentado.

### E11 — Separação entre fluxo controlado e autonomia

**Fonte:** [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents), 19/12/2024. Tipo: orientação técnica de fornecedor com experiências de implementação. O próprio artigo sinaliza evolução posterior das ferramentas.

O texto diferencia fluxos definidos em código de decisões autônomas do modelo e recomenda começar com composições simples. Usamos esse princípio arquitetural, não exemplos antigos de APIs como documentação atual.

**Decisão nossa:** linguagem flexível sobre regras comerciais explícitas, um motor e conectores pequenos. Adicionar agentes ou camadas somente quando uma avaliação mostrar benefício.

**Teste derivado:** a mesma política impede ação inválida independentemente da redação escolhida pelo modelo.

### E12 — Produto comercial comparável, sem assumir os seus resultados

**Fonte:** [Intercom: anúncio de Fin for Sales](https://www.intercom.com/blog/announcing-fin-for-sales/), 22/04/2026. Tipo: anúncio comercial do fornecedor.

O anúncio organiza o atendimento em playbook, conhecimento, qualificação, encaminhamento e próximos passos, incluindo caminhos de autoatendimento e vendas assistidas. Isso é referência de desenho de produto; percentuais de conversão anunciados não são evidência da eficácia da nossa proposta.

**Decisão nossa:** a saída depende da oferta: compra direta, teste, proposta, reunião ou humano. Reunião não deve ser a meta universal de B2B; compra não exige humano automaticamente.

**Teste derivado:** uma empresa comprando uma assinatura simples segue para checkout; uma pessoa física contratando projeto complexo segue para escopo/orçamento.

## 3. Repositórios: decisão de aproveitamento

### R01 — VIDORETTO/dev-skills / hybrid-spec-kit

**Revisão:** `2b5f7ceea081e5abed0bcc2f5a618861e3e063d7`. Inspecionados README, `hybrid-start`, `hybrid-discover`, `hybrid-specify`, contrato operacional, template de descoberta, fontes e trechos do runner.

Na revisão consultada há dez skills `hybrid-*`; não há arquivos com os nomes `grill-me` ou `grill-me-with-docs`. O equivalente de descoberta é [hybrid-discover](https://github.com/VIDORETTO/dev-skills/blob/2b5f7ceea081e5abed0bcc2f5a618861e3e063d7/hybrid-spec-kit/skills/hybrid-discover/SKILL.md). A [proveniência](https://github.com/VIDORETTO/dev-skills/blob/2b5f7ceea081e5abed0bcc2f5a618861e3e063d7/hybrid-spec-kit/docs/sources.md) declara adaptação de contribuições de Matt e Spec Kit.

**Aproveitar:** perguntas por impacto e incerteza, fatos obtidos dos materiais, decisões persistidas, retomada e critérios observáveis. **Adaptar:** atores e saídas de desenvolvimento para negócio, oferta e política comercial. O proprietário não precisa criar ADR para cada preferência de tom.

**Distribuição:** o README do repositório informa ausência de arquivo de licença. Como é projeto do usuário, definir o licenciamento da distribuição e preservar a proveniência de componentes derivados; isso não impede esta fase de planejamento.

### R02 — mattpocock/skills

**Revisão:** `74ca5fe077456a0b3b2f5310cf9430999fd0b5fd`. Licença MIT presente. Inspecionadas as três skills de entrevista.

[grill-me](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/productivity/grill-me/SKILL.md) encaminha para `grilling`; [grill-with-docs](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/engineering/grill-with-docs/SKILL.md) encaminha também para `domain-modeling`. O nome encontrado é `grill-with-docs`. A versão atual de [grilling](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/productivity/grilling/SKILL.md) trabalha em rodadas de decisões dependentes, não necessariamente uma pergunta por rodada.

**Aproveitar:** árvore de decisões e recomendações justificadas. **Adaptar:** rodadas curtas, opção de pausar, ponto de conclusão por capacidade e persistência de decisões comerciais. Remover dependência de uma ferramenta literalmente chamada `Skill` e de subagentes obrigatórios para permitir outros harnesses.

### R03 — louisblythe/Sales-Skills

**Revisão:** `e0f13a6eb41be22fa1f8493b148077cdd6c6654a`. É o catálogo inspecionado com correspondência mais direta aos problemas do atendimento solicitados. O [README declara MIT](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/README.md#license); não foi localizado arquivo de licença na árvore rastreada. Resolver a atribuição/licença antes de redistribuir trechos. As instruções e os pseudocódigos não equivalem a um runtime pronto.

**Aproveitamento seletivo proposto:**

- [conversational-flow-management](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/skills/conversational-flow-management/SKILL.md): referência para fluxo; substituir a passagem obrigatória de saudação para descoberta por transições orientadas ao pedido do cliente.
- [response-length-calibration](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/skills/response-length-calibration/SKILL.md): calibrar tamanho; retirar fragmentação artificial em várias mensagens e corte de texto que possa perder condição comercial.
- [intent-detection](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/skills/intent-detection/SKILL.md): múltiplas intenções e sinais; intenção não concede autorização para cobrança nem serve de probabilidade calibrada.
- [closing](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/skills/closing/SKILL.md): reconhecer decisão de compra; remover fechamento presumido e exigência de novo compromisso ao final de toda resposta.
- [question-disambiguation](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/skills/question-disambiguation/SKILL.md): esclarecer apenas ambiguidades materiais; não transformar preço publicado em pergunta nem investigar autoridade em toda compra.
- [out-of-scope-request-handling](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/skills/out-of-scope-request-handling/SKILL.md): redirecionamento curto; não tratar comparação pertinente como assunto proibido nem retomar venda durante uma reclamação.
- [multi-turn-context-retention](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/skills/multi-turn-context-retention/SKILL.md): memória por camadas; condições comerciais antigas não continuam válidas por estarem no resumo.
- [warm-transfer-execution](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/skills/warm-transfer-execution/SKILL.md) e [handoff-detection](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/skills/handoff-detection/SKILL.md): transferir com contexto; separar pedido por humano de compra pronta que o sistema consegue concluir.
- [prospect-fatigue-detection](https://github.com/louisblythe/Sales-Skills/blob/e0f13a6eb41be22fa1f8493b148077cdd6c6654a/skills/prospect-fatigue-detection/SKILL.md): sinais explícitos de interrupção; não presumir permissão de contato em outro canal.

**Decisão atual:** excluído da seleção de componentes. A lista acima registra somente o que foi inspecionado; não é uma lista de instalação ou adaptação. Os requisitos próprios de conversa continuam no contrato comportamental, e a fonte comercial selecionada passa a ser Corey (R05).

### R04 — nthnclrk/enablement-skills

**Revisão:** `05e1ad4439fa02d70f9e35644817830ec71e1af8`. Licença MIT presente. Inspecionadas contexto e critérios de etapa, com referências indicadas.

[pipeline-stage-definition-and-exit-criteria](https://github.com/nthnclrk/enablement-skills/blob/05e1ad4439fa02d70f9e35644817830ec71e1af8/skills/pipeline-stage-definition-and-exit-criteria/SKILL.md) distingue atividades do vendedor e evidência de decisão do comprador. [revenue-enablement-context](https://github.com/nthnclrk/enablement-skills/blob/05e1ad4439fa02d70f9e35644817830ec71e1af8/skills/revenue-enablement-context/SKILL.md) organiza informações confirmadas, inferidas, conflitantes e ausentes.

**Decisão atual:** referência de pesquisa, sem dependência de instalação. Na seleção consolidada, product-marketing e revops do Corey apoiam contexto e critérios; os controles operacionais continuam próprios.

### R05 — coreyhaines31/marketingskills

**Revisão já inspecionada:** `5b2c0007766c6a1cf1d53fd8fc73e979e0821022`. Licença MIT presente.

[product-marketing](https://github.com/coreyhaines31/marketingskills/blob/5b2c0007766c6a1cf1d53fd8fc73e979e0821022/skills/product-marketing/SKILL.md) e [sales-enablement](https://github.com/coreyhaines31/marketingskills/blob/5b2c0007766c6a1cf1d53fd8fc73e979e0821022/skills/sales-enablement/SKILL.md) são úteis para preparar contexto e materiais.

**Decisão atual:** biblioteca comercial principal, obtida diretamente do Corey. Núcleo: product-marketing, sales-enablement, revops e copy-editing. Condicionais: customer-research, offers, competitors, pricing, emails, sms e churn-prevention. Seleção, aplicação e limites detalhados na seção 5 do plano, com caminhos verificados no snapshot. Não usar como controlador operacional; definir oferta/preço continua sendo decisão do dono.

### R06 — shaunmarsden/practical-ai-sales-workflows

**Revisão:** `859e50c5b8953e2dc182809e3208323d94b98179`. Licença MIT presente. Inspecionadas a skill de objeções e partes do registro de evidências.

[objection-response](https://github.com/shaunmarsden/practical-ai-sales-workflows/blob/859e50c5b8953e2dc182809e3208323d94b98179/.agents/skills/objection-response/SKILL.md) distingue uma objeção expressa de silêncio e pede resposta focada no problema. Ela é voltada a preparar trabalho para revisão humana, não executar vendas autônomas. Há exemplos e um [registro de avaliações e limites](https://github.com/shaunmarsden/practical-ai-sales-workflows/blob/859e50c5b8953e2dc182809e3208323d94b98179/EVIDENCE-STATUS.md).

**Decisão atual:** referência de pesquisa e avaliação, sem dependência de instalação. Preparar objeções com sales-enablement do Corey e aplicar nosso contrato de pergunta/espera. Os resultados publicados não são prova de eficácia no nosso domínio.

### R07 — filip-michalsky/SalesGPT

**Revisão:** `7cd1d4f9fae2a5610fac76e1c0edc38a2fafd388`, commit observado de 16/09/2024. Inspecionados estágios, prompts e metadados.

O projeto demonstra um vendedor consciente de etapas. Contudo, os [prompts consultados](https://github.com/filip-michalsky/SalesGPT/blob/7cd1d4f9fae2a5610fac76e1c0edc38a2fafd388/salesgpt/prompts.py) incluem abertura obrigatória e uma origem predeterminada para os contatos. Também há divergência entre MIT no [LICENSE](https://github.com/filip-michalsky/SalesGPT/blob/7cd1d4f9fae2a5610fac76e1c0edc38a2fafd388/LICENSE) e Apache-2.0 no [pyproject.toml](https://github.com/filip-michalsky/SalesGPT/blob/7cd1d4f9fae2a5610fac76e1c0edc38a2fafd388/pyproject.toml).

**Decisão:** referência histórica de separação de etapas; não usar como fundação do runtime nem copiar prompts/dependências. Não atribuir origem fictícia ao contato e não obrigar saudação antes de responder a um pedido concreto.

### R08 — VIDORETTO/farol-rag-skill-docs

**Revisão:** `81d5dcb2e189d00406cdd9b9e671d94e3f23cd58`. Inspecionados os contratos, geração, consulta de evidências e adaptadores. Como o usuário é o autor e autorizou sua adaptação no planejamento, não limitamos a proposta a um wrapper da interface atual.

Em [docops/generation.py](https://github.com/VIDORETTO/farol-rag-skill-docs/blob/81d5dcb2e189d00406cdd9b9e671d94e3f23cd58/docops/generation.py), `skill_artifacts` gera uma estrutura determinística e prevê enriquecimento externo. Em [docops/master.py](https://github.com/VIDORETTO/farol-rag-skill-docs/blob/81d5dcb2e189d00406cdd9b9e671d94e3f23cd58/docops/master.py), `query_project_evidence` pode usar `InMemoryRetrievalAdapter` por padrão e remove o conteúdo dos hits filtrados. [docops/retrieval.py](https://github.com/VIDORETTO/farol-rag-skill-docs/blob/81d5dcb2e189d00406cdd9b9e671d94e3f23cd58/docops/retrieval.py) distingue adaptadores em memória e MCP.

**Decisão:** aproveitar preparação, rastreabilidade e avaliação; acrescentar preset comercial, enriquecimento explícito e contrato de acesso a trechos autorizados. Exigir backend real no ambiente operacional, preservar separação entre documentos e fatos transacionais e avaliar invalidação de fontes. Essas observações descrevem o snapshot consultado; não são uma auditoria exaustiva nem demonstração de que um backend específico já está configurado.

## 4. Recomendação final de reaproveitamento

Não foi encontrado, entre os projetos inspecionados, um pacote que entregue ao mesmo tempo atendimento B2B/B2C adaptável, concisão verificável, instalação independente de harness e controle seguro das ações.

A combinação recomendada é: **Matt diretamente para entrevista e registro; Corey diretamente para contexto, playbook, critérios e revisão; Farol para conhecimento; Hybrid para apoiar o desenvolvimento do sistema quando necessário.** O controlador de estado, os contratos das ações e os testes de compra direta serão próprios.

Os exemplos aprovados, a seleção de referências e os scripts distribuídos devem funcionar juntos. Copiar somente o texto de uma skill perde dependências; copiar tudo aumenta contexto e conflitos. Cada adaptação terá origem, revisão, licença, diferenças documentadas e avaliação ligada à versão.

O formato [Agent Skills](https://agentskills.io/specification) admite `SKILL.md`, referências, scripts e assets. Isso sustenta a organização portátil, mas não padroniza sozinho execução contínua, credenciais ou equivalência entre modelos. Esses contratos pertencem ao nosso produto.

