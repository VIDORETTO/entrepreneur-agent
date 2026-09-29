# Skills distribuídas

Estas skills são pacotes próprios, pequenos e carregados seletivamente. Corey e
Matt são referências externas fixadas em `manifest.json`; seus controladores não
são copiados para o atendimento. A entrevista do dono e a conversa com o
comprador são fluxos diferentes.

| Skill | Uso | Não usar |
|---|---|---|
| `sales-setup` | diagnóstico, instalação e capacidades | como roteiro de comprador |
| `sales-business-discovery` | checkpoint e decisões do dono | para repetir toda a entrevista |
| `sales-knowledge-preparation` | fontes, versões, revogação e Farol | para estoque/pagamento em tempo real |
| `seller-conversation` | política de pergunta, espera e avanço | como autorização de cobrança |
| `sales-simulate` | casos e demonstrações reproduzíveis | como prova de conversão real |

## Skills de adaptação (para o agente de código)

Guiam Claude Code, Codex ou outro agente que ajuda a pessoa a configurar e
ajustar o vendedor. Têm audiência `developer-adaptation`: nunca entram no
contexto do comprador e não concedem capacidade.

| Skill | Uso | Não usar |
|---|---|---|
| `seller-adapt` | entrada: orientar, classificar o pedido, regras | como autorização de efeito |
| `seller-tune-conversation` | ajustar a conversa pelo pacote versionado | para inventar preço ou política |
| `seller-evaluate-and-tune` | medir com dev, holdout reservado e repetição | para ajustar olhando o holdout |
| `seller-connect-channel` | Chatwoot, assinatura, serviço, janela 24 h | para registrar webhook em produção sem decisão |
| `seller-pilot-readiness` | portão, modos, LGPD, interrupção | para forjar evidência |
| `seller-extend-runtime` | mudar o código com TDD | quando o pacote resolve |

Instale-as no projeto com `vendedor skills install --target claude|codex|all`
(cria também `AGENTS.md`; `CLAUDE.md` importa o `AGENTS.md`).
