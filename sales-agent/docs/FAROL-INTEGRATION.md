# Integração verificável com Farol

O adaptador aceita um artefato produzido pelo Farol upstream, em vez de tratar
um identificador de evidência como conteúdo. O relatório abaixo é um registro
histórico de 17/09/2026, com fixture sintética; o comando upstream não foi
reexecutado nesta sessão e não fixa o contrato da versão estável do Farol. Os
testes locais de governança do artefato foram reexecutados e estão registrados
no campo `current_local_verification`. O comando histórico usou o fixture
`documents/fixtures/acme-docs`:

```bash
python3.12 -m venv /tmp/farol-venv
/tmp/farol-venv/bin/pip install --no-deps -e /caminho/para/farol-rag-skill-docs
/tmp/farol-venv/bin/python -m docops run \
  /caminho/para/farol-rag-skill-docs/documents/fixtures/acme-docs \
  --output /tmp/acme-artifact --slug acme --license MIT \
  --redistribution private-only
vendedor farol import --business-id acme-demo /tmp/acme-artifact
vendedor knowledge query --business-id acme-demo "API"
```

O registro histórico informa que o comando upstream terminou com código 0 e
produziu dois documentos. A importação local registrada retornou trecho,
locator e negócio; veja `reports/farol-artifact-integration.json`. O RAG
opcional `knowledge-rag`/MCP não foi instalado ou executado nesta sessão,
portanto não é anunciado como integração estável ou de produção.
`sqlite-farol-v1` é um backend persistente local do produto, não o backend RAG
upstream.

Artefatos com `rag/sources.json` usam manifesto, geração, revisão, hashes,
vigência e revogações antes da promoção atômica. Um artefato legado que só tem
`rag/documents` recebe o modo `legacy-migration` e uma revisão derivada do hash
do documento; o relatório identifica essa migração e ela não é evidência do
contrato Farol estável. `vendedor farol status` permanece `blocked` até que a
versão estável e seu cliente executável sejam disponibilizados.
