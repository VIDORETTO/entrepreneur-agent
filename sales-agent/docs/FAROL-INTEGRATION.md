# Integração verificável com Farol

O adaptador aceita o artefato produzido pelo Farol upstream, em vez de tratar
um identificador de evidência como conteúdo. A prova executada em 17/09/2026
usou a revisão registrada no manifesto e o fixture `documents/fixtures/acme-docs`:

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

O comando upstream terminou com código 0 e produziu dois documentos. A
importação local retornou trecho, locator, versão e negócio; veja
`reports/farol-artifact-integration.json`. O RAG opcional `knowledge-rag`/MCP
não foi instalado nesta prova, portanto não é anunciado como integração de
produção. `sqlite-farol-v1` é um backend persistente local do produto, não o
backend RAG upstream.
