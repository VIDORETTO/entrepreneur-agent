# Operação e limites

O conector inicial é um simulador: URL usa domínio inválido, `charged` é
sempre falso e pagamento só pode ser confirmado por um evento de provedor que
ainda não existe nesta versão. Timeout vira `unknown` e não é repetido às cegas.

A transferência grava fatos e estado, pausa o vendedor e deixa a retomada para
uma liberação explícita. Follow-up é opt-in e revalidado no momento do envio;
recusa, compra, transferência ou resposta tornam a tarefa inelegível.

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
4. executar `vendedor outbox nack CHAVE --error TEXTO` em falha.

Após o limite de tentativas o item entra em `dead_letter`. `vendedor outbox
recover` recupera itens `processing` cujo lease expirou. A integração real do
canal ainda precisa fornecer seu próprio remetente e comprovar idempotência.

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
