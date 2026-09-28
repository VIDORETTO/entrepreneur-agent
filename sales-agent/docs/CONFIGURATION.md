# Configuração do dono

## Redação opcional de respostas

O pacote aceita `"draft_mode": "on"` ou `"off"` (padrão). Em `on`, o
adaptador de modelo pode produzir uma versão natural do template já calculado
pelo motor. O motor verifica preço, percentual, prazo, quantidade, URL,
pergunta necessária e tópicos solicitados antes de entregar o texto. Um
rascunho inválido recebe uma única tentativa de correção; se a segunda falhar
ou o redator estiver indisponível, o comprador recebe o template. O trace
registra `draft_accepted`, `claim_unsupported` e `draft_fallback`. A ação
comercial continua sendo decidida pelo motor; o redator recebe o link emitido
e não cria um novo. Configure o adaptador HTTP com a mesma referência
`env:NOME` de `model-check` quando desejar redação remota.

`configure start` lê materiais fornecidos, registra indícios com origem e cria
uma questão prioritária. Cada `answer` grava decisões e avança o cursor. Uma
sessão nova consulta o checkpoint, não repete a entrevista inteira. `finalize`
gera um pacote em estado `draft`. Ele não transforma texto livre em preço,
estoque, fonte aprovada ou autorização: cotação, checkout e conhecimento ficam
`pending` até uma revisão estruturada.

Use `vendedor export-package --business-id ID --output package.json`, revise o
arquivo, incremente `package_version`, mude `lifecycle` para `active` somente
depois das aprovações e então execute `vendedor promote-package package.json`.
A promoção exige que o rascunho correspondente esteja instalado e preserva o
registro `owner_configuration`. Um pacote `draft` não pode
habilitar capacidades operacionais. A importação
valida tipos, preços, estoque, capacidades, fontes e versões antes de ativar a
nova versão. Materiais lidos pela entrevista continuam como indícios, não como
fonte aprovada silenciosamente.

O runtime calcula também um fingerprint SHA-256 do pacote persistido. Pilotos,
entregas pendentes e revisões seletivas conferem esse fingerprint no momento
da execução; editar o conteúdo mantendo a mesma `package_version` não herda
uma avaliação ou autorização anterior.

A configuração não pede senhas. Capacidades sem integração permanecem
`disabled`/`pending`; isso não impede capacidades independentes, como consultar
uma oferta sem cobrar.

Cada decisão da entrevista mantém estado `confirmed`, `inferred`,
`conflicting` ou `absent`. O checkpoint registra perguntas respondidas,
adiadas e o impedimento da capacidade escolhida. A versão finalizada do pacote
fica separada da versão de armazenamento, para que uma restauração seja uma
nova promoção auditável.

Use `vendedor skills list`, `vendedor skills show ID` e `vendedor skills doctor`
para verificar a instalação. O catálogo só expõe skills de atendimento ao
comprador e configuração do negócio; versão incompatível ou referência ausente
vira diagnóstico. Skills não concedem permissões e não entram no contexto do
comprador quando pertencem à configuração.

Para revisar uma proposta sem alterar o negócio ativo, use `configure inspect`,
`configure diff` e `configure simulate`. A simulação usa um SQLite temporário.
Uma restauração recebe uma nova versão por `configure restore --business-id ID
--storage-version N`; ela reaplica validação e mantém revogações de fontes.

Fontes encontradas em uma base anterior à governança de revisão recebem
`review_status=pending_review` e ficam fora da consulta até `knowledge review`
registrar motivo e autoridade. Isso evita escolher a revisão vigente pela ordem
lexicográfica.

O produto diferencia:

- fatos confirmados, inferidos e conflitantes;
- fase comercial, prontidão, impedimento, operação e responsável;
- documento, dado operacional e memória da conversa;
- preparar/enviar/reservar/cobrar e seus resultados.

`non_text_policy` na raiz do pacote aceita `ask_text` (padrão) ou
`offer_human`. Sem transcritor, áudio sem legenda usa essa resposta e registra
metadados do anexo. A política não interpreta mídia nem autoriza checkout.

Para interpretação remota, `SELLER_MODEL_CONFIG` aponta para um JSON como:

```json
{
  "profile": "openai", "model": "modelo-configurado-pelo-operador",
  "api_key": "env:OPENAI_API_KEY",
  "prices": {"input_per_million": 1, "output_per_million": 5},
  "fallback": "rules"
}
```

O perfil `openai` usa Chat Completions e Structured Outputs estrito; confirme
que o modelo configurado suporta `json_schema`. `openai-compatible` aceita
`endpoint` HTTPS explícito e não envia `strict`; a compatibilidade deve ser
comprovada com `vendedor model-check --adapter http --config model.json`.
O valor da chave só vem do ambiente. `SELLER_MODEL_NAME` pode fornecer o nome
quando `model` não está no JSON. Os preços são por milhão de tokens de entrada
e saída e nunca são fixos no adaptador. Após duas propostas inválidas, o
fallback registra `model_contract_failed` e não autoriza efeitos comerciais.
Uma recusa explícita do provedor segue a mesma falha fechada.

### Atendimento humano

O pacote pode definir `service_hours` com `timezone` IANA e `intervals` por dia da semana em inglês (`monday` a `sunday`), cada um com `start` e `end` em `HH:MM`. Em transferência fora do horário, a resposta informa a próxima abertura calculada no fuso configurado. Sem horário, informa que a disponibilidade não foi declarada. `loop_policy.fallback_limit` controla quantos fallbacks consecutivos são tolerados antes de oferecer atendimento humano no turno seguinte; o padrão é 2.
