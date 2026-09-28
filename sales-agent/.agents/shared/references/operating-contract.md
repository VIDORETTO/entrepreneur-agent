# Contrato operacional

## Fontes e ownership

- Constituição e instruções do repositório delimitam o trabalho.
- `CONTEXT.md` contém somente vocabulário do domínio; não recebe detalhes de implementação.
- ADR registra apenas decisão difícil de reverter, surpreendente sem contexto e resultante de alternativas reais.
- `spec.md` é a fonte editável do comportamento, requisitos e critérios de aceite.
- `plan.md` é a fonte editável do desenho técnico, interfaces, compatibilidade e verificação.
- Cada `tickets/TK-xxx.md` é a fonte editável de uma fatia e de suas tarefas.
- `todo.md`/`tasks.md`, `backlog.md` e `verification.md` são projeções geradas quando o pacote as declara como tal.
- `state.json` é o checkpoint do esforço; não duplica todos os estados dos tickets.

## Estados

O esforço usa `phase` (`discovery`, `specification`, `planning`, `slicing`, `implementation`, `verification`, `review`, `convergence`, `delivery`, `closed`) e `status` (`active`, `waiting_input`, `blocked_external`, `failed`, `complete`, `cancelled`).

Um ticket segue `draft → ready → in_progress → implemented → verified → done`. Pode voltar a `in_progress` após mudança de código ou evidência e pode ficar `blocked`, `cancelled` ou `superseded` preservando histórico. Dependências de execução exigem predecessor `done` nesta versão.

`done` exige evidência de aceites com resultado `passed` e a revisão exigida pela política do esforço. Checkboxes de checklist continuam pertencendo ao autor declarado; o implementador não aprova em nome de reviewer.

## Protocolo de saída

Toda skill termina com um resultado equivalente a:

```text
outcome: completed | needs_input | blocked | failed
artifacts_changed: caminhos e revisões
findings: referências, quando existirem
evidence_refs: resultados observados
next_action: ação concreta no escopo
```

`needs_input` só é usado para uma escolha material sobre comportamento, público, limite de dados ou autorização. Falta de campo editorial ou convenção existente deve ser resolvida sem pausa. Falta de ambiente ou credencial vira `blocked` com trabalho concluído e ação concreta.

## Invalidação

Hash diferente é sinal para análise, não prova de mudança semântica. Depois de alterar requisito/aceite, contrato público, código sob teste, plano relevante, padrão obrigatório ou ambiente de teste, reavaliar dependentes. Evidência desatualizada é `stale`; nunca é convertida silenciosamente em `passed`.

## Ações externas

O núcleo opera localmente e sem tracker remoto. Publicação, mensagem, merge, deploy, instalação global e mudança de configuração pessoal não fazem parte da primeira versão. Uma skill prepara artefato revisável e só executa ação externa já autorizada e dentro do escopo.
