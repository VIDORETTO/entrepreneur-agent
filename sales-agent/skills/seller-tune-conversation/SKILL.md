---
name: seller-tune-conversation
description: Ajustar como o vendedor conversa (perguntas, tom, transições, objeções, horário, transferência, mensagens não textuais) editando o pacote comercial versionado e provando com simulação. Use quando a pessoa disser que o vendedor pergunta demais, responde estranho, não entende um pedido ou precisa de outra regra.
version: "1"
---

# Ajustar a conversa

Quase todo ajuste de comportamento é **configuração do pacote**, não código. O pacote é um JSON versionado; o motor lê e aplica. Não existe "prompt do vendedor" para editar: o que o vendedor pode afirmar vem de ofertas e fontes aprovadas, e o que pode fazer vem de `package.capabilities`.

## Laço de ajuste

1. **Reproduza.** Pegue a mensagem que deu errado e rode sem alterar nada:
   ```bash
   vendedor configure simulate package.json --message "texto do comprador"
   ```
   Leia a ação escolhida, a resposta e o trace. Para uma conversa persistente use `vendedor chat --business-id ID --conversation-id c1 --contact-id verified:teste --event-id e1 --message "..."`.
2. **Diagnostique** a causa: dado ausente no pacote, política não configurada, fonte inexistente, capacidade desligada ou limite do motor. Só a última exige código (`seller-extend-runtime`).
3. **Mude uma coisa** no JSON e aumente `package_version`.
4. **Compare:** `vendedor configure diff --business-id ID package.json`, depois repita a simulação e mais 3 a 5 mensagens vizinhas, inclusive as que já funcionavam.
5. **Aplique:** rascunho vindo da entrevista usa `vendedor promote-package package.json`; pacote já ativo usa `vendedor import-package package.json`. Depois `vendedor validate`. Reverter: `vendedor restore-package --business-id ID --storage-version N`.

## O que você pode ajustar (e onde)

| Sintoma | Chave do pacote |
|---|---|
| não reconhece o nome que o comprador usa | `package.offers[].aliases` |
| pergunta algo que já sabia, ou não pergunta o que falta | `package.offers[].required_fields` e `package.policies` (grupo `conversation`: `ask_only_missing_required_field`, `do_not_qualify_ready_buyer`) |
| comprador diz "só quero informação" ou "prefiro proposta" e nada muda | `package.policies` (grupo `conversation`, lista `preference_transitions` com `terms`, `objective`, `profile`) |
| cotação vence cedo ou tarde | `package.offers[].quote_validity_minutes`; o que invalida a cotação fica em `package.policies` (grupo `quote`) |
| objeção sobre preço, garantia, prazo | fontes aprovadas em `package.sources` e `package.policies` (grupo `conversation`, `objection_policy`); desconto não aprovado nunca é inventado |
| resposta seca; quer texto mais natural | `package.draft_mode` igual a `on`: o redator reescreve, o motor verifica preço, prazo, URL e pergunta antes de entregar, e cai no template se falhar |
| repete a mesma resposta em loop | `package.loop_policy` (`fallback_limit`, padrão 2, oferece humano depois) |
| áudio, imagem ou documento | `package.non_text_policy`: `ask_text` (padrão) ou `offer_human` |
| fora do horário | `package.service_hours` (fuso IANA e intervalos por dia em inglês) |
| quanto tempo guardar dados | `package.privacy` (`retention_days`, padrão 180, `0` desliga o expurgo) |
| quer que use uma capacidade | `package.capabilities`: estados `enabled`, `assisted`, `disabled`, `pending`; os dois últimos exigem `reason` |
| quais skills entram na conversa | `package.skills` (`id`, `version`, `when`: `always`, `objection`, `material`, `objection-or-material`; `context_chars` limita o texto) |

## Limites que você não contorna

- **Preço, estoque, prazo, garantia:** só com valor aprovado pelo dono, na oferta ou numa fonte `approved` com `origin`. Sem valor, deixe `pending` e pergunte.
- **Capacidade `enabled` que cobra, reserva ou envia:** só existe se houver integração real testada. Pagamento real não existe nesta versão: `charged` é sempre falso.
- **Texto livre não vira regra.** Uma resposta de entrevista fica como indício até o dono aprovar de forma estruturada.
- **Não mude `package_version` para reaproveitar avaliação antiga:** o motor confere o conteúdo (fingerprint), então avaliações e pilotos anteriores não valem para um pacote editado.
- Não coloque instrução de "ignore regras" ou de revelar prompt em fonte. Fonte é dado, não ordem.

## Terminou quando

`configure simulate` mostra o comportamento novo nas mensagens do problema e nas vizinhas, `vendedor validate` passa, e `vendedor evaluate --split dev` não piorou (veja `seller-evaluate-and-tune`).
