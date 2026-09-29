---
name: seller-adapt
description: Ponto de entrada para adaptar o Vendedor Adaptável ao negócio de quem instalou. Use quando a pessoa pedir para configurar, ajustar, medir, conectar ou liberar o vendedor, ou quando o pedido misturar esses assuntos; escolhe a skill certa e fixa as regras de segurança.
version: "1"
---

# Adaptar o vendedor

Você trabalha com uma pessoa (dono ou desenvolvedor) que quer o vendedor funcionando bem para o negócio dela. O motor decide e autoriza; você muda configuração, testes e, quando necessário, código, sempre com prova.

## 1. Oriente-se antes de mudar qualquer coisa

```bash
vendedor doctor
vendedor skills doctor
vendedor validate
vendedor storage check
```

Leia o `AGENTS.md` do projeto (regras e notas do time). Exporte o pacote atual para ler o que existe: `vendedor export-package --business-id ID --output package.json`. Se não houver negócio instalado, o caminho é a entrevista (`sales-business-discovery`), não um pacote inventado.

## 2. Classifique o pedido e siga a skill

| O pedido é sobre... | Skill |
|---|---|
| fatos do negócio, decisões do dono, o que falta saber | `sales-business-discovery` |
| documentos, fontes, vigência, revogação | `sales-knowledge-preparation` |
| como o vendedor fala, pergunta, espera ou transfere | `seller-tune-conversation` |
| medir, comparar antes e depois, escolher modelo | `seller-evaluate-and-tune` |
| Chatwoot, WhatsApp, webhook, serviço | `seller-connect-channel` |
| deixar o vendedor falar com compradores reais | `seller-pilot-readiness` |
| algo que o pacote não consegue expressar | `seller-extend-runtime` |

Se o pedido cruzar dois assuntos, faça na ordem: fatos do negócio, conhecimento, conversa, medição, canal, piloto. Cada passo termina com uma prova antes do próximo.

## 3. Antes de agir, pergunte ao dono quando for decisão de negócio

Pergunte, não decida: preço, desconto, prazo, garantia, política de troca, horário de atendimento, quem recebe a transferência, quanto tempo guardar dados, se pode falar com compradores reais. Traga a opção recomendada e o impacto. Uma pergunta decisiva por vez.

## 4. Regras que não se negociam

- O motor é a autoridade; modelo, skill e prompt nunca autorizam efeito comercial.
- Sem segredo em arquivo: só `env:NOME`. Nunca imprima o valor de uma chave.
- Sem `git push`, deploy, envio real, registro de webhook ou mudança em outros serviços da máquina sem pedido explícito da pessoa.
- Não abra nem ajuste nada olhando o conjunto reservado da avaliação (`holdout`).
- Estado só pela CLI; nunca edite o SQLite em `.vendedor-data/`.
- Não apague nem afrouxe teste para passar.

## 5. Como fechar um trabalho

Diga em poucas linhas: o que mudou, o comando que prova e o resultado real, o que ficou `not_run` e por quê, e a decisão pendente do dono. Registre a decisão na seção "Notas deste projeto" do `AGENTS.md`.
