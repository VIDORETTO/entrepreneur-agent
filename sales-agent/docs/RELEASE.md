# Checklist de liberação

Uma release só está pronta quando todos os itens abaixo têm evidência na revisão
que será marcada. Não reutilize relatório de outro commit.

1. Confirme que a versão é igual em `pyproject.toml`, `manifest.json`,
   `src/sales_agent/resources/manifest.json` e `sales_agent.__version__`.
2. Atualize `CHANGELOG.md` e mantenha as limitações do README explícitas.
3. Execute `ruff check .` e `python -m pytest -q --cov` na matriz Python 3.9/3.12.
4. Execute `vendedor doctor`, `vendedor demo`, `vendedor model-check` e
   `vendedor evaluate --output reports/evaluation-latest.json`.
   O relatório final deve registrar a revisão base e `run.source.dirty` deve
   ser `false`; gere-o a partir de uma árvore limpa. O commit posterior pode
   conter somente a atualização desse relatório antes da tag.
5. Construa sdist e wheel com `python -m build` e valide com
   `python -m twine check dist/*`.
6. Instale a wheel em um ambiente virtual limpo e repita `vendedor doctor` e
   `vendedor demo` fora do checkout do repositório.
7. Confira o conteúdo da wheel: licença, referências, schemas, skills e
   manifesto devem estar presentes.
8. Faça uma busca por segredos e confirme que exemplos e relatórios só contêm
   dados fictícios.
9. Só publique integrações externas como validadas quando o backend real e a
   evidência correspondente estiverem registrados no relatório.

O workflow `sales-agent-ci.yml` executa testes e valida a distribuição, mas não
publica pacotes nem cria releases automaticamente.
