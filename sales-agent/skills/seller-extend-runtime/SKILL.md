---
name: seller-extend-runtime
description: Alterar o código do runtime do vendedor (nova capacidade comercial, integração de pagamento ou agenda, adaptador de modelo, regra que o pacote não expressa) com TDD, sem tirar a autoridade do motor. Use só depois de confirmar que o ajuste não cabe no pacote.
version: "1"
---

# Estender o runtime

Antes de escrever código, prove que o pacote não resolve (`seller-tune-conversation`). Código novo é o último recurso porque aumenta o que precisa ser testado, revisado e mantido.

## Pré-condição: código editável

Isto só vale para quem tem o código-fonte (`src/sales_agent/`). Com a instalação por wheel, faça um clone ou fork e instale com `python -m pip install -e ".[dev]"` (Python 3.11 ou superior; use `python3.12 -m venv .venv`). Não edite dentro de `site-packages`.

## Mapa do código

| Assunto | Módulo |
|---|---|
| decisão da conversa, ações, transições | `conversation.py` (`SellerEngine.handle`) |
| interpretação e adaptadores de modelo | `model.py` (`RuleBasedModel`, `HTTPModelAdapter`) |
| redação natural verificada | `drafting.py` |
| cotação, checkout, proposta, efeitos | `commerce.py` |
| conhecimento e evidência | `knowledge.py` |
| canal Chatwoot, assinatura, eco | `channel.py`, `service.py`, `turns.py`, `delivery.py` |
| estado, migração, outbox | `storage.py` |
| pacote e validação | `config.py`, `validation.py` e o schema JSON do pacote |
| avaliação | `evaluation.py` e os arquivos em `evaluation/` |
| privacidade e retenção | `privacy.py` |
| piloto e supervisão | `governance.py` |
| tempo | `clock.py` (relógio injetável) |

Leia o módulo, os testes existentes dele e o glossário `CONTEXT.md` antes de mexer.

## Invariantes (violar qualquer um reprova a mudança)

1. **O motor decide.** O modelo, o redator, o transcritor e as skills só propõem. Nenhum efeito (cobrar, reservar, enviar, transferir) sai de saída de modelo sem validação do motor.
2. **Falha fechada.** Proposta inválida, recusa do provedor, relógio ausente ou resultado desconhecido não autorizam efeito. `unknown` nunca é repetido às cegas; concilia-se com evidência.
3. **Idempotência e durabilidade.** Todo efeito tem chave idempotente e é gravado no mesmo commit que o evento.
4. **Tempo injetável.** Use o relógio de `clock.py`; nunca leia a data do processo direto, para a suíte passar em qualquer dia (`python -m pytest -q --clock-shift-days=400`).
5. **Sem dependência de runtime nova** sem decisão do dono: o projeto usa a biblioteca padrão (o adaptador HTTP usa `urllib`).
6. **Sem segredo em código, teste, log ou relatório.**
7. **Compatibilidade de dados.** Mudança de estado usa migração aditiva versionada; nunca reescreva histórico de conversa.

## Método: um comportamento por vez, teste primeiro

1. Escreva o teste na interface pública: `SellerEngine.handle(evento)` sobre um `StateStore` temporário real (`StateStore(tmp_path)`, `seed_examples`), ou a CLI por `main([...])`. Dublês só para relógio, servidor Chatwoot falso, servidor do modelo falso, transcritor e aleatoriedade. Não prove comportamento lendo tabelas.
2. Rode e confirme que falha **pelo motivo previsto** (comportamento ausente). Erro de import ou de fixture não é falha válida.
3. Implemente o mínimo para passar; rode o arquivo de teste.
4. Rode tudo: `python -m pytest -q` e `ruff check src tests`; depois `vendedor evaluate` e `vendedor evaluate --split dev --repeat 4` e compare com a base (`seller-evaluate-and-tune`).
5. Atualize schema do pacote, documentação e o teste de contrato quando a interface pública mudar.
6. Não altere o holdout nem o critério de aceite para acomodar a implementação.

Em um esforço maior que uma tarefa, use o fluxo do projeto (`specs/` com contrato, critérios de aceite e evidência) se ele existir; se não existir, escreva o contrato em texto (entradas, saída, erros, compatibilidade) e obtenha o aceite do dono antes de codar.

## Pare e devolva à pessoa quando

- surgir decisão nova de comportamento, contrato público, modelo de dados ou autorização;
- o recurso obrigatório (chave, provedor, canal) estiver indisponível e a tarefa não puder ser concluída de forma honesta;
- a ação exigir tocar produção.

Credencial ausente não bloqueia o trabalho local: registre `not_run` e continue com o que é verificável.
