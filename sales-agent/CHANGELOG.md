# Changelog

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
projeto pretende adotar versionamento semântico após estabilizar a API pública.

## [Não lançado]

### Adicionado

- `vendedor skills install` e `skills status`, `vendedor init --agents`: instalam
  `AGENTS.md` (bloco gerenciado), `CLAUDE.md` e skills em `.claude/skills/` ou
  `.agents/skills/`, sem sobrescrever edições do usuário.
- Seis skills de adaptação para agentes de código (`seller-adapt`,
  `seller-tune-conversation`, `seller-evaluate-and-tune`,
  `seller-connect-channel`, `seller-pilot-readiness`, `seller-extend-runtime`)
  e atualização de `sales-setup` e `sales-simulate`.
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
  recuperação segura para `unknown` em lease expirado, conciliação explícita e
  dead-letter.
- Reserva atômica de efeito e estoque, além de conciliação explícita com
  compensação idempotente e atualização da conversa.
- Promoção explícita de rascunhos revisados e limites para eventos, materiais,
  fontes e artefatos Farol.
- Catálogo versionado de skills, referências instaláveis, seleção por público e
  orçamento de contexto, sem conceder permissões por prompt.
- Entrevista de configuração retomável, estados de decisão, inspeção, diff,
  simulação isolada e restauração como nova versão.
- Turnos duráveis, entrada Chatwoot autenticada por contrato, entrega
  revalidada, modos de observação/assistência/piloto e métricas estruturadas.
- Supervisor desligado por padrão, relatório agregado e uma correção seletiva
  com revalidação de candidato original, estado, pacote e evidência; comparação
  de baseline e supervisão usa o mesmo denominador.
- Migração de fontes antigas para `pending_review`, objeções com condições
  aprovadas, preferências configuradas e políticas opcional/obrigatória do
  supervisor.
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
- O relatório de avaliação passou a verificar a cobertura integral dos 38 casos
  do golden set e mantém integrações remotas como `not-executed` quando não há
  execução correspondente.
- A elegibilidade de entrega e piloto agora também vincula o fingerprint do
  pacote, impedindo que uma edição com `package_version` reutilizada herde uma
  avaliação ou outbox anterior.
- Reservas de piloto passaram a ser persistentes, idempotentes e liquidadas
  uma única vez, mantendo custos fracionários e resultados `unknown` como
  pendência até conciliação.
- Reservas genéricas expiradas agora viram `unknown` e propostas em andamento
  nunca são apresentadas como preparadas; fontes removidas de um pacote deixam
  de ser recuperáveis sem apagar seu histórico.
- Promoção de conhecimento exige revisão explícita; importações Farol rejeitam
  intervalos de vigência inválidos e duas revisões ativas no mesmo escopo.
- Supervisor obrigatório em modo `off`/`observation` falha fechado, e timeout
  do revisor fica persistido como estado `timeout`.
- O transporte Chatwoot bloqueia redirecionamentos fora da origem autorizada,
  e mensagens admitidas pelo webhook podem usar a identidade externa do contato
  sem transformar `verified:*` em autenticação de produção.

## [0.1.0] - 2026-09-17

### Adicionado

- Runtime local com CLI, SQLite, configuração retomável, quatro exemplos
  fictícios e 38 cenários executáveis do contrato comportamental.
- Backend de conhecimento persistente e importador explícito de artefatos do
  Farol.
