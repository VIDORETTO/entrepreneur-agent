# Atendimento configurável, conhecimento verificável e entrega controlada

Estado: proposta completa para revisão; interfaces de teste e divisão dos tickets aguardam confirmação. Este documento não é uma issue publicada e não autoriza implementação ou ativação em produção.

## Problem Statement

O comprador precisa receber respostas úteis, sustentadas por evidências pertinentes, sem repetir informações ou continuar recebendo mensagens automáticas após intervenção humana. O dono precisa adaptar o atendimento à sua realidade comercial. O developer que o auxilia com IA precisa descobrir e configurar ofertas, políticas, capacidades, fontes e skills internas usando interfaces verificáveis.

O runtime atual possui estado durável e autorização estruturada, mas suas skills não são carregadas efetivamente pelo atendimento. A busca pode devolver conteúdo relacionado sem responder à pergunta; versões conflitantes da mesma fonte coexistem; reimportação pode desfazer revogação; respostas pendentes podem sobreviver à pausa humana. A entrevista de configuração ainda é limitada e o conhecimento do Farol é importado sem seu contrato completo de governança.

## Solution

Entregar um atendimento configurável em que o developer, orientado por skills de configuração, prepara um pacote comercial, inspeciona diferenças, simula trajetórias e promove uma versão aprovada pelo dono. O comprador recebe respostas que atendem ao pedido, usam evidências autorizadas e preservam memória de correções e perguntas respondidas. O runtime controla capacidades, vigência, autorização e entrega independentemente do texto das skills.

Existirão somente dois públicos de skills: atendimento ao comprador e configuração do negócio. Não será criada skill para desenvolver, refatorar ou manter o código do sistema.

O Farol será responsável pela preparação e recuperação documental conforme sua versão estável publicada. O sistema manterá aprovação comercial, associação ao negócio e controle da resposta. Um adaptador Chatwoot permitirá validar o primeiro canal, inicialmente em observação e assistência; ativação pública será uma operação separada.

## User Stories

1. Como comprador, quero receber resposta à pergunta que fiz, para não receber um catálogo irrelevante.
2. Como comprador, quero que a ausência de informação seja declarada, para não confiar em uma condição inventada.
3. Como comprador, quero que todas as perguntas do meu turno sejam consideradas, para não precisar repeti-las.
4. Como comprador, quero enviar mensagens curtas consecutivas, para conversar naturalmente.
5. Como comprador, quero corrigir tamanho, quantidade ou objetivo, para continuar com a informação correta.
6. Como comprador, quero que dados já respondidos sejam lembrados, para evitar qualificação repetitiva.
7. Como comprador, quero avançar diretamente quando estiver pronto, para não passar por um funil obrigatório.
8. Como comprador, quero esclarecer objeções com condições aprovadas, para tomar uma decisão informada.
9. Como comprador, quero receber somente uma pergunta necessária por padrão, para destravar o próximo passo.
10. Como comprador, quero pedir um humano e interromper o automático, para assumir o controle do atendimento.
11. Como comprador, quero que uma recusa interrompa mensagens comerciais pendentes, para respeitar minha decisão.
12. Como comprador, quero que minha conversa seja tratada como suporte ou pós-venda quando apropriado, para não receber ofertas fora de contexto.
13. Como comprador, quero que um comprovante seja tratado como pendente de verificação, para não receber confirmação falsa de pagamento.
14. Como comprador, quero que uma condição de prazo seja confirmada antes da operação, para não comprar sob uma promessa indevida.
15. Como dono, quero configurar modalidades físicas, digitais, diretas e consultivas, para atender meu negócio.
16. Como dono, quero aprovar limites de autonomia separadamente da linguagem da skill, para manter controle das operações.
17. Como dono, quero que decisões inferidas sejam distinguidas de decisões aprovadas, para revisar o que falta.
18. Como dono, quero retomar a configuração de um checkpoint, para não depender do histórico da conversa com a IA.
19. Como dono, quero adiar decisões e visualizar impedimentos, para configurar progressivamente.
20. Como dono, quero promover uma versão revisada sem ativar um rascunho por acidente, para operar com condições aprovadas.
21. Como dono, quero restaurar uma configuração anterior sem restaurar fontes revogadas, para recuperar comportamento com segurança.
22. Como dono, quero ver cenários e resultados associados à versão ativa, para avaliar a preparação do atendimento.
23. Como developer configurador, quero listar e ler as skills de configuração e atendimento, para adaptar o pacote sem editar código.
24. Como developer configurador, quero ver a configuração efetiva e a origem de suas decisões, para explicar o comportamento.
25. Como developer configurador, quero entender por que uma capacidade está bloqueada, para corrigir a configuração necessária.
26. Como developer configurador, quero comparar rascunho e versão ativa, para revisar mudanças antes da promoção.
27. Como developer configurador, quero simular o rascunho sem afetar conversas ativas, para testar adaptações.
28. Como developer configurador, quero referências acessíveis após instalar o produto, para usar as skills fora do repositório.
29. Como developer configurador, quero que minhas instruções internas não apareçam ao comprador, para manter a separação de públicos.
30. Como developer configurador, quero configurar segredos por referências externas, para não gravá-los no pacote comercial.
31. Como responsável pelo conhecimento, quero revogar uma fonte de forma persistente, para impedir uso em consultas futuras.
32. Como responsável pelo conhecimento, quero que importações não reapropriem uma fonte revogada, para preservar minha decisão.
33. Como responsável pelo conhecimento, quero selecionar a revisão vigente por escopo e período, para impedir mistura de condições.
34. Como responsável pelo conhecimento, quero que conflitos materiais sejam explicitados, para não escolher informação arbitrariamente.
35. Como responsável pelo conhecimento, quero importar uma geração validada de forma atômica, para não expor corpus parcial.
36. Como responsável pelo conhecimento, quero recuperar trechos com origem, revisão e localização, para auditar afirmações.
37. Como responsável pelo conhecimento, quero separar documentação comercial de informação operacional, para consultar o provedor correto.
38. Como responsável pelo conhecimento, quero avaliar a versão estável do Farol antes de promovê-la, para não depender de compatibilidade presumida.
39. Como operador, quero que mensagens obsoletas sejam canceladas antes do envio, para respeitar correções e intervenção humana.
40. Como operador, quero que tentativas com resultado desconhecido sejam conciliadas, para evitar duplicação.
41. Como operador, quero observar o atendimento antes de ativar respostas públicas, para medir erros sem expor compradores.
42. Como operador, quero interromper o automático por negócio ou canal, para conter um incidente.
43. Como operador, quero confirmar que uma transferência chegou à fila humana, para não prometer encaminhamento inexistente.
44. Como operador, quero métricas de entrega, relevância, latência e custo sem conteúdo sensível, para diagnosticar o atendimento.
45. Como dono, quero comparar modelos com o mesmo conjunto de casos, para escolher com base em evidência.
46. Como dono, quero avaliar um supervisor de qualidade em observação antes de lhe dar poder de bloqueio, para medir seu benefício.
47. Como comprador, quero que qualquer revisão de texto preserve condições e autorização, para não receber promessas acrescentadas pelo revisor.
48. Como operador, quero distinguir simulação, contrato externo e validação real no relatório, para não anunciar integração inexistente.

## Implementation Decisions

1. Preservar o runtime Python local, SQLite e CLI definidos no ADR aceito. Evitar migração ampla de infraestrutura.
2. O modelo interpreta e propõe; o motor valida fatos, decide capacidades e autoriza operações. Skills não concedem permissões.
3. Distribuir somente skills dos públicos atendimento e configuração. Diagnóstico, conhecimento e simulação são atividades de configuração. Não criar um público de desenvolvimento de software.
4. Evoluir as skills existentes de instalação, descoberta, conhecimento, simulação e conversa; adicionar conteúdo especializado somente quando um comportamento e seus cenários justificarem uma skill separada.
5. Um catálogo versionado declarará identidade, público, gatilhos, recursos, compatibilidade, entradas e saídas das skills. Recursos aprovados serão resolvidos pelo catálogo; referências desconhecidas ou incompatíveis não serão tratadas como carregadas.
6. A inspeção distinguirá skills declaradas, disponíveis, selecionadas e efetivamente aplicadas. Recursos internos não serão encaminhados ao comprador ou incluídos na recuperação pública.
7. O developer configurador usará o fluxo de checkpoint, inspeção, comparação, simulação e promoção. A interface de configuração exibirá lacunas e a fonte de cada decisão sem exigir conhecimento da implementação.
8. A descoberta priorizará impedimentos da capacidade escolhida e aproveitará material aprovado. Inferências permanecem propostas; preencher a entrevista não concede autorização operacional.
9. Promoção exigirá versão nova, validação de esquema, referências resolvidas e capacidades consistentes. Mudanças em capacidades sensíveis serão explicitadas no diff. Simulação usará estado isolado. Restauração criará nova versão e respeitará revogações atuais.
10. Versões de skills, pacote, modelo e conhecimento usadas em uma decisão serão registradas com orçamento de contexto limitado. Nenhuma consulta a dependência ausente será silenciosamente anunciada como executada.
11. Representar resultados silenciosos sem mensagem pública. Pausa humana não gera a cada evento um aviso automático. Recusa ou pausa invalida respostas comerciais pendentes incompatíveis; retomada exige regra explícita.
12. Criar uma interface pública pequena de processamento de entrega, consumida pelo worker e CLI. Ela concentra revalidação, lease com identidade de posse, autorização, envio e registro do resultado, com um adaptador externo substituível.
13. Antes de cada envio, revalidar controle humano, recusa, estado, pacote aplicável, evidência e posse do lease. Uma verificação local não prova atomicidade com o provedor: o relatório deve declarar a janela residual e os mecanismos do canal.
14. ACK/NACK de um worker antigo não pode finalizar a tentativa de outro. Uma confirmação incerta no canal não volta automaticamente à fila de envio; requer conciliação pelo contrato do provedor.
15. Revogação será uma decisão de governança persistente, com escopo de fonte ou revisão. Reimportação e rollback não a desfazem. Reaprovação será explícita, auditável e sujeita à autoridade vigente, inclusive a upstream.
16. Fonte terá revisão imutável por conteúdo, escopo de negócio, público, oferta/assunto quando aplicável e vigência. A versão ativa será promovida explicitamente, nunca inferida pela ordenação lexicográfica.
17. Conflitos serão comparados dentro do mesmo assunto e escopo. Preços de ofertas diferentes não formam automaticamente conflito; divergência material da mesma fonte ou entre fontes não pode ser ignorada.
18. Recuperar conteúdo relacionado não basta. A resposta precisa de evidência que cubra a afirmação específica; ausência, conflito ou cobertura parcial produz resultado explícito. Não prometer encaminhamento que não foi enfileirado/confirmado.
19. Separar fato documental de cotação e estado operacional. Estoque, pagamento, agenda e venda confirmada continuam dependendo do conector e da política correspondente.
20. Atualizar memória estruturada por fatos, correções, perguntas abertas/respondidas e objetivo. Manter procedência por turno e evitar repetir perguntas respondidas ou armazenar histórico bruto sem necessidade.
21. Agrupar mensagens com janela configurável e limite máximo, preservando ordem e identidade. Recusa e pedido de humano não aguardam debounce. Duplicatas não produzem novo efeito.
22. Construir requisitos observáveis de resposta: assuntos a abordar, evidências permitidas, afirmações proibidas e perguntas necessárias. A redação pode variar; fatos, autorização e evidência devem permanecer verificáveis.
23. Perfis de atendimento são configuração comportamental, não novos agentes autônomos nem novas permissões. Suporte, financeiro e pós-venda terão escopo limitado a documentação e encaminhamento autorizado. Cobranças e disputas não viram efeitos livres.
24. Evoluir a importação Farol para validação, staging e promoção atômica da geração, com hashes, procedência e revogações. Artefatos legados não verificáveis serão identificados e não promovidos automaticamente como corpus aprovado.
25. A consulta ao Farol estável usará o KnowledgeBackend existente. O transporte será decidido pelo contrato publicado; processo separado/MCP é candidato para compatibilidade Python, não promessa já implementada.
26. Falha ou incompatibilidade do Farol não permite servir uma geração revogada nem apresentar o fallback local como Farol. Readiness, timeout, tamanho, geração e freshness devem ser observáveis.
27. Separar avaliação determinística, integração de contrato e execução real de modelo/Farol/canal. O comando de verificação do modelo deverá avaliar o adaptador selecionado, preservando a prova adversarial local como categoria distinta.
28. Implementar adaptador Chatwoot independente, com autenticação do contrato publicado, mapeamento de identidade e negócio, entrada durável e ACK antes de chamadas lentas. Não alterar Chatwoot core.
29. Entrega real deve distinguir envio público, nota interna, transferência solicitada e transferência confirmada. Identificadores externos verificam identidade; a convenção fictícia do simulador nunca autentica compradores reais.
30. Introduzir observação, assistência e piloto com limites explícitos e interrupção por escopo. Código pronto não equivale a autorização de deploy ou ativação pública.
31. Supervisor de qualidade começa desligado ou em observação, avalia o candidato e não autoriza capacidades. Revisão ativa admite no máximo uma correção e revalida o candidato completo; mudança de conteúdo/estado invalida a avaliação anterior.
32. Reaproveitar contratos e casos do projeto antigo gradualmente, preservando procedência/licença quando houver port de código. Não importar dependências, dados ou regras específicas de outro negócio.
33. Mudanças de esquema devem preservar histórico e permitir a atualização documentada. Caso seja necessário expand–contract, manter leitores antigos até a migração dos consumidores; nenhum refactor amplo é pré-requisito presumido.

## Testing Decisions

As interfaces abaixo são propostas e aguardam confirmação. Nenhum teste novo é autorizado por este rascunho.

- S1 — Atendimento: interface pública SellerEngine.handle, observando resposta ou silêncio, estado público, evidências e operações; chamadas subsequentes comprovam memória e retomada.
- S2 — Operação e configuração: interface pública da CLI vendedor, incluindo configuração, conhecimento, skills, simulação, avaliação e execução de um ciclo de worker. Observar resultado estruturado, códigos de saída e comportamento após reabrir o processo.
- S3 — Contrato externo do canal: entrada HTTP do adaptador e entrega observada por um servidor falso do provedor, com controle de tempo e falhas. Necessário somente para o canal real, pois a CLI não comprova autenticação/ACK HTTP.

Priorizar S1 e S2 existentes. A interface de entrega será exercitada por S2 e pelo contrato S3, sem testes de helpers ou uma bateria redundante para cada camada. Contratos remotos de modelo e Farol serão exercitados por S1/S2 com doubles apenas no processo/transporte externo.

SQLite temporário real; não consultar suas tabelas para provar comportamento. Não testar métodos privados, ordem de chamadas internas, snapshots gerados pelo próprio código ou expectativas que reproduzam o algoritmo.

Há precedentes de testes públicos de conversa, configuração retomável, consulta/revogação, CLI, concorrência e adaptador HTTP no projeto. Aproveitar o padrão de fixtures fictícias e observar suas limitações: teste privado de conflito não substitui uma conversa que recusa evidência conflitante; teste local não comprova serviço remoto.

Aplicar TDD por ticket e por comportamento: escolher um critério, escrever um teste em uma seam confirmada, executar e observar a falha correta, implementar o mínimo e executar os testes relevantes. Repetir somente depois de validar a primeira fatia. Refatoração pertence à revisão, fora do ciclo red → green.

Adicionar casos das quatro falhas reproduzidas, isolamento por negócio/público, versões, revisão de política, pacote instalado sem checkout, correções, perguntas múltiplas, timeout desconhecido, posse de lease e intervenção humana antes de envio.

Golden set sintético e versionado conterá pergunta, contexto, afirmações esperadas/proibidas, evidência esperada e resultado de ação. Para segurança: zero efeitos indevidos, vazamentos ou envios bloqueados nos casos críticos. Para relevância: o caso de garantia sem documentação deve abster-se; o caso com política de garantia deve responder usando essa política. Definir limiares de qualidade agregada antes de avaliar o candidato, sem ajustá-los ao resultado.

Latência e custo serão medidos e terão limites de piloto configurados antes da ativação. Critério comercial não é cobertura de código. Modelo/revisor como juiz auxiliar não será a única fonte de verdade.

Executar verificações locais relevantes a cada ticket e o conjunto completo nos marcos integrados. Integração externa não executada deve aparecer como não executada, nunca como aprovada por substituição por um fake.

## Out of Scope

- Skills para programação, manutenção, arquitetura, criação de conectores ou refatoração do sistema.
- Implementação nesta entrega de planejamento.
- Deploy, migração em produção, envio a compradores ou ativação pública implícitos.
- Reescrever o Farol ou definir antecipadamente contratos da versão ainda não publicada.
- Importar integralmente o projeto antigo, seu frontend ou sua infraestrutura.
- Migração obrigatória para Postgres/Redis, painel administrativo novo e orquestração multiagente.
- Novos gateways de pagamento, agenda ou CRM reais; os contratos atuais serão preservados.
- Follow-up proativo novo, campanhas e automação irrestrita de financeiro/suporte.
- Garantia de exatamente uma entrega quando o provedor não oferece idempotência/consulta suficiente.
- Treino automático em conversas reais ou promoção automática de conhecimento aprendido.

## Further Notes

A análise anterior executou 74 testes e 38 cenários aprovados no baseline, com provas adicionais das quatro lacunas; estes números não são uma nova execução deste planejamento. O baseline analisado do produto foi 30b9cf96d4dcf3edaf7af901a71f79eb2a1d92c1.

Referências de comparação: chatwoot-ai 783f41927c7fe1652d6bf78933c51bdde31ab751; Farol público observado 2ff00fcfc581147ba9367b6a2a84dc1b1d6cbab5; integração antiga do produto fixada em 81d5dcb2e189d00406cdd9b9e671d94e3f23cd58. Não tratar o HEAD observado como a versão estável futura anunciada pelo dono.

Partes úteis do projeto antigo: memória e registro de perguntas, requisitos de resposta, debounce, perfis, verificação antes do envio, pacotes comerciais e supervisor de qualidade. Reaproveitamento é proposta, não validação de produção.

Publicação: não foi encontrada configuração de issue tracker ou vocabulário de triagem no projeto/monorepo. As skills solicitadas instruem executar /setup-matt-pocock-skills. Após configurar o destino e confirmar seams/tickets, publicar a spec e um ticket por issue com ready-for-agent, respeitando as dependências. Não modificar nem encerrar uma issue pai.

Bloqueios externos: T16 requer a versão estável publicada do Farol; execução real dos contratos de canal/modelo depende de ambiente e credenciais adequados. T20 requer autorização específica para piloto público. Esses bloqueios não impedem as correções locais, configuração ou preparação dos adaptadores.
