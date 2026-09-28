# Revisão TK-009

Baseline fixo: `53641a4ad0aac6e4da11550554271b8279f1d5ec`. Foram inspecionados
o diff de commits (vazio), staging (vazio), worktree, arquivos novos
`drafting.py` e `test_grounded_drafting.py`, schema, documentação e
EV-086–EV-089. `git diff --check` e Ruff passaram.

## Standards

Sem achados bloqueantes. O motor gera o template e decide a ação antes de
chamar o redator opcional. A resposta proposta passa por verificação
determinística de preço, percentual, prazo, quantidade, URL, alegação de
pagamento/política, pergunta e tópicos. O redator recebe o texto do comprador
em mensagem `user` delimitada; template e evidências ficam em `system`. Falha
do redator e duas violações preservam o template. O supervisor passou a usar
os mesmos extratores comerciais e de política. O modo padrão é `off`.

Uma corrida preexistente do mesmo evento ficou visível na regressão completa.
O guard de ação nula e uma espera local limitada a 0,2 segundo para o evento
em andamento permitem observar o efeito confirmado sem duplicá-lo. Cem
execuções multiprocesso focadas passaram após a correção. Esse ajuste em
`conversation.py` excede o mapa original do ticket, mas corrige uma falha
concreta descoberta durante a regressão.

## Spec

- AC-024: o rascunho com R$ 79,90 foi entregue (EV-086).
- AC-025: desconto de 10% repetido caiu para template com
  `claim_unsupported` duas vezes (EV-087).
- AC-026: ausência da pergunta de tamanho e da duração solicitada fez cair
  para template (EV-088).
- AC-027: URL não emitida nem aprovada foi rejeitada; permaneceu o link do
  checkout simulado (EV-089).

Sem achados bloqueantes. A suíte completa passou com 221 testes; Ruff passou.
Os testes do redator HTTP usam resposta falsa. Nenhuma chamada a modelo real
foi feita, e a semântica além dos extratores explícitos ainda pode exigir
template. Não há prova de qualidade da redação remota sem credencial.
