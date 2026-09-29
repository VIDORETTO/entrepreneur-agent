# Instalação e atualização

Requer Python 3.11 ou superior. Para desenvolvimento local, use `python3.12`
ao criar o ambiente virtual. A matriz de CI verifica 3.11 e 3.14 e confirma
que o instalador recusa 3.10.

1. Crie ambiente virtual e instale o projeto com `python -m pip install -e .`
   (ou `python -m pip install .` para instalar a wheel).
2. Execute `vendedor doctor` para diagnosticar Python, SQLite, diretório
   privado, skills, modelo e Farol.
3. Execute `vendedor examples` ou importe um pacote validado.
4. Rode `vendedor validate` antes de habilitar atendimento.

Para desenvolvimento, instale o extra de testes com `python -m pip install -e ".[dev]"` e execute `python -m pytest -q`.

Os packs de skills, referências, schemas e atribuições também são incluídos na
wheel em `share/vendedor-adaptavel/`. O código instalado é separado dos dados
em `.vendedor-data/`. Em sistemas POSIX, o runtime restringe o diretório a
`0700` e o SQLite a `0600`; em Windows, use um perfil de usuário com ACL privada.
O SQLite contém
pacotes, conversas, eventos, efeitos idempotentes, outbox, inventário,
checkpoint e fontes. Não coloque segredos no pacote; o adaptador HTTP lê a chave
somente de `SELLER_MODEL_API_KEY` em tempo de execução.

Atualizações do código não sobrescrevem a base. Faça backup do diretório privado
antes de migrar; a avaliação de recuperação usa cópia da base e IDs
idempotentes. Uma alteração de política deve ser validada novamente e ter uma
versão de pacote promovida explicitamente.

## Agente de código (Claude Code, Codex e similares)

`vendedor skills install --target claude|codex|all [--dir DIR] [--dry-run] [--force]`
instala no projeto, sem sobrescrever conteúdo do usuário:

- `AGENTS.md` com um bloco gerenciado entre `<!-- vendedor-adaptavel:begin -->` e
  `<!-- vendedor-adaptavel:end -->`; o texto fora do bloco é preservado. Se o
  arquivo já existe sem o bloco, o bloco é acrescentado no fim.
- `claude`: `.claude/skills/<skill>/` e `CLAUDE.md` que importa `@AGENTS.md`.
- `codex`: `.agents/skills/<skill>/`.
- `.vendedor-workspace.json`: versão e SHA-256 de cada arquivo instalado.

Um arquivo já editado (ou que existia antes e difere) é mantido e aparece em
`skipped` com o motivo `modified` ou `unregistered_conflict`; `--force` o
substitui. `vendedor skills status` compara com o pacote instalado (`ok`,
`modified`, `missing`, `outdated`). Depois de atualizar o vendedor, rode
`skills install` de novo para receber as skills novas. `vendedor init --agents
claude|codex|all [--workspace DIR]` faz o mesmo ao criar o banco; sem `--agents`,
`init` não escreve fora do diretório de dados.
