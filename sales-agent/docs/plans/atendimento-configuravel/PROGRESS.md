# Registro de execução — atendimento configurável

Atualizado em 20/09/2026.

## Baseline

- Planejamento, especificação, ADR, contexto e 22 tickets lidos.
- Seams aprovadas pelo pedido: S1 (`SellerEngine.handle`), S2 (CLI) e S3
  (HTTP/contrato de canal).
- `python3 -m pip install -e .`: concluído.
- `python -m pip install -e ".[dev]"`: concluído.
- `python -m pytest -q`: 172 aprovados.
- `vendedor doctor`: aprovado; SQLite íntegro, sem Farol upstream instalado.
- `vendedor demo`: concluído com os quatro negócios fictícios.
- `vendedor evaluate --output reports/evaluation-latest.json`: 38/38 aprovados;
  backend local persistente e simuladores, Farol upstream e modelo remoto
  `not-executed`.
- Wheel e sdist reconstruídos; `twine check` passou. Instalação isolada do
  wheel confirmou `vendedor skills doctor`, referências instaladas,
  `vendedor doctor` e avaliação 38/38 fora do checkout.
- Revisões de fonte agora são imutáveis por `source_version`; supervisor ignora
  correções que chegam após timeout ou mudança de estado.
- Catálogo de skills, configuração por checkpoint, turnos, contrato Chatwoot,
  modos graduais e supervisor seletivo foram verificados pelas interfaces
  públicas; a entrada/saída externa continua classificada como contrato local.
- `ruff check src tests` e `git diff --check`: aprovados.

### Revalidação desta continuação

- `python -m pytest -q`: 172 aprovados, incluindo fingerprint de pacote com
  versão reutilizada, reservas de piloto persistentes após restart, custo
  fracionário, resultado desconhecido, liquidação idempotente e expiração.
- `python3.12 -m pytest -q`: 172 aprovados; Python 3.12 está disponível no
  ambiente e passou o mesmo conjunto.
- `ruff check src tests`, `python -m compileall -q src tests` e `git diff
  --check`: aprovados após a revisão do supervisor.
- `python3 -m pip install -e .`, `python -m pip install -e ".[dev]"`,
  `vendedor doctor`, `vendedor demo`, `vendedor evaluate`, `python -m build` e
  `twine check dist/*`: aprovados; o wheel também foi instalado e executado
  fora do checkout com Python 3.9.
- `vendedor model-check` com `rules-v1` e com o adaptador adversarial,
  `ruff check .` e nova avaliação após a construção: aprovados; o relatório
  atual registra `source.dirty=true` porque esta execução não cria commit.
- Testes Farol locais de geração, fuso, substituição e reimportação legacy:
  aprovados, incluindo promoção bloqueada para `pending_review`, intervalo
  inválido e duas revisões ativas no mesmo escopo; o cliente/contrato Farol
  estável continua não resolvido.

### Correções residuais da revisão

- Reservas genéricas agora expõem expiração de lease como estado estruturado;
  uma proposta expirada vai para `unknown` e uma proposta ainda em andamento
  permanece pendente, sem ser anunciada como preparada.
- O transporte HTTP Chatwoot usa redirecionamento somente na mesma origem
  (esquema, host e porta), impedindo downgrade HTTPS ou encaminhamento do
  token para outro destino antes de uma nova requisição.
- A entrada Chatwoot marca a identidade externa somente depois do registro do
  evento autenticado; o motor confere esse ledger antes de aceitar a identidade
  para o checkout simulado. `verified:*` continua exclusivo do simulador.
- Atualizações/restaurações de pacote desativam fontes declaradas removidas,
  preservando as linhas históricas e as revogações de governança.

## Estado dos tickets

| Ticket | Estado | Evidência atual | Próximo trabalho |
|---|---|---|---|
| T01 | concluído local | takeover/recusa silenciam e cancelam entregas elegíveis | integração de canal permanece externa |
| T02 | concluído local | lease com identidade, recuperação para `unknown` quando o resultado é ambíguo e `DeliveryProcessor` público | provedor real não executado |
| T03 | concluído local | revogação persistente sobrevive reimportação/restart; fontes removidas de snapshot ficam inativas sem apagar histórico | — |
| T04 | concluído local | escopo, público, vigência, revisão ativa, promoção explícita e `pending_review` para dados antigos | — |
| T05 | concluído local | filtro por tópico, cobertura parcial e conflito material | — |
| T06 | concluído local | catálogo instalado, referências e diagnóstico | — |
| T07 | concluído local | checkpoint persistente, decisões confirmadas/inferidas e impedimentos | — |
| T08 | concluído local | inspeção, diff redigido, simulação isolada, promoção e restauração | — |
| T09 | concluído local | seleção de skill de comprador e trace declarado/selecionado/aplicado | — |
| T10 | concluído local | memória estruturada, fatos e histórico de correções | — |
| T11 | concluído local | debounce durável, agrupamento por lacuna e urgência | — |
| T12 | concluído local | respostas cobrem fatos conhecidos e nomeiam lacunas | — |
| T13 | concluído local | perfis, objeções com condições aprovadas e preferências configuradas sem efeito comercial automático | — |
| T14 | concluído local | evidência no outbox e revalidação antes do envio | — |
| T15 | concluído local | manifesto, hash, geração, revogações, limites, promoção atômica, datas UTC e diagnóstico de legado | contrato upstream estável pertence ao T16 |
| T16 | bloqueado externamente | `StableFarolAdapter` reporta bloqueio/incompatibilidade sem fallback silencioso | versão estável/cliente executável não disponíveis |
| T17 | concluído local | golden set sintético e relatório reproduzível com limiares | modelo remoto não executado |
| T18 | concluído por contrato local | HMAC, mapeamento, ACK após persistência, replay, identidade externa autenticada e separação de eventos | webhook de produção não executado |
| T19 | concluído por contrato local | mensagens públicas, notas privadas, transferência, confirmação separada, resultado desconhecido e redirecionamento same-origin | Chatwoot real não executado |
| T20 | concluído local | observação/assistência/piloto, coorte, limites, interrupção, métricas e plano operacional | ativação pública exige autorização externa |
| T21 | concluído local | supervisor desligado/observável, quatro dimensões determinísticas, persistência, timeout e comparação sem alterar resposta | juiz externo não executado |
| T22 | concluído local com bloqueio de adoção | política opcional/obrigatória, uma correção seletiva vinculada ao candidato original, comparação com denominador comum e revalidação | critérios de ativação pública ainda externos |

## Bloqueios registrados

- T16 depende da publicação da versão estável do Farol e de seu contrato
  executável. O HEAD público citado no planejamento não será tratado como essa
  versão.
- Provas reais de modelo e Chatwoot dependem de ambiente/credenciais externos;
  fixtures e servidores falsos serão classificados como contrato local.
- T20 e T22 têm partes de ativação pública que exigem autorização e critérios
  operacionais do dono. O controle local e a política de supervisor estão
  implementados e testados.
- Não há tracker configurado. A publicação dos tickets fica separada e não
  impede a implementação local.

## Convenções de evidência

Cada fatia deve ter teste na seam aprovada, red observado, green e regressão
pertinente. SQLite temporário real será usado nos testes; doubles ficam nas
fronteiras externas, tempo e aleatoriedade. Nenhum deploy, envio público,
cobrança ou alteração externa faz parte desta execução.
