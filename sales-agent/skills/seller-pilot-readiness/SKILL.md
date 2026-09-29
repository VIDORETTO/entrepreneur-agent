---
name: seller-pilot-readiness
description: Decidir e executar, com prova, a passagem de observação para assistência e piloto com compradores reais (modelo real, holdout, canal, horário, privacidade LGPD, interrupção). Use quando a pessoa perguntar se o vendedor está pronto, quiser ativar o piloto ou precisar de privacidade e monitoramento.
version: "1"
---

# Prontidão do piloto

"Pronto" é o que o portão `vendedor pilot readiness` aceita com evidência **executada**, não o que parece bom. A decisão de ligar é do dono.

## O portão exige

| Item | Como se prova |
|---|---|
| `holdout_selected_model` | `evaluate --split holdout` com **modelo real** e o **mesmo pacote** que vai ao ar (versão e fingerprint), thresholds atendidos e SHA-256 do holdout igual ao instalado. Relatório de `rules-v1` não libera. |
| `model_check_selected_profile` | `vendedor model-check --adapter http --config model.json` passou, com o mesmo modelo e perfil do holdout |
| `channel_contract` | assinatura `timestamped` e eco provados (`seller-connect-channel`) |
| `service_hours` | `package.service_hours` declarado |
| `privacy` | `package.privacy` com `retention_days` |
| `interruption_exercised` | `vendedor pilot interrupt` exercitado para o mesmo negócio e canal |

## Passo a passo

1. **Pacote:** confirme com o dono horário de atendimento (fuso IANA), retenção de dados (padrão 180 dias; `0` desliga o expurgo), quem recebe a transferência e o que o vendedor nunca promete. Aplique pelo fluxo do pacote (`seller-tune-conversation`) e `vendedor validate`.
2. **Modelo real:** exige `OPENAI_API_KEY` (ou a chave do perfil) no ambiente e `SELLER_MODEL_NAME`. Sem chave: registre `not_run` e pare aqui; não simule o resultado.
   ```bash
   vendedor model-check --adapter http --config model.json
   vendedor evaluate --split holdout --repeat 4 --package package.json --business-id ID \
     --model-config model.json --output reports/holdout.json
   ```
3. **Canal e interrupção:** execute os testes de `seller-connect-channel` e `vendedor pilot interrupt --business-id ID --channel chatwoot --reason "teste de interrupção"` em ambiente de teste.
4. **Monte o arquivo de evidências** com as chaves `holdout`, `model_check`, `channel_contract` e `interruption`, copiando o que os comandos **realmente** retornaram. Não há comando que gere esse arquivo: cada campo (`signature_passed`, `echo_passed`, `status`, `scope_key`) precisa vir de uma execução que você fez e anotou. Nunca escreva `true` por presunção; o que não foi executado fica de fora, e o portão o listará em `missing`.
5. **Portão:** `vendedor pilot readiness --business-id ID --channel chatwoot --evidence-file evidencias.json`. Leia `ready` e `missing`.
6. **Modos:** `vendedor pilot configure ... --mode observation`, depois `assistance`, e só com `ready: true` e autorização explícita do dono, `--mode pilot --cohort ... --limits ... --evaluated-package-version V --authorize`. Uma exceção (`--override --reason`) é decisão registrada do dono, nunca sua.

## Privacidade (LGPD) que você deve conhecer

- `vendedor privacy export --business-id ID --contact CONTATO` exporta o histórico do titular.
- `vendedor privacy erase ...` remove o histórico e anonimiza efeitos; é irreversível no banco ativo, então faça `vendedor storage backup` antes.
- `vendedor privacy purge --business-id ID` aplica a retenção do pacote; `--before` aceita corte ISO-8601 com fuso.
- Relatórios redigem telefone, e-mail e documento como `[REDACTED]`. Não acrescente dados reais a fixtures ou relatórios.

## Acompanhar depois de ligar

`vendedor supervisor report` (rejeições, falsos positivos, custo, latência), `vendedor outbox list`, `vendedor effects list` (efeitos `unknown` precisam de conciliação com evidência do provedor), `vendedor storage check` e backups periódicos. Qualquer sinal estranho: `vendedor pilot interrupt` primeiro, investigação depois.

## Terminou quando

O relatório final traz: `ready` e `missing` do portão, o que ficou `not_run`, a decisão do dono (quem, quando, com que limite de coorte) e o plano de interrupção. Se algo obrigatório faltar, o estado honesto é "não pronto".
