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

A configuração não pede senhas. Capacidades sem integração permanecem
`disabled`/`pending`; isso não impede capacidades independentes, como consultar
uma oferta sem cobrar.

O produto diferencia:

- fatos confirmados, inferidos e conflitantes;
- fase comercial, prontidão, impedimento, operação e responsável;
- documento, dado operacional e memória da conversa;
- preparar/enviar/reservar/cobrar e seus resultados.
