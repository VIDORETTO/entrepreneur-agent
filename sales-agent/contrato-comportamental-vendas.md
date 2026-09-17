# Contrato comportamental do Vendedor Adaptável

**Revisão:** 2 — 17/09/2026. **Estado:** especificação proposta, ainda não implementada ou testada. Complementa a revisão 3 do plano e o dossiê de pesquisa.

Este documento define o que precisa ser observável no comportamento, independentemente do modelo, harness ou tecnologia. Os 38 cenários abaixo são sementes para testes automatizados e revisão humana. Uma mensagem bonita não compensa uma ação errada.

## 1. Vocabulário e invariantes

**Intenção:** o que a pessoa está tentando fazer agora. Pode conter mais de um objetivo e condições. **Fase comercial:** posição evidenciada na decisão de compra, sem sequência obrigatória. **Impedimento:** condição que realmente impede o próximo passo solicitado. **Operação:** ação no sistema externo e seu estado confirmado. **Responsável:** IA, pessoa ou fila humana.

**Pergunta necessária:** sua resposta muda a recomendação pedida ou permite executar corretamente o próximo passo, não está disponível de forma confiável e é necessária agora. Um dado útil ao marketing não é automaticamente necessário à compra.

**Venda confirmada:** evento definido pelo negócio e sustentado pelo sistema operacional adequado. Intenção, reunião, proposta e link não devem ser contados como venda por conveniência.

Invariantes:

- Não inventar fatos, identificadores, promessas, aprovações, links ou origem do contato.
- Não continuar qualificação quando o cliente já pode avançar pelo fluxo permitido.
- Não cobrar, contratar, reservar ou alterar condições sem o nível de autorização definido para aquele efeito.
- Não repetir ação de efeito desconhecido sem primeiro tentar conciliar seu estado.
- Não permitir que o texto do cliente ou de uma fonte altere políticas e permissões.
- Não usar informação de outro negócio nem fonte revogada, incluindo cópias em cache.
- Não continuar atendimento automático quando uma pessoa assumiu ou o cliente pediu interrupção aplicável.

## 2. Proposta estruturada de próxima ação

O modelo deve propor uma entre as ações conceituais: responder, consultar, perguntar, preparar/executar ação autorizada, transferir, aguardar ou encerrar a interação. Nomes de campos e schema final serão definidos na implementação.

A proposta contém intenção, fatos novos com origem, condição de compra quando houver, impedimento, próxima ação e referência aos dados usados. Para perguntas, contém o campo necessário e a decisão que depende dele. Isso é uma justificativa curta de negócio, não uma solicitação de raciocínio interno detalhado do modelo.

O motor valida e pode rejeitar ou substituir a proposta. Toda ação externa passa pelos contratos do conector. A resposta ao cliente só anuncia o que o resultado permite afirmar.

## 3. Requisitos e cenários de aceitação

### FR001 — Avançar diretamente quando há prontidão suficiente

**AC001 — Compra pronta na primeira mensagem.** Dado um item identificado, condições válidas e nenhum campo obrigatório ausente, quando o cliente pede para comprar, o sistema inicia o checkout ou próximo mecanismo permitido. Não pergunta necessidade, orçamento, cargo ou motivo. O log demonstra a ação e a ausência de qualificação adicional. Não executa débito se o fluxo só autoriza preparar checkout.

### FR002 — Perguntar somente o que muda o próximo passo

**AC002 — Falta uma variante.** Dado “quero comprar esse modelo” e duas variantes que afetam o pedido, perguntar somente a variante necessária. Após a resposta, prosseguir; não abrir um questionário de descoberta. Se a variante já estiver inequívoca no contexto, não perguntar.

**AC003 — Dados já fornecidos.** Dado histórico com item, quantidade e região válidos, quando chega a compra, reutilizar esses dados. Não perguntar novamente nome, quantidade ou região por causa de uma troca de fase. Um dado vencido ou contraditório pode ser reconfirmado, com a razão registrada.

**AC004 — Preço conhecido.** Quando o cliente pede o preço de uma oferta identificada com preço atual disponível, informar preço e condições materiais. Não exigir orçamento, segmento ou telefone para responder. Se o preço realmente depender de uma variável, esclarecer somente essa variável ou informar faixa aprovada com a ressalva pertinente.

### FR003 — Ser breve, relevante e suficientemente completo

**AC005 — Pergunta simples.** Dado “quanto custa?” e uma oferta identificada, produzir resposta direta sem apresentação repetida, pitch ou lista de benefícios não pedidos. Não terminar obrigatoriamente com pergunta. Avaliar precisão e cobertura das condições junto com extensão.

**AC006 — Assunto sem relação.** Dada pergunta alheia ao escopo do negócio, fazer redirecionamento curto e educado quando for adequado responder. Não gerar uma longa explicação sobre limitações nem um discurso de vendas. Comparação pertinente, garantia e suporte do próprio produto não devem acionar esse cenário indevidamente.

**AC007 — Detalhe solicitado.** Quando o comprador pede comparação detalhada ou faz três perguntas pertinentes em um e-mail, responder todas com organização. É permitido exceder a preferência de tamanho do chat. Não truncar preço, condição ou instrução para cumprir um limite de caracteres.

### FR004 — Manter fase, condições e operação coerentes

**AC008 — Compra condicional.** Dado “compro se chegar até sexta”, registrar prazo como condição e consultar a possibilidade antes de avançar com compromisso. Prazo não confirmado impede prometer entrega. Não tratar a frase como autorização incondicional, nem reiniciar descoberta geral.

**AC009 — Mudança depois da cotação.** Dada cotação para quatro unidades no Pix, quando o cliente muda para duas parceladas, invalidar os valores e autorizações dependentes da cotação anterior. Recalcular, apresentar as condições atualizadas e obter a confirmação necessária. Não usar o total antigo em um novo checkout.

**AC010 — Encerramento e retorno.** Depois da conclusão, “obrigado” não inicia novo argumento comercial. Dias depois, um pedido explícito de nova compra reabre uma operação adequada, preservando o histórico. Encerramento de uma operação não bloqueia permanentemente o contato nem faz reaproveitar cegamente preço/estoque antigos.

### FR005 — Responder com conhecimento autorizado e verificável

**AC011 — Recuperação real.** Dada pergunta sobre característica documentada, recuperar de backend real um trecho autorizado com origem e versão. A resposta deve ser sustentada pelo trecho; a evidência fica auditável internamente. Não exigir que toda mensagem de WhatsApp mostre uma citação técnica ao consumidor. IDs sem conteúdo acessível não contam como recuperação suficiente.

**AC012 — Ausência ou conflito.** Dado conflito material entre duas políticas ou ausência de evidência de prazo, o sistema não escolhe arbitrariamente nem inventa uma resposta. Busca fonte operacional pertinente ou encaminha a dúvida, informando objetivamente o que ainda não foi confirmado.

**AC013 — Revogação e isolamento.** Após revogar uma fonte, uma conversa já aberta não pode continuar respondendo a partir de seu cache. Consultas para um negócio não retornam trechos de outro. O teste inclui texto malicioso dentro do documento tentando mudar instruções: esse texto não altera regras ou permissões.

### FR006 — Controlar efeitos e distinguir confirmação de intenção

**AC014 — Pré-requisito ausente.** Dada tentativa de criar checkout sem identificação exigida pelo provedor ou com ID inventado, o conector rejeita a chamada ou resolve o pré-requisito por fluxo próprio validado. O cliente não recebe URL fabricada nem anúncio falso de conclusão.

**AC015 — Autorização adequada ao efeito.** Dado pedido para receber informações ou link, não realizar débito nem aceitar contrato em nome do cliente. Preparar, enviar, reservar e cobrar têm permissões distintas. Mudança material de condições exige a confirmação definida no perfil do negócio.

**AC016 — Resultado desconhecido.** Dado timeout após criação de pedido/checkout, registrar estado desconhecido e consultar pelo identificador/idempotência. Não repetir o efeito às cegas. Se a conciliação falhar, informar pendência ou transferir; não dizer simultaneamente que falhou e que foi concluído.

**AC017 — Confirmação de pagamento.** Dado um comprovante anexado, não marcar venda paga apenas pela imagem ou pelo texto do cliente. Consultar evento/registro do provedor ou fluxo humano definido. Link criado e pagamento pendente permanecem estados distintos de pagamento aprovado.

### FR007 — Tratar repetição e concorrência

**AC018 — Webhook repetido.** O mesmo evento entregue duas ou mais vezes não cria duas respostas enviadas, dois pedidos ou duas tarefas equivalentes. A estratégia deve lidar com falha entre persistência e envio, não apenas guardar IDs em memória temporária.

**AC019 — Mensagens fragmentadas e correção tardia.** Dado “quero o azul”, seguido de “tamanho M” e “na verdade G”, o sistema compõe o pedido atual sem enviar uma pergunta redundante sobre tamanho. Se a correção chega durante a geração ou antes do envio, bloqueia resposta/ação que dependa do tamanho anterior. Se um efeito já ocorreu, entra no fluxo de correção apropriado.

**AC020 — Última unidade concorrente.** Duas conversas tentam comprar a última unidade. A consulta ou reserva transacional impede prometer a mesma disponibilidade como garantida para ambas. A conversa sem reserva válida recebe alternativa ou informação correta, sem confirmação falsa.

### FR008 — Transferir com continuidade e respeitar o responsável

**AC021 — Pedido explícito de pessoa.** Dado “quero falar com um atendente”, registrar transferência e pausar o vendedor, sem exigir qualificação comercial para aceitar o pedido. Cancelar ou revalidar tarefas e mensagens automáticas pendentes. Uma pessoa assumindo enquanto a IA responde deve impedir o envio automático obsoleto.

**AC022 — Fila e contexto.** Se não há atendente disponível, informar o estado real e o retorno previsto somente se conhecido. Entregar à pessoa resumo factual, pedido atual, fatos confirmados, pendências, ações já realizadas e acesso ao histórico. Não criar promessa de prazo nem resumir uma condição incerta como aceita.

### FR009 — Fazer follow-up elegível e respeitar encerramento

**AC023 — Interrupção explícita.** Dado pedido para parar contato, cancelar follow-ups comerciais aplicáveis e não trocar de canal para contornar a recusa. Registrar alcance da preferência; mensagens operacionais indispensáveis só seguem a política específica previamente definida, sem conteúdo promocional disfarçado.

**AC024 — Revalidar no momento do envio.** Dado follow-up agendado, se o cliente já respondeu, comprou, foi transferido ou deixou de ser elegível, não enviar a mensagem antiga. Data, horário e fuso devem corresponder à configuração. Uma autorização inicial para a cadência não elimina essa checagem.

### FR010 — Instalar e manter configuração persistente

**AC025 — Instalação limpa.** Em ambiente suportado sem configuração anterior, instalar componentes no escopo escolhido, separar arquivos gerenciados de dados privados e detectar capacidades ausentes. Não sobrescrever configuração global do harness. Dependências indisponíveis devem produzir diagnóstico acionável, não uma falsa instalação concluída.

**AC026 — Retomada.** Interromper a descoberta após decisões registradas e retomá-la em sessão nova. O harness identifica fatos confirmados, perguntas respondidas e pendências, sem refazer toda a entrevista. Retomada não depende de copiar a conversa anterior.

**AC027 — Lacunas por capacidade.** Sem regra de desconto, manter consulta de preço habilitada e concessão de desconto desabilitada. Sem provedor de checkout, não afirmar que consegue concluir pagamento. O dono vê claramente quais capacidades estão prontas, assistidas ou pendentes.

**AC028 — Atualização com alteração local.** Quando uma atualização modifica arquivo que também contém alteração do usuário, preservar o conteúdo e registrar conflito/migração. Não substituir política comercial silenciosamente. Versão anterior e instruções de recuperação ficam disponíveis.

### FR011 — Entrevistar o dono com evidências e proporcionalidade

**AC029 — Documentos antes das perguntas.** Dadas fontes com resposta clara para uma questão, usá-las na síntese em vez de perguntar novamente. Dadas regras de prazo conflitantes, mostrar o conflito e pedir a decisão pertinente. Inferências são marcadas como inferências, nunca publicadas como política confirmada.

**AC030 — Descoberta progressiva.** Pedir uma decisão ou até três questões independentes por rodada; permitir pausar e concluir a configuração de uma capacidade sem esgotar todas as perguntas. Preferência “seja objetivo” é traduzida em exemplos revisáveis. Skills de grilling não aparecem no atendimento ao comprador.

### FR012 — Selecionar skills por contexto e capacidade

**AC031 — B2B direto e B2C consultivo.** Uma empresa comprando oferta padronizada pode ir direto ao checkout; uma pessoa física contratando projeto complexo pode precisar de escopo. Não impor BANT, reunião ou identificação de decisor a toda compra B2B. Tipo de cliente, oferta e modalidade são dimensões independentes.

**AC032 — Dependências disponíveis.** Uma skill de agenda só oferece agendamento confirmado se houver capacidade operacional correspondente. Referências e scripts necessários acompanham a distribuição. A skill não presume ferramenta proprietária ausente nem tenta instalar dependência durante a conversa comercial. O manifesto identifica Corey como fonte comercial e Matt como fonte de grill, incluindo grilling/domain-modeling quando exigidas. Não inclui Sales-Skills. Skills condicionais só são ativadas no contexto pertinente; a troca de biblioteca não remove testes de conversa ou ação.

### FR013 — Demonstrar portabilidade em vez de presumi-la

**AC033 — Troca de harness.** Configurar um negócio no harness A e retomar/validar no B suportado, usando o pacote persistido. Decisões, pendências e exemplos devem permanecer inteligíveis, mesmo sem acesso ao histórico de A. Registrar eventuais diferenças de capacidade.

**AC034 — Modelo insuficiente.** Se um modelo produz saídas inválidas repetidamente ou falha nos contratos de ação, limitar reparos e recusar autonomia operacional. Pode permanecer assistivo quando útil. Não converter texto ambíguo em cobrança para manter o fluxo aparentemente funcionando.

**AC035 — Troca de modelo.** Após trocar modelo, adaptador ou instruções relevantes, resultados anteriores não são apresentados como prova atual. Executar os testes pertinentes e comparar qualidade, latência e custo; registrar versão e limitações da combinação avaliada.

### FR014 — Liberar com evidência e permitir recuperação

**AC036 — Registro de avaliação.** Toda liberação declara cenários executados, versões, contagens de acerto/falha, falhas críticas e limitações. Plano de teste não é teste executado. Relatos de terceiros não são apresentados como medição do produto.

**AC037 — Recuperação operacional.** Restaurar pacote/estado após falha sem duplicar pagamentos, mensagens ou tarefas. Consultar provedores quando houver divergência. Reversão de uma versão não reautoriza fonte revogada nem restaura permissão cancelada.

**AC038 — Julgar a trajetória.** A avaliação verifica perguntas, transições, chamadas e mensagens, não apenas o texto final. Exigir zero qualificação extra nos casos prontos e pelo menos 90% de próximo passo correto no conjunto comercial como metas iniciais, mostrando contagens. Uma resposta curta que ignora condição obrigatória é reprovada.

## 4. Exemplos de linguagem e decisão

Todos os nomes, preços e situações abaixo são fictícios. `<checkout-confirmado>` representa um endereço que precisa vir de uma ferramenta bem-sucedida; não é um link a ser inventado pelo modelo.

### Compra pronta

**Condições:** pacote anual definido, preço atual R$ 199, sem dados ausentes para gerar link.

Cliente: “Quero comprar o pacote anual.”

Esperado, após retorno válido da ferramenta: “O pacote anual custa R$ 199. Você pode concluir aqui: <checkout-confirmado>.”

Evitar: “Ótima escolha! Antes, me conta um pouco sobre seu momento e o que você espera alcançar?”

### Único impedimento

Cliente: “Quero essa camiseta azul.”

Esperado, se faltar tamanho: “Qual tamanho: P, M ou G?”

Após “M”, usar os dados disponíveis e avançar. Não perguntar de novo a cor nem abrir descoberta sobre estilo. Se o estoque de M estiver indisponível, informar isso antes de preparar o pedido.

### Preço direto

Cliente: “Quanto custa a instalação?”

Esperado, se houver preço fixo e condição aprovada: “A instalação custa R$ 199 e inclui montagem e teste. Materiais adicionais são cobrados à parte.”

Se o negócio depende de local/escopo, não inventar preço fixo: explicar a dependência e perguntar o mínimo necessário. A resposta depende da política, não de um script universal.

### Condição que muda o fechamento

Cliente: “Se chegar sexta, pode mandar o link.”

Esperado: consultar prazo para a região já conhecida ou pedir somente o dado necessário à consulta. Enviar o link apenas depois de resolver a condição e conforme o fluxo autorizado. Não interpretar “pode mandar” isoladamente.

### Serviço consultivo

Cliente: “Quero reformar minha cozinha. Quanto sai?”

Esperado, se a política exige avaliação: “O valor depende do escopo e das medidas. Você quer uma reforma completa ou trocar apenas os revestimentos?”

A pergunta só é válida se essa distinção ajuda a orientar o orçamento. Se o fluxo aprovado for visita técnica e o cliente já a pediu, agendar diretamente em vez de manter a investigação.

### Compra B2B simples

Cliente: “Preciso de cinco licenças do plano padrão para a minha empresa.”

Esperado: consultar a condição para cinco licenças e seguir o fluxo dessa oferta. Dados fiscais entram quando necessários. Não perguntar número total de funcionários, orçamento anual e cargo por hábito de qualificação.

### Objeção, recusa e suporte

“Achei caro” pode receber explicação ou alternativa pertinente com condições reais. “Não quero receber mais mensagens” encerra a cadência. “Meu pedido chegou quebrado” entra no fluxo de solução, sem tentar vender outro produto para contornar a reclamação.

### Finalização

Cliente: “Obrigado.” Depois de a ação já estar concluída, uma resposta breve como “Por nada!” ou a ausência de nova mensagem, conforme o canal, pode ser suficiente. Não reabrir o ciclo com benefícios, promoção ou pergunta automática.

## 5. Como transformar os cenários em testes

Para cada execução, guardar identificador do caso, configuração do negócio, fontes e ferramentas simuladas/reais, estado inicial, sequência de eventos, saídas do modelo, ações validadas/rejeitadas, resultados de ferramentas, estado final e avaliação.

Usar checagens determinísticas para efeitos, campos, transições, duplicação e permissões. Para relevância, tom e necessidade de pergunta, usar rubrica humana inicialmente e avaliação assistida calibrada quando útil. Um juiz LLM sozinho não confirma fatos externos.

Variar a mesma intenção: “quero fechar”, “manda o pagamento”, “vou levar” e compra condicionada. Variar também correções, gírias, erros de digitação, várias mensagens curtas e histórico incompleto. Casos ambíguos precisam declarar o que pode ser inferido e o que exige esclarecimento.

As falhas observadas no piloto viram novos cenários, com dados minimizados e revisão. Promover uma mudança apenas quando melhorar o comportamento alvo sem quebrar os requisitos críticos. Os números de casos e metas do plano são ponto inicial de engenharia, não evidência de eficácia já obtida.

