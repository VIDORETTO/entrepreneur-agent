## Vendedor Adaptável: como o agente de código deve trabalhar aqui

Este projeto usa o **Vendedor Adaptável**: um vendedor comercial configurável cujo estado, políticas, permissões, cotação e efeitos ficam num motor local com SQLite. O modelo de linguagem interpreta a mensagem e **propõe** fatos e intenção; quem **decide e autoriza** é o motor (`SellerEngine`/`DeliveryProcessor`). Você ajuda a pessoa a configurar, ajustar, medir, conectar e liberar esse vendedor para o negócio dela.

### Regras que não mudam

1. **O motor é a autoridade.** Nada que o modelo, uma skill, um prompt ou este arquivo diga concede preço, desconto, cobrança, reserva, transferência ou envio. Isso vem do pacote comercial aprovado e do código com teste.
2. **Nunca invente fato do negócio.** Preço, estoque, prazo, política, horário e promessa vêm do dono ou de fonte aprovada. Sem a informação, pergunte ao dono e registre a lacuna; não use exemplo fictício como se fosse real.
3. **Segredos ficam fora dos arquivos.** Use referências `env:NOME`. Nunca escreva chave, token, telefone, e-mail ou CPF reais em pacote, teste, log, relatório ou commit, e nunca imprima o valor de uma chave.
4. **Não toque em produção sem decisão explícita.** Sem autorização específica da pessoa, não faça deploy, `git push`, envio real a compradores, registro de webhook, mudança em proxy, systemd, Docker ou em outros serviços da máquina. Teste canal com servidor falso local em porta efêmera.
5. **Não enfraqueça a prova.** Não apague nem afrouxe teste ou caso de avaliação para passar. Não ajuste prompt ou regra olhando o conjunto reservado (`holdout`); não abra o arquivo dele.
6. **Não edite o estado à mão.** O diretório `.vendedor-data/` (SQLite, chave de privacidade) só se altera pela CLI `vendedor`. Não o coloque no git.
7. **Relate com honestidade.** Diga o que rodou, com o comando e o resultado. O que não foi executado (por falta de chave, canal ou tempo) é `not_run`, não "passou".

### Por onde começar

Confirme o ambiente e o que já existe:

```bash
vendedor doctor            # Python, SQLite, diretório privado, skills, modelo, Farol
vendedor skills doctor     # skills instaladas e referências
vendedor validate          # pacotes comerciais instalados
```

Depois escolha a skill pelo objetivo (elas estão em `.claude/skills/` ou `.agents/skills/`; se faltar alguma, `vendedor skills install`):

| Objetivo da pessoa | Skill |
|---|---|
| Não sabe por onde começar, ou o pedido mistura assuntos | `seller-adapt` |
| Descrever o negócio, decisões do dono, checkpoint | `sales-business-discovery` |
| Preparar fontes de conhecimento, versões, revogação | `sales-knowledge-preparation` |
| Ajustar como o vendedor conversa (pacote, políticas, tom) | `seller-tune-conversation` |
| Medir qualidade e melhorar com método | `seller-evaluate-and-tune` |
| Conectar o Chatwoot / WhatsApp | `seller-connect-channel` |
| Liberar observação, assistência ou piloto | `seller-pilot-readiness` |
| Mudar o código do runtime (nova capacidade, adaptador) | `seller-extend-runtime` |
| Diagnosticar instalação e capacidades | `sales-setup` |
| Rodar cenários reproduzíveis | `sales-simulate` |
| Política de conversa com o comprador | `seller-conversation` |

### Ciclo de trabalho

1. **Entender o pedido** e o estado atual (`doctor`, `validate`, o pacote exportado).
2. **Mudar uma coisa por vez**, de forma reversível: pacote versionado ou teste primeiro, depois código.
3. **Provar** com um comando repetível: `vendedor configure simulate`, `vendedor evaluate --split dev`, `python -m pytest -q`.
4. **Ler o resultado**, não só o código de saída; comparar antes e depois.
5. **Registrar a decisão** na seção "Notas deste projeto" abaixo: o que mudou, por quê, quem aprovou, e o comando que prova.

### Pacote comercial em uma linha

O pacote (JSON versionado) reúne negócio, ofertas, políticas, capacidades, fontes e skills. Fluxo seguro de mudança: `vendedor export-package` → editar o JSON → aumentar `package_version` → `vendedor configure diff` e `configure simulate` → `vendedor import-package` (ou `promote-package` para rascunho da entrevista) → `vendedor validate`. Voltar atrás: `vendedor restore-package`. O texto livre de uma entrevista nunca vira preço, estoque ou autorização por conta própria.

### Pronto significa

- o comportamento pedido está coberto por um teste ou cenário que falhou antes e passa agora;
- `python -m pytest -q` e `vendedor validate` passam, e `ruff check` quando há código Python novo;
- nenhuma regra acima foi contornada;
- a decisão do dono e a evidência estão registradas.
