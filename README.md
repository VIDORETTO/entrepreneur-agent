# entrepreneur-agent

Monorepo do **Vendedor Adaptável**: um vendedor comercial configurável, com
estado, políticas, permissões, cotação e efeitos num motor local (SQLite). O
modelo de linguagem interpreta a mensagem e propõe; o motor decide e autoriza.

| Caminho | Conteúdo |
|---|---|
| [`sales-agent/`](sales-agent/README.md) | o produto: runtime, CLI `vendedor`, skills, avaliação, documentação |
| `.github/` | CI (Python 3.11 e 3.14, rejeição de 3.10, build, relógio deslocado) e Dependabot |

## Começar

```bash
cd sales-agent
python3.12 -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
vendedor doctor
python -m pytest -q
```

Para usar com Claude Code, Codex ou outro agente de código, rode
`vendedor skills install` no seu projeto: ele cria o `AGENTS.md` e as skills de
adaptação. Detalhes em [`sales-agent/docs/INSTALLATION.md`](sales-agent/docs/INSTALLATION.md).

## Estado

Alpha demonstrável. O runtime local, o serviço Chatwoot, a janela de 24 h do
WhatsApp, a avaliação com conjunto reservado e a privacidade local são testados.
Pagamento real não existe nesta versão, e o piloto com compradores reais exige
evidência de modelo e canal reais (`vendedor pilot readiness`). Consulte
[`sales-agent/docs/OPERATIONS.md`](sales-agent/docs/OPERATIONS.md) e
[`sales-agent/SECURITY.md`](sales-agent/SECURITY.md).

## Licença

MIT. Veja [`sales-agent/LICENSE`](sales-agent/LICENSE).
