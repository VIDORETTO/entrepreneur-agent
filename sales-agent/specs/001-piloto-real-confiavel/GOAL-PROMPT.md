# Goal: implementar o esforço 001-piloto-real-confiavel

Você vai implementar, de forma autônoma e até o fim, o esforço `001-piloto-real-confiavel` do projeto **Vendedor Adaptável**, em `/root/saas/entrepreneur-agent/sales-agent`. O trabalho segue o **hybrid-spec-kit**, já instalado no projeto (`.hybrid/hybrid.py` e skills em `.agents/skills/hybrid-*`).

## Objetivo final (condição de término)

Os 15 tickets `TK-001` a `TK-015` em `specs/001-piloto-real-confiavel/tickets/` estão `done`, e os 48 critérios AC-001 a AC-048 têm evidência executada `passed`. A exceção é o que depende de credencial real: isso fica como `not_run` com a limitação escrita. Além disso:
- `python -m pytest -q` passa por inteiro;
- `ruff check src tests` passa;
- `vendedor doctor` e `vendedor evaluate --split dev` rodam;
- `hybrid.py check --mode convergence` não aponta AC sem evidência nem ticket `done` sem gate.

## Leia antes de qualquer código (nesta ordem)

1. `AGENTS.md`, `CONTEXT.md`, `docs/adr/0001-runtime-local-portable.md`.
2. `specs/001-piloto-real-confiavel/spec.md`: é o contrato, revisão 2, **aceito**. As decisões do dono estão em "Respostas do dono".
3. `specs/001-piloto-real-confiavel/plan.md`: é o desenho técnico, revisão 2, `ready`. A ordem serial de execução está no risco R5.
4. `specs/001-piloto-real-confiavel/tdd.md` e `research.md`.
5. `.agents/skills/hybrid-implement/SKILL.md`, `hybrid-verify`, `hybrid-review`, `hybrid-check` e `.hybrid/shared/references/*.md`.

## Decisões já tomadas (não reabra)

- **Modelo:** OpenAI. O perfil padrão é `openai` (Chat Completions com `response_format` `json_schema` e `strict: true`; trate `refusal`). O segundo perfil é `openai-compatible`. O nome do modelo vem de `SELLER_MODEL_NAME`, a chave de `env:OPENAI_API_KEY` e os preços da configuração. Nada disso vai fixo no código. Consulte a documentação atual da OpenAI sobre Structured Outputs antes do TK-008. Não use o SDK: o projeto não tem dependências de runtime, e o adaptador usa `urllib`.
- **Retenção LGPD:** padrão de 180 dias; o valor `0` desativa o expurgo.
- **Webhook do Chatwoot:** `signature_mode=timestamped` é o padrão, com HMAC-SHA256 sobre `"{X-Chatwoot-Timestamp}.{raw_body}"`, prefixo `sha256=` e tolerância de 300 s. `legacy-body` só existe como opção explícita por binding e bloqueia `pilot readiness`.
- **Python:** a versão mínima passa a ser 3.11 (TK-002). Use `python3.12` localmente: `python3.12 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`.

## Fluxo por ticket (repita até acabar)

1. Rode `python3.12 .hybrid/hybrid.py start --project . --effort 001-piloto-real-confiavel --json` e `graph ... --json`. Escolha o próximo ticket pela ordem do R5 no plan.md, respeitando `requires`.
2. Rode `hybrid.py package --project . --effort 001-piloto-real-confiavel --ticket TK-xxx --json`. Só comece se vier `ready: true`. Depois rode `ticket update --status in_progress`.
3. Faça TDD, um AC por vez, na seam indicada no plan.md:
   - escreva o teste e rode, confirmando que ele falha **pelo motivo previsto** no tdd.md (erro de import ou de fixture não conta como falha válida);
   - implemente o mínimo para passar;
   - rode os testes do arquivo e siga para o próximo AC.
   - Use SQLite temporário real. Use doubles só para relógio, servidor Chatwoot falso, servidor OpenAI falso, transcritor e aleatoriedade. Não prove comportamento consultando tabelas diretamente.
4. Rode a regressão completa (`python -m pytest -q`, `ruff check src tests`) e atualize a documentação da interface alterada (README, docs/OPERATIONS.md, docs/CONFIGURATION.md, docs/EVALUATION.md, schema do pacote).
5. Registre a evidência para cada AC com `hybrid.py evidence add --ticket TK-xxx --acceptance-refs AC-... --procedure "<comando exato>" --result passed --executed --path <src> --path <tests> --observations "..."`. Depois rode `ticket update --status verified`.
6. Faça a revisão como uma passada separada, seguindo a skill `hybrid-review` nos dois eixos (Standards e Spec), sobre o diff do ticket. Salve o relatório em `specs/001-piloto-real-confiavel/findings/`.
   - Se houver um achado bloqueante, corrija e volte ao passo 4.
   - Se não houver, rode `ticket update --status done`.
7. Faça o commit na branch `feat/001-piloto-real-confiavel` (crie a partir de `main` no primeiro ticket). Use a mensagem `TK-xxx: <título>` e termine a mensagem com a linha de coautoria configurada no ambiente, se existir.
8. Rode `hybrid.py checkpoint write` com `--expected-revision` atual e `--next-action`, e depois `render --view all`.

## Regras invioláveis

- **Produção:** esta VPS tem serviços em produção (Chatwoot em `/root/saas/chatwoot`, `chatwoot-ai`, containers Docker). **Não** toque em `/root/saas/chatwoot`, `/root/saas/chatwoot-ai` (só leitura, apenas para comparar contrato), Docker, Nginx, systemd, webhooks, AgentBots ou `.env` de outros projetos. Todo teste de canal usa servidor falso local em porta efêmera.
- Não faça deploy, `git push`, envio real a compradores, chamada à API real da OpenAI sem `OPENAI_API_KEY` presente, nem registro de webhook. Se a chave existir no ambiente, uma execução real de `model-check`/`evaluate --split holdout` pode ser feita e registrada como evidência `real`. Nunca imprima a chave.
- A autoridade é sempre do motor (`SellerEngine`/`DeliveryProcessor`). O modelo, o redator, o transcritor e as skills nunca autorizam efeitos.
- Não mude a spec nem os ACs para acomodar uma implementação. Não renumere IDs. Não edite `todo.md`/`backlog.md` à mão: são gerados.
- Não enfraqueça nem apague testes existentes para passar. O teste Farol vencido deve passar por injeção de relógio (TK-001), não trocando a data.
- O holdout (`evaluation/holdout.json`) só é lido por `evaluate --split holdout`. Não ajuste prompts olhando o holdout.
- Nenhum segredo, telefone, e-mail ou CPF real em fixture, log ou relatório.

## Quando parar e devolver (em vez de inventar)

Siga a "Condição de retorno à planejadora" de cada ticket. Pare e reporte (ticket, passo, evidência, trabalho feito, decisão necessária, impacto) em três casos:
- surgiu uma decisão nova de comportamento, contrato público, modelo de dados ou autorização;
- um recurso obrigatório está indisponível e o ticket não pode ser concluído de forma honesta;
- uma ação exigiria tocar produção.

Credencial ausente **não** bloqueia: registre `not_run` e continue.

## Relatório final

Entregue uma tabela ticket → status → ACs → EV refs; os comandos executados com seus resultados; o que ficou `not_run` e por quê; os desvios do plano; o hash dos commits; e a próxima ação recomendada (ex.: executar o holdout com o modelo OpenAI real e rodar `vendedor pilot readiness`).
