---
name: seller-connect-channel
description: Conectar o vendedor ao Chatwoot (WhatsApp ou outro inbox) com assinatura, serviço, janela de 24 h, eco e mensagens não textuais, testando só com servidor falso local. Use quando a pessoa pedir para ligar o vendedor a um canal, configurar o webhook ou rodar o serviço.
version: "1"
---

# Conectar o canal

O canal suportado é o **Chatwoot**. O runtime recebe o webhook, grava a entrada antes do ACK, monta o turno, decide e entrega pela API do Chatwoot com fila durável. Você prepara a configuração e prova o contrato sem tocar em nada real.

## Antes de tudo: limites

Esta máquina pode ter Chatwoot, proxies e serviços em produção. **Não** registre webhook, crie AgentBot, altere proxy, systemd, Docker ou variáveis de outros projetos, nem envie mensagem real, sem pedido explícito da pessoa para esse passo. Teste com servidor falso local em porta efêmera. O modo inicial de qualquer canal é observação.

## 1. Binding (quem pode falar com qual negócio)

Um arquivo JSON local, só com referências a segredos:

```json
{"business_id": "meu-negocio", "account_id": "11", "inbox_id": "13",
 "secret": "env:CHATWOOT_WEBHOOK_SECRET", "signature_mode": "timestamped",
 "channel_kind": "whatsapp"}
```

- `signature_mode` padrão `timestamped`: cabeçalhos `X-Chatwoot-Timestamp` (segundos Unix) e `X-Chatwoot-Signature: sha256=<hex>`; HMAC-SHA256 sobre `"{timestamp}."` mais o corpo bruto; tolerância de 300 s (`timestamp_tolerance_seconds`, de 60 a 900).
- `legacy-body` (assina só o corpo) só por opção explícita, aparece como `legacy_signature` e **bloqueia** a prontidão do piloto.
- `channel_kind: "whatsapp"` liga a janela de 24 h: resposta pública só até 24 h após a última mensagem do comprador; depois vira `window_closed` e uma nota privada avisa o atendente. Sem isso o padrão é `other`.
- Segredo literal no JSON é recusado.

Diagnostique sem imprimir o segredo: `vendedor doctor --chatwoot-binding binding.json` (a variável precisa estar no ambiente).

## 2. Contrato de admissão, sem rede

`vendedor channel chatwoot-admit --business-id ID --account-id 11 --inbox-id 13 --secret env:CHATWOOT_WEBHOOK_SECRET --body '{...}' --signature sha256=... --timestamp T` exercita assinatura, conta, inbox, replay e mensagens privadas ou humanas. Teste também uma assinatura errada, um timestamp velho e um replay: todos devem ser recusados. Guarde o comando e o resultado como evidência.

## 3. Serviço

Arquivo de configuração (guarde com acesso restrito ao usuário do serviço):

```json
{"bindings": [{"business_id": "meu-negocio", "account_id": "11", "inbox_id": "13",
   "secret": "env:CHATWOOT_WEBHOOK_SECRET", "signature_mode": "timestamped", "channel_kind": "whatsapp"}],
 "transport": {"base_url": "https://chatwoot.example.invalid", "account_id": "11",
   "api_access_token": "env:CHATWOOT_API_TOKEN", "timeout_seconds": 10},
 "window_seconds": 3, "poll_interval_seconds": 1, "lease_seconds": 60}
```

`vendedor --data-dir DIR serve --config service.json --host 127.0.0.1 --port 8080`. `GET /healthz` (processo vivo) e `GET /readyz` (SQLite íntegro e canal não interrompido; 503 caso contrário). O webhook é `POST /webhook`. Só uma instância por diretório de dados (trava `service.lock`); SIGTERM desliga com segurança. No proxy reverso, encaminhe apenas `/webhook`, preserve os dois cabeçalhos e o corpo bruto, aplique TLS e limites, e não exponha `/readyz` nem `/healthz` à internet. Você escreve a configuração; instalar no proxy ou no systemd é passo do dono.

## 4. Comportamentos que você deve verificar, com teste

- **Eco:** mensagem enviada pelo vendedor e devolvida pelo webhook `outgoing` não pausa a conversa; texto humano desconhecido pausa (intervenção humana).
- **Áudio, imagem, documento:** admitidos com metadados; sem transcritor segue `package.non_text_policy`. Transcritor opcional em `"transcriber"` (endpoint HTTPS, token `env:`); compra transcrita exige confirmação por texto.
- **Janela 24 h e follow-up:** revalidados no instante do envio; sem relógio confiável falha fechado.
- **Entrega desconhecida (`unknown`):** nunca reenvie às cegas. Use `vendedor outbox recover`, consulte o provedor e `vendedor outbox reconcile CHAVE --resolution ...` com evidência.

## 5. Modos

`vendedor pilot configure --business-id ID --channel chatwoot --mode observation` (não envia), depois `assistance` (não envia; sugere ao atendente), e só então `pilot`, que exige a prontidão de `seller-pilot-readiness`. `vendedor pilot interrupt` corta novas entregas na hora.

## Terminou quando

Contrato de admissão provado (incluindo casos negativos), serviço sobe contra servidor falso local com `/readyz` 200, modo observação configurado, e você listou o que o dono precisa fazer fora daqui (webhook, proxy, credenciais).
