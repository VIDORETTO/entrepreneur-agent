# Contexto do Vendedor Adaptável

Glossário do domínio comercial usado pelo runtime e pelos testes. O arquivo descreve linguagem do produto, não sua implementação.

## Conversa e decisão

**Comprador**:
Pessoa ou organização que manifesta uma necessidade ou intenção em uma conversa comercial.
_Evitar_: lead, prospecto, usuário (quando o papel comercial for o que importa)

**Dono**:
Pessoa responsável por configurar, aprovar e manter o negócio atendido pelo sistema.
_Evitar_: comprador, administrador (quando a decisão comercial estiver em jogo)

**Intenção**:
O que o comprador está tentando fazer agora, possivelmente com uma condição explícita.
_Evitar_: fase, prontidão (são dimensões diferentes)

**Impedimento**:
Condição que realmente bloqueia o próximo passo solicitado, como variante ausente ou prazo não confirmado.
_Evitar_: qualquer informação útil ao marketing

**Pergunta necessária**:
Pergunta cuja resposta muda a recomendação pedida ou permite executar corretamente o próximo passo, não está disponível de forma confiável e é necessária agora.
_Evitar_: pergunta de qualificação, pergunta de curiosidade

**Fase comercial**:
Posição evidenciada na decisão de compra, sem representar sozinha operação, intenção ou responsável.
_Evitar_: funil (quando não houver sequência obrigatória)

**Operação**:
Ação externa ligada à oportunidade e o resultado confirmado, pendente, falho ou desconhecido dessa ação.
_Evitar_: venda (nem toda operação é venda confirmada)

**Venda confirmada**:
Evento definido pelo negócio e sustentado pelo sistema operacional adequado; intenção, proposta ou checkout não bastam.
_Evitar_: conversão para qualquer próximo passo

## Configuração e conhecimento

**Pacote comercial**:
Versão aprovada de perfil, ofertas, políticas, capacidades, fontes, skills e exemplos usados pelo vendedor.
_Evitar_: prompt, memória do modelo

**Fonte**:
Documento ou registro aprovado que pode sustentar uma afirmação, com escopo, versão e vigência conhecidos.
_Evitar_: evidência (evidência é o trecho recuperado)

**Evidência**:
Trecho recuperado de uma fonte autorizada, com origem e versão auditáveis.
_Evitar_: citação sem conteúdo

**Checkpoint**:
Estado persistente da configuração, com decisões, lacunas, conflitos e próxima pergunta prioritária.
_Evitar_: histórico bruto da conversa

**Capacidade**:
Ação que o sistema pode consultar, preparar, enviar, reservar, cobrar, transferir ou executar sob uma política explícita.
_Evitar_: skill (skill orienta; capacidade define autorização)
