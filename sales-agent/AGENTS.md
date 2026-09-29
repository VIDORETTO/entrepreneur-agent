# Instruções locais

## Verificação rápida

```bash
python3.12 -m pip install -e .
vendedor doctor
python -m pip install -e ".[dev]"
python -m pytest -q
vendedor demo
vendedor evaluate --output reports/evaluation-latest.json
```

Não use dados reais ou segredos nos exemplos. O runtime deve manter políticas,
permissões e validações no código/estado estruturado; prompts são apenas uma
entrada de interpretação. Antes de afirmar integração de produção, confira o
backend e a evidência correspondente no relatório.

## Adaptar o vendedor com um agente de código

Quem usa Claude Code, Codex ou outro agente compatível com `AGENTS.md` recebe as
regras e as skills de adaptação com um comando, no diretório do projeto:

```bash
vendedor skills install --target all     # claude, codex ou all
vendedor skills status                   # modificado, ausente ou desatualizado
```

O comando grava `AGENTS.md` (bloco gerenciado entre marcadores; o texto fora
dele nunca é alterado), `CLAUDE.md` (importa o `AGENTS.md`) e as skills em
`.claude/skills/` ou `.agents/skills/`. Um arquivo editado pelo usuário é
preservado, salvo `--force`. O modelo do `AGENTS.md` distribuído fica em
`src/sales_agent/resources/workspace/AGENTS.md`; as skills de adaptação
(`seller-adapt` e as demais `seller-*`) ficam em `skills/`. Mudanças nelas
seguem o esforço `specs/002-skills-adaptacao-agente` e são cobertas por
`tests/test_agent_workspace.py`, que confere que todo comando e chave de pacote
citados existem.
