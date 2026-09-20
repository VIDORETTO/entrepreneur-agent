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
