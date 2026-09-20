# Configuração do dono

`configure start` lê materiais fornecidos, registra indícios com origem e cria
uma questão prioritária. Cada `answer` grava decisões e avança o cursor. Uma
sessão nova consulta o checkpoint, não repete a entrevista inteira. `finalize`
gera um pacote em estado `draft`. Ele não transforma texto livre em preço,
estoque, fonte aprovada ou autorização: cotação, checkout e conhecimento ficam
`pending` até uma revisão estruturada.

Use `vendedor export-package --business-id ID --output package.json`, revise o
arquivo, incremente `package_version`, mude `lifecycle` para `active` somente
depois das aprovações e então execute `vendedor promote-package package.json`.
A promoção exige que o rascunho correspondente esteja instalado e preserva o
registro `owner_configuration`. Um pacote `draft` não pode
habilitar capacidades operacionais. A importação
valida tipos, preços, estoque, capacidades, fontes e versões antes de ativar a
nova versão. Materiais lidos pela entrevista continuam como indícios, não como
fonte aprovada silenciosamente.

O runtime calcula também um fingerprint SHA-256 do pacote persistido. Pilotos,
entregas pendentes e revisões seletivas conferem esse fingerprint no momento
da execução; editar o conteúdo mantendo a mesma `package_version` não herda
uma avaliação ou autorização anterior.

A configuração não pede senhas. Capacidades sem integração permanecem
`disabled`/`pending`; isso não impede capacidades independentes, como consultar
uma oferta sem cobrar.

Cada decisão da entrevista mantém estado `confirmed`, `inferred`,
`conflicting` ou `absent`. O checkpoint registra perguntas respondidas,
adiadas e o impedimento da capacidade escolhida. A versão finalizada do pacote
fica separada da versão de armazenamento, para que uma restauração seja uma
nova promoção auditável.

Use `vendedor skills list`, `vendedor skills show ID` e `vendedor skills doctor`
para verificar a instalação. O catálogo só expõe skills de atendimento ao
comprador e configuração do negócio; versão incompatível ou referência ausente
vira diagnóstico. Skills não concedem permissões e não entram no contexto do
comprador quando pertencem à configuração.

Para revisar uma proposta sem alterar o negócio ativo, use `configure inspect`,
`configure diff` e `configure simulate`. A simulação usa um SQLite temporário.
Uma restauração recebe uma nova versão por `configure restore --business-id ID
--storage-version N`; ela reaplica validação e mantém revogações de fontes.

Fontes encontradas em uma base anterior à governança de revisão recebem
`review_status=pending_review` e ficam fora da consulta até `knowledge review`
registrar motivo e autoridade. Isso evita escolher a revisão vigente pela ordem
lexicográfica.

O produto diferencia:

- fatos confirmados, inferidos e conflitantes;
- fase comercial, prontidão, impedimento, operação e responsável;
- documento, dado operacional e memória da conversa;
- preparar/enviar/reservar/cobrar e seus resultados.
