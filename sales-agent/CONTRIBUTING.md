# Contribuindo

Obrigado por melhorar o Vendedor Adaptável. O projeto está em alpha e prioriza
segurança operacional, rastreabilidade e afirmações verificáveis.

## Ambiente local

Use Python 3.9 ou superior em um ambiente virtual:

```bash
python -m pip install -e ".[dev]"
vendedor doctor
ruff check .
python -m pytest -q --cov
vendedor demo
vendedor evaluate --output reports/evaluation-latest.json
```

Antes de abrir um pull request, execute também:

```bash
python -m build
python -m twine check dist/*
```

## Regras para mudanças

- Não use dados reais, segredos, chaves ou conversas de clientes em código,
  exemplos, testes, commits ou issues.
- Políticas, permissões e validações pertencem ao código ou ao estado
  estruturado. Prompts podem interpretar texto, mas nunca autorizar efeitos.
- Uma integração só pode ser descrita como validada quando o backend foi
  executado e a evidência correspondente aparece no relatório.
- Mudanças de comportamento precisam de um teste que falhe sem a correção.
- Preserve compatibilidade com Python 3.9 e 3.12.

Pull requests devem explicar o comportamento alterado, os riscos e os comandos
de verificação executados. Alterações de escopo devem atualizar o README, o
plano de execução e o changelog quando aplicável.
