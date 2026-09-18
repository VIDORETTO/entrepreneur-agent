# Changelog

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
projeto pretende adotar versionamento semântico após estabilizar a API pública.

## [Não lançado]

### Adicionado

- Verificação de distribuição, documentação de contribuição, segurança e
  processo de liberação.
- Proteção POSIX para o diretório de estado e o arquivo SQLite.
- Validação de preço, estoque e campos obrigatórios do pacote comercial.
- Exportação de pacotes e rascunho seguro após a entrevista, sem promover texto
  livre ou valores fictícios a regra operacional.
- Escrita otimista por versão para impedir que um worker obsoleto sobrescreva
  o estado mais novo de uma conversa.
- Migração versionada do SQLite, verificação de integridade, backup e
  restauração com cópia de segurança obrigatória.
- Commit atômico de conversa, evento e outbox; entrega com lease, retry,
  recuperação e dead-letter.
- Reserva atômica de efeito e estoque, além de conciliação explícita com
  compensação idempotente e atualização da conversa.
- Promoção explícita de rascunhos revisados e limites para eventos, materiais,
  fontes e artefatos Farol.
- Testes multiprocesso para evento duplicado e disputa pela última unidade.

### Corrigido

- `vendedor validate` agora falha quando não há negócio instalado, evitando um
  resultado positivo sem configuração para validar.
- O adaptador HTTP rejeita `facts` fora do contrato estruturado.
- Cotação e proposta agora respeitam a capacidade estruturada `quote`.
- Consulta de catálogo/conhecimento, transferência e follow-up agora respeitam
  suas capacidades estruturadas antes de produzir ações ou afirmações.
- O manifesto embarcado volta a preservar a lista de skills e a procedência do
  manifesto do repositório.
- O adaptador HTTP agora exige HTTPS fora de localhost, limita timeout,
  tentativas e resposta, e valida estritamente o envelope retornado.
- Status e identificadores persistentes não podem mais ser sobrescritos por
  campos homônimos do payload; conciliação também protege os metadados da
  reserva de estoque.

## [0.1.0] - 2026-09-17

### Adicionado

- Runtime local com CLI, SQLite, configuração retomável, quatro exemplos
  fictícios e 38 cenários executáveis do contrato comportamental.
- Backend de conhecimento persistente e importador explícito de artefatos do
  Farol.
