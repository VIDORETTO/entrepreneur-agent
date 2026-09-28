# Revisão TK-002 (parcial)

Baseline fixo: `27baee9a78962ff739507753c8cce27e29d9e6ad`.
Escopo: diff de trabalho, workflow no diretório pai, EV-003/EV-004;
commits e staging vazios após o baseline.

## Standards

Sem achado bloqueante no código e na configuração. `requires-python`,
classifiers e alvo Ruff agora concordam com o piso 3.11. A instalação 3.10
falhou pelo metadado do pacote; não houve alteração de dependências runtime.

## Spec

AC-003 permanece parcial: o instalador local rejeitou 3.10.21, e as suítes
locais passaram com 172 testes em 3.11.16 e 3.14.7. O workflow foi atualizado
para essas versões e tem job que verifica a recusa em 3.10, mas GitHub Actions
ainda não executou este commit. Esse é um gap de evidência do critério, pois
ele exige aprovação no CI. EV-004 registra a limitação; TK-002 não pode ser
marcado `verified` ou `done` ainda.

Revalidação após TK-012: EV-085 registra rejeição de 3.10.21, 208 testes
verdes tanto em 3.11.16 quanto em 3.14.7, build e Twine verdes. O CI real
continua sem execução porque o objetivo proíbe `git push`; AC-003 permanece
parcial e TK-002 permanece `implemented`.

## Revisão final após publicação autorizada

Baseline preservado: `27baee9a78962ff739507753c8cce27e29d9e6ad`.
Escopo revisado: diff do ticket em `pyproject.toml`, workflow, README e
`docs/INSTALLATION.md`; correção de lint em `.hybrid/hybrid.py`; EV-142 e
estado ainda não commitado. A autorização posterior do usuário permitiu o push.

**Standards:** nenhum achado bloqueante. O primeiro run de CI falhou no Ruff
por duas linhas preexistentes em `.hybrid/hybrid.py`; o commit `9d945fc`
corrigiu ambas sem mudar o comportamento. Ruff e 246 testes locais passaram.

**Spec:** AC-003 passou no run GitHub Actions `36472024805` para `9d945fc`:
jobs Python 3.11 e 3.14 verdes, recusa de instalação em 3.10 verde, distribuição
e relógio deslocado verdes. `requires-python >=3.11` e a matriz conferem com
FR-002. EV-142 registra o run. Nenhum achado bloqueante.

Limite: este CI prova o contrato Python; não constitui teste com modelo real,
canal real ou comprador. TK-002 foi marcado `done`; views e checkpoint foram
atualizados, e a convergência não apontou erro nem lacuna de AC-003.
