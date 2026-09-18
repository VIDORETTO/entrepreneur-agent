# Vendedor Adaptável

Primeira versão local e instalável de um vendedor comercial configurável. O
runtime mantém estado, políticas, permissões, cotação e efeitos em SQLite; o
modelo interpreta a mensagem e propõe fatos, mas não autoriza cobrança,
checkout, transferência ou uso de dados sem validação.

> **Estado do projeto:** alpha demonstrável. O runtime local e os simuladores
> são testados; integrações de canal, pagamento, agenda e transferência humana
> ainda não são produção e não devem ser tratadas como tal.

## Instalação

Requer Python 3.9 ou superior. A instalação base não precisa de serviço externo:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
vendedor doctor
```

`doctor` informa capacidades disponíveis, diretório privado e a situação do
Farol. Nenhuma chave é pedida ou armazenada pelo briefing.

## Configurar e retomar

O pacote privado fica em `.vendedor-data/` por padrão. Uma entrevista salva um
checkpoint a cada resposta:

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

A sessão pode ser retomada com outro processo ou harness por seu identificador e
pelos artefatos SQLite; a conversa original não é necessária. `finalize` cria um
rascunho seguro: sem preço, estoque ou fonte fictícia e com cotação/checkout
pendentes. Revise o JSON exportado, preencha somente dados aprovados, altere o
`package_version`, declare `lifecycle: active` e promova explicitamente:

```bash
vendedor promote-package package.json
```

Respostas livres da entrevista não viram autorização operacional por conta
própria. `import-package` continua disponível para instalar pacotes versionados
que não fazem parte desse fluxo de promoção.

Para instalar os quatro negócios fictícios usados na demonstração:

```bash
vendedor examples
```

## Demonstração reproduzível

Os nomes e preços abaixo são fictícios e estão no código de exemplos. A saída
mostra quatro modalidades: físico B2C, oferta B2B padronizada, serviço
consultivo e produto digital.

```bash
vendedor demo
```

Por padrão a demonstração usa uma base temporária para poder ser repetida sem
herdar estoque ou eventos anteriores; use `vendedor demo --persist` se quiser
inspecionar esse estado em `--data-dir`.

Também é possível dirigir uma conversa individual:

```bash
vendedor chat --business-id azul-b2c --conversation-id c1 \
  --contact-id verified:alice --event-id e1 \
  --message "Quero comprar a camiseta azul tamanho M, uma unidade para SP."
```

`verified:*` é somente a identidade reconhecida pelo simulador. O link
`checkout.invalid` demonstra preparação de checkout e nunca representa cobrança
real. O adaptador registra `charged: false`.

## Conhecimento e Farol

O backend padrão `sqlite-farol-v1` é persistente, local e fornece conteúdo,
origem, versão, localização e isolamento por negócio. Revogação é aplicada na
consulta, inclusive para conversas já abertas:

```bash
vendedor knowledge query --business-id azul-b2c "quanto custa a camiseta"
vendedor knowledge revoke --business-id azul-b2c --source-id azul-catalogo
```

Artefatos gerados pelo Farol upstream podem ser importados de modo explícito:

```bash
vendedor farol import --business-id minha-loja ./artefato-farol
```

O comando lê `rag/documents` e preserva locators como evidência persistente;
isso não é apresentado como execução do RAG opcional upstream. A validação
upstream do Farol requer Python 3.11+ e sua dependência opcional, e fica
registrada como `not-executed` quando não estiver configurada.

## Avaliação

```bash
python -m pip install -e ".[dev]"
vendedor model-check
vendedor evaluate --output reports/evaluation-latest.json
python -m pytest -q
```

O avaliador executa os 38 cenários AC da especificação, com contagens e falhas
individuais. O relatório separa o adaptador determinístico, o backend local
persistente e as integrações ainda não validadas. A cobertura inclui compra
pronta, pergunta única, preço direto, alteração de cotação, deduplicação,
correção, timeout desconhecido, humano, recusa, revogação, isolamento,
retomada, quatro modalidades e modelo incapaz de cumprir o contrato.

## Operação durável

O estado SQLite possui migração versionada, verificação de integridade e backup
consistente. A restauração exige preservar o estado atual em outro arquivo:

```bash
vendedor storage check
vendedor storage backup ./backup.sqlite3
vendedor storage restore ./backup.sqlite3 --backup-current ./antes-da-restauracao.sqlite3
```

Respostas ficam em uma outbox com lease, retry e dead-letter. Um worker deve
usar `outbox claim`, entregar a mensagem e finalizar com `outbox ack`; falhas
usam `outbox nack`. `outbox recover` devolve leases expirados à fila.

```bash
vendedor outbox claim --limit 10 --lease-seconds 60
vendedor outbox ack CHAVE
vendedor outbox nack CHAVE --error "falha transitória"
vendedor outbox recover
```

Efeitos `unknown` nunca são repetidos automaticamente. Depois de consultar o
provedor, registre a evidência com `effects reconcile`. Uma confirmação de
checkout exige `checkout_id`, URL e `charged: false`; uma falha libera a reserva
local de estoque uma única vez.

```bash
vendedor effects list --status unknown
vendedor effects reconcile CHAVE --resolution confirmed \
  --details '{"checkout_id":"co_exemplo","url":"https://checkout.invalid/co_exemplo","charged":false}'
```

## Estrutura e limites

- `src/sales_agent/`: estado, política, adaptadores, conhecimento, configuração e CLI.
- `examples/`: negócios fictícios e trajetórias demonstráveis.
- `skills/`: pacotes portáteis de configuração/simulação com referências, exemplos e scripts.
- `schemas/`: contratos JSON mínimos para pacote e evento.
- `tests/`: testes de comportamento pela interface pública.
- `reports/`: evidência de avaliação gerada localmente.

Para contribuir, consulte [`CONTRIBUTING.md`](CONTRIBUTING.md). Vulnerabilidades
devem seguir o canal descrito em [`SECURITY.md`](SECURITY.md), sem incluir dados
reais, credenciais ou conversas de clientes em issues públicas. A participação
também segue o [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

Não há canal real, cobrança, gateway, agenda ou equipe humana conectados. Não há
promessa de equivalência com qualquer modelo remoto. Uma combinação remota só
deve ser liberada após executar seus testes de capacidade e registrar versão,
latência, custo e falhas.
