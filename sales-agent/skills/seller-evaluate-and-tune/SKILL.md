---
name: seller-evaluate-and-tune
description: Medir e melhorar o vendedor com método (dev, holdout reservado, repetição pass^k, custo, recuperação de evidência) sem contaminar a avaliação. Use quando a pessoa pedir para "testar", comparar versões do pacote, escolher ou trocar de modelo, ou provar que uma mudança melhorou.
version: "1"
---

# Avaliar e ajustar

Uma mudança só "melhorou" se um comando repetível mostra isso. Este é o método.

## Os três conjuntos

| Conjunto | Comando | Para que serve |
|---|---|---|
| `contract` (38 cenários de contrato) | `vendedor evaluate` | invariantes do motor: pausa humana, revogação, idempotência, cotação, segurança |
| `dev` (50 casos com repetição) | `vendedor evaluate --split dev --repeat 4 --output reports/dev.json` | **o único que você usa para ajustar** |
| `holdout` (30 casos reservados) | `vendedor evaluate --split holdout --repeat 4 --output reports/holdout.json` | prova final, uma vez por versão candidata |

Código de saída 0 significa limiares atendidos (`evaluation/thresholds.json`: zero falha crítica, taxa mínima de aprovação e latência máxima); 2 significa que não. Leia o relatório, não só o código.

## Regras do holdout

- Não abra `evaluation/holdout.json` nem cole seus casos em conversa, prompt ou fonte. Só `evaluate --split holdout` o lê.
- Nunca ajuste pacote, prompt ou código para um caso do holdout. Se o holdout reprovar, descreva a **classe** do erro, escreva casos novos parecidos no `dev`, corrija pelo `dev` e registre que o holdout foi consultado: para afirmar qualidade de novo, o piloto precisa de uma execução limpa depois.
- Mudar o holdout muda o SHA-256 (`evaluation/holdout.sha256`); `--previous-report` compara com um relatório aprovado e marca `holdout_changed`.

## Métricas que importam

- `pass@1`: acertos entre todas as execuções. `pass^k`: casos que passaram em **todas** as `k` repetições (o que mede confiabilidade com modelo real). Compare os dois.
- `critical_failures` deve ser 0. Uma falha crítica vale mais que várias leves.
- `evaluation.retrieval.recall_at_5` e `evaluation.retrieval.abstention`: a busca encontra a fonte certa e se abstém quando não há resposta. Só medem a recuperação local, não o modelo remoto.
- Custo e latência (p95) por caso quando há modelo real. O adaptador local `rules-v1` não tem custo.

## Laço de melhoria

1. Rode `dev` com `--repeat 4` e guarde o relatório como base (`reports/dev-base.json`).
2. Escolha **uma** falha ou classe de falha; entenda a causa lendo o trace do caso.
3. Corrija no lugar certo: pacote (`seller-tune-conversation`), fonte (`sales-knowledge-preparation`) ou código com teste primeiro (`seller-extend-runtime`).
4. Rode `dev` de novo e compare com a base: o caso corrigido passa, nada que passava reprova, `pass^k` não cai.
5. Repita. Só chame o holdout quando o `dev` estiver estável.

## Seu negócio, não só os exemplos

Os casos `dev` e `holdout` cobrem os quatro negócios fictícios do produto. Para o seu pacote:

- `vendedor evaluate --split dev --package package.json --business-id ID` valida a instalação do pacote e o caminho mínimo de resposta dele (sondagem) e aparece no relatório em `candidate`; não substitui casos próprios.
- Para regressão do seu negócio, guarde as conversas que importam como testes no seu projeto (`seller-extend-runtime` mostra o padrão) e como transcrições de `configure simulate`.

## Modelo real

Crie o JSON de configuração sem segredo:

```json
{"profile": "openai", "model": "nome-do-modelo", "api_key": "env:OPENAI_API_KEY",
 "prices": {"input_per_million": 1, "output_per_million": 5}, "fallback": "rules"}
```

Confirme o contrato antes de medir: `vendedor model-check --adapter http --config model.json`. Depois `vendedor evaluate --split dev --repeat 4 --model-config model.json`. Preços vêm da configuração; o nome do modelo pode vir de `SELLER_MODEL_NAME`. Sem chave no ambiente, registre `not_run` e siga com o adaptador local. Perfil `openai-compatible` exige `endpoint` HTTPS explícito e a compatibilidade precisa ser provada por `model-check`.

## Relato

Entregue: comando, conjunto, `repeat`, versão do pacote, `pass@1`, `pass^k`, falhas críticas, custo e o que não foi medido. Não escreva "melhorou" sem a comparação com a base.
