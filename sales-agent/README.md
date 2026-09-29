<div align="center">

# Vendedor Adaptável

**Vendedor comercial configurável e local: o modelo interpreta a conversa, e um motor com estado em SQLite decide, autoriza e registra a evidência de cada resposta.**

[![CI](https://github.com/VIDORETTO/entrepreneur-agent/actions/workflows/sales-agent-ci.yml/badge.svg?branch=main)](https://github.com/VIDORETTO/entrepreneur-agent/actions/workflows/sales-agent-ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Status: alpha](https://img.shields.io/badge/status-alpha-orange)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue)](LICENSE)

[Sobre](#-sobre) · [Instalação](#-instalação) · [Início rápido](#-início-rápido) · [Uso](#-uso) · [Documentação técnica](#-technical-documentation) · [Contribuir](#-contribuindo)

</div>

## 📖 Sobre

O runtime mantém estado, políticas, permissões, cotação e efeitos em SQLite. O modelo interpreta a mensagem e propõe fatos, mas não autoriza cobrança, checkout, transferência ou uso de dados sem validação do motor. É pensado para o dono de um negócio que quer atender compradores com regras próprias, em conversas por CLI ou pelo Chatwoot, sem depender de um serviço externo para funcionar.

> **Estado do projeto:** alpha. O runtime local, o serviço Chatwoot e os simuladores são testados. Cobrança, gateway, agenda e equipe humana reais **não** estão conectados, e nada aqui deve ser tratado como pronto para produção sem a evidência descrita em [Canal e piloto](#canal-chatwoot-e-piloto-com-compradores-reais). A visão geral do repositório está no [README da raiz](../README.md).

## ✨ Recursos

- Quatro modalidades de demonstração: físico B2C, oferta B2B padronizada, serviço consultivo e produto digital.
- Entrevista do dono com checkpoint retomável e pacote comercial versionado (`export`, `diff`, `simulate`, `promote`, `restore`).
- Conhecimento com origem, versão e localização, isolado por negócio, com revogação aplicada na consulta.
- Pausa humana, recusa, correção de pedido e follow-up opt-in revalidado no envio.
- Serviço Chatwoot com HMAC com timestamp, eco, janela de 24 h do WhatsApp e anexos.
- Adaptador de modelo `openai` (Structured Outputs) e `openai-compatible`, além do adaptador local `rules-v1`.
- Outbox durável, backup e restauração do SQLite, conciliação de efeitos `unknown`.
- Avaliação com conjuntos `contract`, `dev` e `holdout`, repetição e `pass^k`.
- Privacidade local: exportação, eliminação e expurgo por retenção.
- `vendedor skills install`: `AGENTS.md` e skills para Claude Code, Codex e similares.

## 🧠 Como funciona

1. A mensagem do comprador é gravada e o turno é montado.
2. O modelo devolve uma proposta estruturada (intenção e fatos); o motor a valida contra o pacote, o estado e as fontes aprovadas.
3. O efeito permitido (cotação, checkout preparado, transferência) é gravado com chave idempotente, e a resposta vai para a outbox.

Uma proposta inválida, uma recusa do provedor ou um resultado desconhecido nunca autorizam efeito comercial.

## 📋 Requisitos

- Python 3.11 ou superior.
- O módulo `sqlite3` da biblioteca padrão; nenhuma dependência de runtime.

## 📦 Instalação

```bash
git clone https://github.com/VIDORETTO/entrepreneur-agent.git
cd entrepreneur-agent/sales-agent
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
vendedor doctor
```

`doctor` informa capacidades disponíveis, diretório privado e a situação do Farol. Nenhuma chave é pedida ou armazenada. Para desenvolver, use `python -m pip install -e ".[dev]"`. Mais detalhes em [`docs/INSTALLATION.md`](docs/INSTALLATION.md).

## 🚀 Início rápido

```bash
vendedor examples
vendedor chat --business-id azul-b2c --conversation-id c1 \
  --contact-id verified:alice --event-id e1 \
  --message "Quero comprar a camiseta azul tamanho M, uma unidade para SP."
```

Resultado esperado: o preço e um link `checkout.invalid`, com `charged: false`. `verified:*` é só a identidade reconhecida pelo simulador; o link nunca representa cobrança real. Para as quatro modalidades: `vendedor demo` (usa uma base temporária; `--persist` mantém o estado em `--data-dir`).

## 🧑‍💻 Uso

### Configurar e retomar

O pacote privado fica em `.vendedor-data/` por padrão. Uma entrevista salva um checkpoint a cada resposta:

```bash
vendedor configure start --business-id minha-loja --template physical \
  --material briefing.txt
vendedor configure answer discovery-XXXXXXXX "Camiseta azul; sem acessórios"
vendedor configure status discovery-XXXXXXXX
# repetir `answer` para as próximas decisões
vendedor configure finalize discovery-XXXXXXXX
vendedor export-package --business-id minha-loja --output package.json
vendedor validate
```

A sessão pode ser retomada por outro processo ou agente pelo identificador e pelos artefatos SQLite; a conversa original não é necessária. `finalize` cria um rascunho seguro: sem preço, estoque ou fonte fictícia e com cotação/checkout pendentes. Revise o JSON exportado, preencha somente dados aprovados, altere `package_version`, declare `lifecycle: active` e promova:

```bash
vendedor promote-package package.json
```

Respostas livres da entrevista não viram autorização operacional por conta própria. `import-package` instala pacotes versionados que não fazem parte desse fluxo (por exemplo, um pacote ativo editado). Para instalar os negócios fictícios: `vendedor examples`. Detalhes em [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

### Usar com Claude Code, Codex ou outro agente

```bash
vendedor skills install --target all    # claude, codex ou all (ou: vendedor init --agents all)
vendedor skills status
```

Cria `AGENTS.md` e `CLAUDE.md` (que o importa) e as skills `seller-adapt`, `seller-tune-conversation`, `seller-evaluate-and-tune`, `seller-connect-channel`, `seller-pilot-readiness` e `seller-extend-runtime`, além das skills de configuração. Nada é sobrescrito: o texto seu no `AGENTS.md` e as skills que você editou são preservados; `vendedor skills status` mostra o que mudou e `--force` substitui. Comece pedindo ao agente: "use a skill seller-adapt".

### Conhecimento e Farol

O backend padrão `sqlite-farol-v1` é persistente e local e fornece conteúdo, origem, versão, localização e isolamento por negócio. A revogação vale na consulta, inclusive em conversas abertas:

```bash
vendedor knowledge query --business-id azul-b2c "quanto custa a camiseta"
vendedor knowledge revoke --business-id azul-b2c --source-id azul-catalogo
```

Artefatos gerados pelo Farol upstream podem ser importados de modo explícito:

```bash
vendedor farol import --business-id minha-loja ./artefato-farol
```

O comando lê `rag/documents` e preserva os locators como evidência persistente; isso não é apresentado como execução do RAG opcional upstream, que fica `not-executed` quando não configurado. Veja [`docs/FAROL-INTEGRATION.md`](docs/FAROL-INTEGRATION.md).

### Avaliação

```bash
vendedor model-check
vendedor evaluate --output reports/evaluation-latest.json          # 38 cenários de contrato
vendedor evaluate --split dev --repeat 4 --output reports/dev.json # conjunto de desenvolvimento
```

O relatório traz contagens por caso, `pass@1`, `pass^k`, falhas críticas, custo e latência, e separa o adaptador determinístico, o backend local e as integrações ainda não validadas. O conjunto reservado (`--split holdout`) só deve ser executado ao final e nunca usado para ajustar o pacote. Veja [`docs/EVALUATION.md`](docs/EVALUATION.md).

### Canal Chatwoot e piloto com compradores reais

`vendedor serve --config service.json` recebe e entrega mensagens pelo Chatwoot (`/webhook`, `/healthz`, `/readyz`). O piloto começa em `observation`, passa por `assistance` e só chega a `pilot` quando `vendedor pilot readiness` aceita a evidência de modelo real (holdout e `model-check`), contrato do canal, horário de atendimento, privacidade e interrupção exercitada. Configuração e operação em [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

### Operação durável

O SQLite tem migração versionada, verificação de integridade e backup consistente. A restauração exige preservar o estado atual em outro arquivo:

```bash
vendedor storage check
vendedor storage backup ./backup.sqlite3
vendedor storage restore ./backup.sqlite3 --backup-current ./antes-da-restauracao.sqlite3
```

Respostas ficam em uma outbox com lease, retry e dead-letter. Um worker usa `outbox claim`, entrega a mensagem e finaliza com `outbox ack`; falhas comprovadamente transitórias usam `outbox nack`. `outbox recover` move leases expirados para `unknown`, pois o resultado no provedor é ambíguo e não deve ser reenviado automaticamente.

```bash
vendedor outbox claim --limit 10 --lease-seconds 60
vendedor outbox ack CHAVE
vendedor outbox nack CHAVE --error "falha transitória"
vendedor outbox recover
```

Depois de consultar o provedor, finalize um item `unknown` com `outbox reconcile` e uma justificativa estruturada:

```bash
vendedor outbox reconcile CHAVE --resolution sent \
  --details '{"provider":{"provider_id":"message-exemplo"},"reason":"confirmado no provedor fictício"}'
```

Efeitos `unknown` nunca são repetidos automaticamente. Registre a evidência com `effects reconcile`: uma confirmação de checkout exige `checkout_id`, URL e `charged: false`, e uma falha libera a reserva local de estoque uma única vez.

```bash
vendedor effects list --status unknown
vendedor effects reconcile CHAVE --resolution confirmed \
  --details '{"checkout_id":"co_exemplo","url":"https://checkout.invalid/co_exemplo","charged":false}'
```

## 🛠️ Solução de problemas

| Sintoma | O que fazer |
|---|---|
| `requires a different Python: ... not in '>=3.11'` | Use Python 3.11 ou superior. |
| Dúvida sobre o ambiente | `vendedor doctor` e `vendedor skills doctor`. |
| `vendedor evaluate` termina com código 2 | Limiares de `evaluation/thresholds.json` não atendidos; leia o relatório. |
| `vendedor pilot configure --mode pilot` termina com código 2 | Falta prova no portão de prontidão; rode `vendedor pilot readiness`. |

---

# 🔧 Technical Documentation

## 🏗️ Visão técnica

Python 3.11+ sem dependências de runtime; SQLite (WAL, esquema versionado, busca BM25 via FTS5 quando disponível); serviço WSGI da biblioteca padrão para o webhook; adaptador HTTP via `urllib`. Testes com pytest e lint com ruff. Decisão de arquitetura em [`docs/adr/0001-runtime-local-portable.md`](docs/adr/0001-runtime-local-portable.md). O relógio é injetável (`SystemClock` por padrão; `FixedClock` nos testes), e as regras de vigência do conhecimento o usam.

## 📁 Estrutura do projeto

```text
sales-agent/
├── src/sales_agent/   # estado, política, adaptadores, conhecimento, canal, avaliação e CLI
├── tests/             # testes de comportamento pela interface pública
├── skills/            # skills de configuração, conversa e adaptação
├── evaluation/        # conjuntos dev, holdout e de recuperação, limiares
├── schemas/           # contratos JSON do pacote e do evento
├── examples/          # negócios fictícios e trajetórias demonstráveis
├── docs/              # instalação, configuração, operação, avaliação, release
├── reports/           # evidência de avaliação gerada localmente
└── specs/             # esforços de desenvolvimento, critérios de aceite e evidências
```

## 🧑‍🔧 Desenvolvimento

| Comando | Finalidade |
|---|---|
| `python -m pip install -e ".[dev]"` | Instala com as ferramentas de desenvolvimento |
| `python -m pytest -q` | Suíte de testes |
| `python -m pytest -q --clock-shift-days=400` | Suíte com a data do processo avançada 400 dias |
| `ruff check .` | Lint |
| `python -m build` e `python -m twine check dist/*` | Distribuição |

## 🔁 CI/CD

O workflow [`sales-agent-ci.yml`](../.github/workflows/sales-agent-ci.yml) roda `vendedor doctor`, `ruff`, `pytest --cov`, `vendedor demo`, `vendedor model-check` e `vendedor evaluate` em Python 3.11 e 3.14, além de build da distribuição, suíte com relógio deslocado e verificação de que o Python 3.10 é recusado. Não há etapa de publicação.

## ⚠️ Limitações

- Sem cobrança real: o comércio é simulado e `charged` é sempre `false`.
- Sem agenda nem equipe humana conectadas; o Chatwoot é o único canal implementado.
- Sem equivalência declarada com qualquer modelo remoto: uma combinação remota só deve ser liberada depois de executar seus testes de capacidade e registrar versão, latência, custo e falhas.
- A integração com o Farol estável está bloqueada até haver versão e cliente publicados.

---

## 🗺️ Roadmap

Veja [`roadmap.md`](roadmap.md).

## 🤝 Contribuindo

Consulte [`CONTRIBUTING.md`](CONTRIBUTING.md) e o [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Vulnerabilidades seguem o canal de [`SECURITY.md`](SECURITY.md), sem dados reais, credenciais ou conversas de clientes em issues públicas.

## 💬 Suporte

[Issues do GitHub](https://github.com/VIDORETTO/entrepreneur-agent/issues).

## 📜 Versões

Veja o [`CHANGELOG.md`](CHANGELOG.md).

## 🙏 Agradecimentos

Referências externas com licença MIT e revisão fixada em [`manifest.json`](manifest.json); atribuições em [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## 📄 Licença

Distribuído sob a licença MIT. Veja [`LICENSE`](LICENSE).
