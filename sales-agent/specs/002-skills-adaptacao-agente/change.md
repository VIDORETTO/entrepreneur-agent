---
schema: hybrid/change
schema_version: 1.0
effort_id: 002-skills-adaptacao-agente
revision: 1
status: accepted
profile: compact
---

# Change: Skills e AGENTS.md para adaptar o vendedor com agentes de código

## Objetivo e limites

Quem instala o Vendedor Adaptável e usa Claude Code, Codex ou outro agente compatível com `AGENTS.md`/skills deve receber, com um comando, (a) um `AGENTS.md` com as regras e o fluxo de trabalho do produto e (b) skills que guiam o agente a configurar, ajustar, avaliar, conectar e liberar o vendedor com segurança.

Dentro: comando `vendedor skills install`/`status`, opção `vendedor init --agents`, modelo de `AGENTS.md`, cinco skills de adaptação novas, atualização das cinco skills existentes, documentação e empacotamento.
Fora: mudar o motor de conversa, o formato do pacote, a avaliação ou o canal; publicar; qualquer skill que conceda capacidade operacional; novo runtime de skills para o comprador. Decisão do dono (2026-09-29): "faça tudo que achar melhor".

## Contrato de comportamento

- Entradas: `vendedor skills install [--target claude|codex|all] [--dir DIR] [--force] [--dry-run]`; `vendedor skills status [--dir DIR]`; `vendedor init --agents claude|codex|all [--workspace DIR]`.
- Saída: JSON com `written`, `unchanged`, `skipped` (com motivo) por arquivo. `AGENTS.md` recebe um bloco gerenciado entre marcadores; `claude` grava skills em `.claude/skills/<id>/` e `CLAUDE.md` que importa `@AGENTS.md`; `codex` grava em `.agents/skills/<id>/`. Um `.vendedor-workspace.json` guarda versão e hash de cada arquivo instalado.
- Erros/invariantes: nunca sobrescrever conteúdo do usuário. Fora do bloco gerenciado o `AGENTS.md` é intocável. Arquivo de skill modificado pelo usuário ou sem registro e diferente é preservado (`skipped`), salvo `--force`. Nenhum segredo é escrito. Reexecutar sem mudança não altera arquivos. `--dry-run` não escreve nada. Alvo desconhecido é erro de uso.
- Compatibilidade: `vendedor init` sem `--agents` não escreve fora do diretório de dados. Skills de adaptação têm audiência `developer-adaptation` e nunca entram no contexto do comprador nem em `SkillCatalog.select`. `skills list/show/doctor` seguem válidos.

## Requisitos e aceite

- **FR-001** — `skills install` instala `AGENTS.md`, as skills e o registro no diretório de trabalho para o(s) alvo(s) escolhido(s).
- **AC-001** — Dado um diretório vazio, quando `skills install --target codex` roda, então existem `AGENTS.md` com o bloco gerenciado, `.agents/skills/seller-adapt/SKILL.md` e `.vendedor-workspace.json`, e não existe `.claude/`.
- **AC-002** — Dado um diretório vazio, quando `skills install --target claude` roda, então existem `.claude/skills/seller-adapt/SKILL.md` e `CLAUDE.md` contendo `@AGENTS.md`, e não existe `.agents/skills/`.
- **AC-003** — Dado um `AGENTS.md` do usuário sem marcadores, quando `skills install` roda, então o texto original permanece byte a byte no início e o bloco gerenciado é acrescentado; uma segunda execução não duplica o bloco e preserva texto que o usuário escreveu após o bloco.
- **AC-004** — Dado um `SKILL.md` instalado que o usuário editou, quando `skills install` roda, então o arquivo editado é mantido e aparece em `skipped` com motivo `modified`; com `--force` é substituído.
- **AC-005** — Dado um workspace já instalado e sem mudanças, quando `skills install` roda de novo, então nenhum arquivo é reescrito e `written` é vazio; `--dry-run` em workspace vazio lista os arquivos e não cria nenhum.
- **AC-006** — Dado o catálogo, quando `skills list` roda, então incluem-se `seller-adapt`, `seller-tune-conversation`, `seller-evaluate-and-tune`, `seller-connect-channel`, `seller-pilot-readiness` e `seller-extend-runtime` com audiência `developer-adaptation`, `skills doctor` reporta `ok` e `SkillCatalog.select` nunca escolhe uma delas.
- **AC-007** — Dado `vendedor init --agents codex --workspace DIR`, quando roda, então o banco é criado e os arquivos do alvo aparecem em `DIR`; sem `--agents`, nada é escrito em `DIR`.
- **AC-008** — Dado `skills status` após editar uma skill e apagar outra, quando roda, então reporta `modified` e `missing` por arquivo e `outdated` quando a versão do pacote instalado difere da registrada.
- **AC-009** — Dado o texto de todas as skills instaladas e do modelo de `AGENTS.md`, quando verificados, então cada comando `vendedor <grupo> <sub>` citado existe no parser da CLI, cada chave de pacote citada existe no schema e nenhum contém segredo ou telefone real.
- **AC-010** — Dado uma wheel construída, quando inspecionada, então contém o modelo de `AGENTS.md` e as onze skills (`SKILL.md` e scripts) em `share/vendedor-adaptavel/skills`, e `skills install` funciona a partir dela.

## Leitura e mapa de alterações

- `src/sales_agent/workspace.py` → `AgentWorkspace` — instalação, registro, status; new.
- `src/sales_agent/resources/workspace/AGENTS.md`, `CLAUDE.md` — modelos; new.
- `src/sales_agent/skills.py` → `AUDIENCES` — audiência das novas skills; existing.
- `src/sales_agent/cli.py` → `command_skills_install`, `command_skills_status`, `command_init` — CLI; existing.
- `skills/seller-*`, `skills/sales-*` — conteúdo das skills; new/existing.
- `pyproject.toml`, `MANIFEST.in` — empacotamento; existing.
- `tests/test_agent_workspace.py` — testes; new.
- `README.md`, `AGENTS.md`, `docs/INSTALLATION.md`, `docs/CONFIGURATION.md`, `skills/README.md`, `CHANGELOG.md` — documentação; existing.

## Plano breve

Seam: CLI `main([...])` sobre diretório temporário real e o parser da CLI para AC-009. Abordagem: `AgentWorkspace` copia arquivos de `SkillCatalog` e do recurso de pacote, calcula SHA-256, e grava o registro; o bloco gerenciado usa marcadores HTML. Skills são texto puro que orientam o agente a usar a CLI existente, sem código novo no motor. Dependências: none.

## Sequência e tarefas

- [x] C-001 Escrever os testes AC-001 a AC-009 e observar red pelo motivo esperado (comando inexistente, skills ausentes).
- [x] C-002 Implementar `AgentWorkspace`, CLI e recursos; escrever as skills e o modelo de `AGENTS.md`.
- [x] C-003 Empacotar (AC-010), atualizar documentação, executar regressão completa e registrar evidência.

## Validação e evidência

Comando/procedimento: `python -m pytest -q tests/test_agent_workspace.py`, `python -m pytest -q`, `ruff check src tests`, `python -m build` e instalação da wheel em venv limpo seguida de `vendedor skills install --target all` em diretório vazio.

Resultado executado: EV-001 (AC-001 a AC-009: 14 testes novos, suíte completa 260 passed, ruff ok) e EV-002 (AC-010: wheel construída, instalada em venv limpo, `skills install --target all` grava 42 arquivos, `skills status` ok).

Limitações: a compreensão real da skill por Claude Code ou Codex não é testável de forma determinística aqui; o teste cobre estrutura, referências e instalação, não o comportamento do agente.

## Condição de retorno

Retornar se o contrato, símbolo, dependência ou decisão material não puder ser satisfeito sem ampliar o escopo.

## Estado

`change.md` é a fonte canônica deste esforço compacto. Não crie `tasks.md` ou tickets paralelos para esta mudança.
