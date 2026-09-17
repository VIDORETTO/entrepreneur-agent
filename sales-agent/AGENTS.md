# Instruções locais

## Verificação rápida

```bash
python3 -m pip install -e .
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
