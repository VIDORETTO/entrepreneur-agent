# Operação e limites

O conector inicial é um simulador: URL usa domínio inválido, `charged` é
sempre falso e pagamento só pode ser confirmado por um evento de provedor que
ainda não existe nesta versão. Timeout vira `unknown` e não é repetido às cegas.

A transferência grava fatos e estado, pausa o vendedor e deixa a retomada para
uma liberação explícita. Follow-up é opt-in e revalidado no momento do envio;
recusa, compra, transferência ou resposta tornam a tarefa inelegível.

Não publicar, fazer deploy, enviar mensagem, cobrar ou conectar sistemas reais
sem uma decisão específica e testes da integração correspondente.
