# Configuração do dono

`configure start` lê materiais fornecidos, registra indícios com origem e cria
uma questão prioritária. Cada `answer` grava decisões e avança o cursor. Uma
sessão nova consulta o checkpoint, não repete a entrevista inteira. `finalize`
gera o pacote de negócio e ingere as fontes aprovadas no backend persistente.

A configuração não pede senhas. Capacidades sem integração permanecem
`disabled`/`pending`; isso não impede capacidades independentes, como consultar
uma oferta sem cobrar.

O produto diferencia:

- fatos confirmados, inferidos e conflitantes;
- fase comercial, prontidão, impedimento, operação e responsável;
- documento, dado operacional e memória da conversa;
- preparar/enviar/reservar/cobrar e seus resultados.
