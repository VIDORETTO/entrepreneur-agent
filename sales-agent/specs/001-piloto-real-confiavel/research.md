# Pesquisa e diagnóstico — 001-piloto-real-confiavel

Data: 28/09/2026. Baseline: `9abaf956eeaa8459fc237c185c14d4241529063e` (árvore limpa).
Este documento é insumo de `spec.md` e `plan.md`; não é contrato.

## 1. Espírito do projeto

O Vendedor Adaptável é um atendente comercial instalável e configurável em que
**o modelo interpreta e propõe, mas o motor decide e autoriza** (ADR 0001,
`plano-ia-de-vendas.md` §9). O princípio central é ajudar o comprador a concluir
uma decisão adequada com o menor atrito: responder ao que foi perguntado,
perguntar só o necessário, avançar direto quando o comprador está pronto,
transferir para uma pessoa quando pedido e nunca inventar preço, prazo,
desconto ou confirmação. Honestidade de evidência é regra: simulação, contrato
local e integração real nunca se confundem.

## 2. Onde paramos

| Marco do plano de produto | Estado observado |
|---|---|
| M0 contrato comercial | concluído (38 AC, 4 negócios fictícios) |
| M1 instalação e configuração retomável | concluído local |
| M2 vendedor simulado | concluído local |
| M3 Farol e pacote versionado | concluído local; Farol estável bloqueado externamente (T16) |
| M4 primeiro negócio real | **não iniciado**: nenhum canal, modelo ou checkout real executado |
| M5 piloto e distribuição | controles locais existem (T20–T22); nenhuma ativação |

O esforço anterior (`docs/plans/atendimento-configuravel`, T01–T22) foi
concluído localmente. O que falta é justamente a fronteira M3→M4: tornar o
sistema **executável, seguro e mensurável contra um canal e um modelo reais**.

Verificação desta análise (executada em 28/09/2026, Python 3.9.25):
`python3 -m pytest -q` → **171 passed, 1 failed**.

## 3. Achados no código

| ID | Achado | Evidência | Gravidade |
|---|---|---|---|
| A01 | Teste com data fixa venceu: vigência `2026-09-22` usada com relógio real; a suíte ficou vermelha sozinha. `utc_now()` é chamado diretamente em ~51 pontos. | `tests/test_knowledge_and_configuration.py::test_farol_manifest_normalizes_offset_dates_and_replaces_previous_generation`; `storage.py:29` | P0 |
| A02 | Assinatura Chatwoot calculada só sobre o corpo. O contrato publicado assina `"{timestamp}.{raw_body}"` com `X-Chatwoot-Timestamp`. Webhooks reais seriam rejeitados e não há janela anti-replay por tempo. | `channel.py` → `ChatwootReceiver._signature_matches`; docs Chatwoot; `chatwoot-ai/backend/app/api/routes/webhook.py` usa timestamp | P0 |
| A03 | Mensagem enviada pelo próprio sistema com token de usuário volta como webhook `sender.type=user` e é classificada `human_message` → pausa humana indevida (loop de eco). Não há correlação por ID do provedor. | `channel.py` → `ChatwootReceiver._event_kind`; issue chatwoot#15914 | P0 |
| A04 | `requires-python >=3.9`; Python 3.9 está fora de suporte desde out/2025 e o Farol upstream exige 3.11+. | `pyproject.toml`; CI matriz 3.9/3.12 | P1 |
| A05 | Não existe processo executável de serviço: receptor WSGI, processamento de turnos e worker de entrega com transporte real não são orquestrados; `outbox process` só usa provedor falso. | `cli.py` (sem `serve`); `ChatwootChannelService` | P1 |
| A06 | "Modelo" padrão é regex (`RuleBasedModel`). O `HTTPModelAdapter` envia tudo como uma mensagem `user` sem papel de sistema, sem saída estruturada nativa, sem reparo, sem registro de tokens/custo. | `model.py` | P1 |
| A07 | Resposta ao comprador é template determinístico; não há redação natural verificada. Verificador de alegações existe apenas no supervisor. | `conversation.py` → `_evidence_answer`, `governance.py` → `_commercial_claims` | P1 |
| A08 | Recuperação é sobreposição de tokens com varredura completa; sem BM25, sem normalização de acentos, sem métrica de recall. | `storage.py` → `search_sources` | P1 |
| A09 | Mensagens não textuais (áudio, imagem, documento) não têm tratamento: no Brasil, áudio no WhatsApp é comum. | `channel.py` (sem `attachments`) | P1 |
| A10 | Sem janela de 24 h do WhatsApp: respostas/follow-ups fora da janela seriam rejeitados pelo provedor ou violariam política. | ausência em `delivery.py`/`governance.py` | P1 |
| A11 | Avaliação tem 38 casos, todos de desenvolvimento; plano pede 80 (50 dev / 30 reservados) e repetição para adaptadores estocásticos. | `evaluation/golden_set.json`; plano §17 | P1 |
| A12 | Sem horário de atendimento humano, detecção de loop/frustração, exportação/eliminação por titular (LGPD) ou redação de PII em relatórios. | `CONTEXT.md`, `schemas/` | P1 |

## 4. O que usuários e o mercado relatam

- **Alucinação de preço/condição** é a falha mais citada em bots de vendas no
  WhatsApp; um agente de loja chegou a conceder descontos, brindes e indicar
  contas inexistentes para pagamento. → reforça A06/A07: texto do modelo precisa
  de verificação determinística de números e links.
  [DEV Community](https://dev.to/instant/your-whatsapp-ai-chatbot-is-lying-to-your-customers-heres-why-384n),
  [AI Runs the Store](https://aicentral.substack.com/p/ai-runs-the-store)
- **Injeção de prompt**: o caso Chevrolet ("Tahoe por US$ 1, legalmente
  vinculante") e a responsabilização da Air Canada por política inventada pelo
  chatbot. OWASP LLM01. → casos adversariais obrigatórios e proibição de
  "acordo" textual fora de capacidade.
  [vectara/awesome-agent-failures](https://github.com/vectara/awesome-agent-failures/blob/main/docs/case-studies/chevrolet-dealership-chatbot.md),
  [CX Today](https://www.cxtoday.com/contact-center/3-times-customer-chatbots-went-rogue-and-the-lessons-we-need-to-learn/)
- **Mensagens picadas** geram várias respostas; a comunidade n8n resolve com
  buffer/debounce em Redis. → já coberto por T11; precisa rodar no serviço real.
  [n8n community](https://community.n8n.io/t/whatsapp-debounce-flow-combine-multiple-rapid-messages-into-one-ai-response-using-redis-n8n/225494)
- **Chatwoot**: loop de eco quando a integração reage às próprias alterações
  (≈15 inversões em 17 s, três mensagens duplicadas ao cliente); resposta de bot
  duplicada quando o claim expira no meio do POST; divergência entre segredo
  exposto e chave usada na assinatura.
  [chatwoot#15914](https://github.com/chatwoot/chatwoot/issues/15914),
  [fazer-ai/agents#499](https://github.com/fazer-ai/agents/issues/499),
  [chatwoot#13809](https://github.com/chatwoot/chatwoot/issues/13809),
  [Chatwoot webhooks](https://developers.chatwoot.com/api-reference/webhooks/add-a-webhook)
- **Preferência por humano**: 85% preferem falar com pessoa; só 7% dizem
  raramente repetir informação. → acesso humano garantido e sem requalificação.
  [SurveyMonkey](https://www.surveymonkey.com/curiosity/customer-service-statistics/),
  [CX Dive](https://www.customerexperiencedive.com/news/customers-dislike-ai-customer-service/757711/)
- **Brasil — regulação**: Decreto 11.034/2022 (SAC) garante acesso a atendente
  humano; diretrizes Senacon vedam encerrar sessão automatizada sem conclusão ou
  transferência; LGPD exige canal para direitos do titular.
  [Conjur](https://conjur.com.br/2024-dez-23/novo-sac-obriga-atendimento-humano-e-ataca-problemas-recorrentes-na-justica/),
  [Mercado & Consumo](https://mercadoeconsumo.com.br/22/04/2026/artigos/seu-atendimento-foi-feito-por-uma-maquina-e-seus-direitos-ignorados/)
- **WhatsApp Business**: desde 15/01/2026 a Meta proíbe chatbots de propósito
  geral na API; bots de negócio (vendas, suporte) continuam permitidos. Janela
  de 24 h para mensagem livre; fora dela só templates. O Brasil foi excluído da
  proibição por ordem do CADE, mas o escopo "assistente de negócio" continua
  sendo a postura segura.
  [respond.io](https://respond.io/blog/whatsapp-general-purpose-chatbots-ban),
  [TechCrunch](https://techcrunch.com/2026/01/15/after-italy-whatsapp-excludes-brazil-from-rival-chatbot-ban)
- **Confiabilidade de agentes**: τ-bench mostra que sucesso médio > 60% cai
  para < 25% em pass^8; avaliar uma execução só esconde inconsistência.
  [τ-bench](https://arxiv.org/abs/2406.12045),
  [Sierra](https://sierra.ai/blog/tau-bench-shaping-development-evaluation-agents)
- **Recuperação local**: SQLite FTS5 com BM25 (stdlib) é suficiente para
  corpus pequeno e combinável depois com vetores via RRF.
  [DEV — hybrid RAG em SQLite](https://dev.to/soytuber/building-a-hybrid-rag-in-200-lines-sqlite-fts5-sqlite-vec-rrf-38h1)

## 5. Conclusão para o próximo esforço

Não é hora de nova capacidade comercial nem de infraestrutura nova. O maior
valor é fechar a lacuna **M3 → M4** com o menor escopo possível:

1. Consertar o que já está quebrado ou quebraria no primeiro webhook real (A01–A03).
2. Tornar o serviço executável e compatível com o canal (A05, A09, A10).
3. Trocar regex por modelo real sem perder a regra de ouro (A06–A08).
4. Provar com avaliação honesta e reservada antes de liberar piloto (A11).
5. Garantir humano e privacidade exigidos no Brasil (A12).

Checkout/Pix real, Farol estável, embeddings e múltiplos canais ficam no
`roadmap.md` como candidatos.
