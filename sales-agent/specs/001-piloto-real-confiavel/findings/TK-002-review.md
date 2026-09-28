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
