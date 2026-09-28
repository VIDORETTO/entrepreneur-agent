# Operação e limites

O conector inicial é um simulador: URL usa domínio inválido, `charged` é
sempre falso e pagamento só pode ser confirmado por um evento de provedor que
ainda não existe nesta versão. Timeout vira `unknown` e não é repetido às cegas.

A transferência grava fatos e estado, pausa o vendedor e deixa a retomada para
uma liberação explícita. Follow-up é opt-in e revalidado no momento do envio;
recusa, compra, transferência ou resposta tornam a tarefa inelegível.

Uma pausa humana só volta ao atendimento automático por `vendedor conversation
resume`, com autoridade e motivo registrados. Saudação, agradecimento e replay
não liberam a conversa.

Não publicar, fazer deploy, enviar mensagem, cobrar ou conectar sistemas reais
sem uma decisão específica e testes da integração correspondente.

## Banco e recuperação

O SQLite usa WAL, sincronização completa, timeout para concorrência e migrações
aditivas identificadas por `PRAGMA user_version`. `vendedor doctor` inclui o
relatório de integridade. Para operação manual:

```bash
vendedor storage check
vendedor storage backup ./backup.sqlite3
vendedor storage restore ./backup.sqlite3 --backup-current ./estado-anterior.sqlite3
```

Backup nunca sobrescreve arquivo existente. A restauração valida integridade,
tabelas e versão antes de tocar no banco ativo e exige um backup de segurança
do estado corrente.

## Entrega da outbox

Cada resposta e sua intenção de entrega são persistidas atomicamente com o
evento e a conversa. Um worker de canal deve seguir o protocolo:

1. `vendedor outbox claim --limit N --lease-seconds S`;
2. entregar usando `message_key` como chave idempotente;
3. executar `vendedor outbox ack CHAVE` em sucesso;
4. executar `vendedor outbox nack CHAVE --error TEXTO` em falha comprovadamente transitória.

Após o limite de tentativas o item entra em `dead_letter`. `vendedor outbox
recover` move itens `processing` cujo lease expirou para `unknown`; como o
provedor pode ter aceitado a mensagem, eles não voltam à fila automaticamente.
Consulte o provedor e use `vendedor outbox reconcile CHAVE --resolution ...`
com evidência antes de encerrar o caso. A integração real do canal ainda
precisa fornecer seu próprio remetente e comprovar idempotência.

O runtime também oferece `vendedor outbox process --channel chatwoot` com um
provedor falso explícito para validar o ciclo local. O comando não configura
credenciais nem envia para um canal externo.

## Skills, turnos e canal

`vendedor skills list`, `skills show ID` e `skills doctor` verificam somente as
skills distribuídas pelo produto. Skills de configuração não entram na conversa
do comprador. `vendedor turn receive` grava mensagens e `turn process` agrupa a
janela persistida, preservando cada id original.

O receptor Chatwoot valida HMAC, conta, inbox e negócio antes de admitir uma
mensagem. Mensagens privadas, humanas, de saída e replays ficam fora da fila do
comprador. A entrada autenticada é gravada antes do ACK. O contrato local pode
ser exercitado com `vendedor channel chatwoot-admit`; isso não comprova uma
integração de produção. Depois da admissão autenticada, o envelope carrega a
identidade externa `chatwoot:<id>` e ela pode ser usada pelo checkout simulado;
esse vínculo é conferido no ledger persistente do evento. O prefixo
`verified:*` continua reservado aos exemplos e à simulação local.

O binding Chatwoot usa `signature_mode: "timestamped"` por padrão. O receptor
exige `X-Chatwoot-Timestamp` em segundos Unix e
`X-Chatwoot-Signature: sha256=<hex>`; o HMAC-SHA256 cobre os bytes de
`"{timestamp}."` seguidos do corpo bruto. O timestamp deve estar a até 300 s
do relógio do receptor, configurável por binding entre 60 e 900 s. Um binding
antigo que assina somente o corpo precisa declarar `"signature_mode":
"legacy-body"` explicitamente. Esse modo aparece como `legacy_signature` no
diagnóstico e deve ser recusado pelo portão de prontidão do piloto.

Para diagnosticar um binding sem imprimir o segredo, use um JSON local com os
campos `business_id`, `account_id`, `inbox_id`, `secret: "env:NOME"`,
`signature_mode` e, opcionalmente, `timestamp_tolerance_seconds`; uma lista
pode ficar sob `bindings`. Então execute `vendedor doctor --chatwoot-binding
binding.json` com a variável de ambiente configurada. O diagnóstico lê o
segredo somente em memória e informa se há assinatura legada.
O harness `vendedor channel chatwoot-admit` aceita `--timestamp` com o valor
exato usado na assinatura e `--secret env:NOME`; `--signature-mode legacy-body`
é necessário para testes com assinatura antiga.

### Serviço Chatwoot

`vendedor serve` executa receptor HTTP e worker de turnos e entregas no mesmo
processo. Prepare o negócio no diretório de dados, configure o piloto pela CLI
e guarde o arquivo de configuração com acesso restrito ao usuário do serviço.
O arquivo contém apenas referências aos segredos:

```json
{
  "bindings": [{
    "business_id": "minha-loja", "account_id": "11", "inbox_id": "13",
    "secret": "env:CHATWOOT_WEBHOOK_SECRET", "signature_mode": "timestamped",
    "channel_kind": "whatsapp"
  }],
  "transport": {
    "base_url": "https://chatwoot.example.invalid",
    "account_id": "11", "api_access_token": "env:CHATWOOT_API_TOKEN",
    "timeout_seconds": 10
  },
  "window_seconds": 3, "poll_interval_seconds": 1, "lease_seconds": 60
}
```

```bash
vendedor --data-dir /var/lib/vendedor serve --config /etc/vendedor/service.json \
  --host 127.0.0.1 --port 8080
```

`GET /healthz` confirma que o processo responde. `GET /readyz` exige SQLite
íntegro e canal não interrompido; informa `storage_integrity_failed` ou
`channel_interrupted` com HTTP 503. O webhook é `POST /webhook`; o ACK é enviado
depois da gravação da entrada, antes de montar o turno ou chamar o Chatwoot.
Segredo literal no JSON é recusado. Uma trava em `service.lock` impede dois
processos sobre o mesmo diretório. SIGTERM bloqueia novas admissões, aguarda a
tentativa de entrega atual e fecha o servidor. Entrega sem ACK confirmado fica
`unknown` e requer conciliação; leases vencidos são recuperados no início.

Exemplo de unidade systemd, a adaptar ao usuário e caminhos locais:

```ini
[Unit]
Description=Vendedor Chatwoot
After=network-online.target

[Service]
Type=simple
User=vendedor
EnvironmentFile=/etc/vendedor/secrets.env
ExecStart=/usr/local/bin/vendedor --data-dir /var/lib/vendedor serve --config /etc/vendedor/service.json --host 127.0.0.1 --port 8080
Restart=on-failure
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

No proxy reverso, encaminhe somente o caminho `/webhook` ao endereço local e
preserve os cabeçalhos `X-Chatwoot-Timestamp` e `X-Chatwoot-Signature` e o corpo
bruto. Exponha `/readyz` e `/healthz` apenas à rede de monitoramento. O proxy
deve aplicar TLS e limites de corpo e de taxa adequados à instalação.

Para inbox WhatsApp, declare `channel_kind: "whatsapp"` no binding. O padrão
`other` não aplica a janela. Uma resposta pública só é enviada até 24 h após
a última mensagem admitida do comprador, no instante da entrega. Depois disso,
o item termina em `window_closed` e uma nota privada idempotente avisa o
atendente, inclusive em modo de observação; uma interrupção do canal bloqueia
esse envio. Follow-ups são revalidados na mesma janela; sem instante confiável
o envio público falha fechado. Templates HSM não fazem parte deste serviço.

Áudio, imagem e documento são admitidos com metadados `type`, `mime` e `size`;
o serviço não baixa anexos por padrão. Sem transcritor, um áudio sem legenda
segue `non_text_policy` do pacote. Opcionalmente, o JSON do serviço aceita
`"transcriber": {"endpoint": "https://transcriber.example.invalid/transcribe",
"token": "env:TRANSCRIBER_API_TOKEN", "timeout_seconds": 10}`. O adaptador envia
apenas a URL HTTPS do áudio ao endpoint configurado. Uma transcrição é marcada
no trace e um pedido de compra transcrito exige confirmação posterior por
texto antes de qualquer operação comercial. Falha de transcrição volta à
política do pacote.

Na entrega pública, o trabalhador registra um hash do conteúdo como envio em
curso antes de chamar o transporte. Ao receber o ID da mensagem do Chatwoot,
grava esse ID no mesmo commit que confirma o item do outbox. Um webhook
`outgoing` com esse ID é eco do vendedor, mesmo se `sender.type=user`. Se o
webhook chegar antes da resposta do POST, o receptor usa o hash do conteúdo
somente na mesma conversa e durante 120 s. IDs desconhecidos ou texto diferente
continuam sendo tratados como intervenção humana. O ledger persiste no SQLite
entre reinícios e não guarda o texto da resposta.

Os modos de canal são `observation`, `assistance` e `pilot`. Observação e
assistência não enviam mensagens públicas. Piloto exige versão e fingerprint do
pacote avaliados, coorte, limites e autorização explícita; reservas de entrega
e custo são persistidas por chave idempotente, inclusive durante restart. Um
resultado `unknown` mantém a reserva até conciliação; cancelamento e sucesso a
liquidam uma única vez. `pilot interrupt` bloqueia novas entregas e as métricas
persistem apenas contadores estruturados.

O supervisor começa desligado, pode ser configurado para observação ou revisão
seletiva e aceita no máximo uma correção com revalidação. A política pode ser
`optional`, preservando o candidato quando o revisor falha, ou `mandatory`,
bloqueando a entrega até revisão seletiva disponível; `mandatory` em `off` ou
`observation` também falha fechado. Timeout é registrado como `timeout` e não
aplica correção tardia. `supervisor report` compara a linha de base
determinística com custo, latência e falhas do supervisor; mudar para `off` não
exige migrar conversas.

Consulte `vendedor supervisor report` para o agregado de rejeições, falsos
positivos, falhas determinísticas, dimensões de qualidade, latência, custo e
correções. O relatório não substitui a validação de capacidades, evidências ou
efeitos.

`vendedor farol status` informa a situação do cliente Farol estável. O estado
`blocked` é esperado enquanto a versão e o contrato executável não forem
disponibilizados; o backend local `sqlite-farol-v1` não é promovido a essa
integração por fallback.

## Conciliação de efeitos

Liste efeitos com `vendedor effects list`. Efeitos `reserved` ou `unknown`
precisam ser consultados no provedor antes de qualquer repetição. Registre o
resultado com:

```bash
vendedor effects reconcile CHAVE --resolution failed \
  --details '{"resolution_source":"consulta-ficticia","reason":"não confirmado"}'
```

Para `confirmed`, checkouts exigem `checkout_id`, `url` e `charged: false`.
Metadados de negócio, conversa, cotação e reserva de estoque não podem ser
alterados pelos detalhes da conciliação. Falha compensa o estoque uma vez e
libera uma nova tentativa com outra chave idempotente. Se uma correção de
conversa conflitar com um checkout já preparado, a reversão só é aceita com
`cancelled: true` e uma `resolution_source` não vazia; até lá o motor bloqueia
novas alterações de pedido e novos checkouts.

## Privacidade local

`vendedor --data-dir DIR privacy export --business-id ID --contact CONTATO` exporta as conversas e eventos do contato indicado. `privacy erase` remove esse histórico e anonimiza os efeitos persistidos com um HMAC local; o segredo fica em `DIR/privacy.key` com permissão privada. A operação registra um evento em `privacy_audit` e mantém contadores agregados. Faça um backup operacional antes da eliminação, pois ela é irreversível no banco ativo.

`privacy purge --business-id ID` usa `privacy.retention_days` do pacote (padrão 180 dias); `0` desativa o expurgo automático. `--before` permite um corte ISO-8601 explícito com fuso. Intenções de entrega pendentes permanecem na outbox até conciliação; o expurgo remove eventos antigos e limpa o histórico da conversa correspondente. A exportação usa JSON e os relatórios de avaliação substituem telefones, e-mails e documentos reconhecidos por `[REDACTED]`.

## Portão do piloto

`vendedor pilot readiness --business-id ID --channel chatwoot --evidence-file bundle.json` devolve `ready`, `missing` e os nomes das evidências aceitas. O bundle reúne `holdout` do modelo e pacote selecionados, `model_check`, `channel_contract` (assinatura timestamped e eco) e `interruption` para o mesmo escopo. O hash do holdout deve corresponder ao corpus instalado. O pacote precisa declarar `service_hours` e `privacy.retention_days`. Um relatório `rules-v1` não libera o piloto.

`pilot configure --mode pilot` consulta o mesmo portão e retorna código 2 se faltar prova. O dono pode registrar uma exceção explícita com `--authorize --override --reason TEXTO`; `pilot inspect` exibe o motivo e os itens ausentes. Isso altera somente o estado local. Não registra webhook nem ativa uma integração externa.
