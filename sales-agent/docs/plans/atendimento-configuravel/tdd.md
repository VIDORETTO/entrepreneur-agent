# Estratégia TDD — proposta para confirmação

## Escopo

Aplicar a skill tdd na implementação futura. Não criar testes nesta etapa. Confirmar as seams antes do primeiro teste; mudar a interface exige rever o acordo, não testar helpers por conveniência.

Usar os termos do domínio: comprador, dono, intenção, impedimento, pergunta necessária, fase comercial, operação, venda confirmada, pacote comercial, fonte, evidência, checkpoint e capacidade.

## Interfaces públicas

| Seam | Interface | Observação | Evitar |
|---|---|---|---|
| S1 | SellerEngine.handle | Resposta/silêncio, estado, evidência, operação e consequência no próximo turno | Métodos privados, prompt inteiro, banco consultado diretamente |
| S2 | CLI vendedor | JSON, status, código de saída, consultas posteriores, retomada e ciclo de worker | SQL como prova, chamadas internas, estrutura de classes |
| S3 | HTTP de entrada e contrato de canal | ACK/rejeição, processamento via S2, ações observadas no servidor externo falso | Mock do motor/armazenamento, afirmar produção com fake |

Modelo e Farol usam adaptadores existentes. Doubles representam apenas provedores externos, relógio ou aleatoriedade. A interface de entrega concentra revalidação e envio; testes a observam pelo ciclo público S2.

## Primeiro ciclo recomendado

T01: preparar resposta pendente, pedir humano, processar a fila e observar ausência de entrega comercial autorizada.

1. Escrever somente um teste desse comportamento na seam confirmada.
2. Executar e observar a falha esperada, não erro de importação/fixture.
3. Implementar apenas o necessário.
4. Executar o teste e regressões pertinentes.
5. Escolher outro comportamento do ticket e repetir.
6. Revisar a alteração; refatoração pertence à revisão, fora do ciclo red → green.

Não escrever antecipadamente testes de todos os tickets. Critérios de aceite são expectativas de produto, não uma bateria horizontal.

## Casos com expectativas independentes

| Caso | Resultado esperado |
|---|---|
| Garantia perguntada; corpus só tem preço/tamanho | Lacuna explícita; nenhuma garantia inventada |
| Política aprovada informa 30 dias de garantia | Informar 30 dias com evidência dessa política |
| Fonte revogada e pacote reimportado | Consulta continua sem a fonte |
| Revisão vigente muda acesso de 6 para 24 meses | Usar 24 meses; revisão anterior é histórica |
| Ofertas distintas têm preços distintos | Não declarar conflito só pela diferença |
| Mesma condição tem divergência sem resolução | Impedimento, sem escolha arbitrária |
| Humano assume antes do envio | Nenhum envio daquele candidato |
| Lease expira e outro worker assume | Worker antigo não conclui tentativa nova |
| Timeout após possível recebimento pelo provedor | Resultado desconhecido, sem retry automático |
| Preço e garantia perguntados, só preço documentado | Responder preço e declarar lacuna de garantia |
| Skill pede ação proibida | Nenhuma operação proibida |
| Supervisor acrescenta prazo não autorizado | Candidato revisado bloqueado |
| Instalação sem checkout | Skills e recursos necessários acessíveis |

Valores são literais de fixtures fictícias revisadas. Não calcular a expectativa pelo algoritmo da implementação. Exigir frase exata somente quando ela for contrato; nos demais casos observar fatos, lacunas e operações.

## Persistência e concorrência

SQLite temporário real e diretórios isolados. Comprovar persistência reabrindo o produto e consultando sua interface, sem acessar tabelas para provar comportamento.

Injetar relógio para vigência, leases e debounce, sem sleeps longos. Coordenar concorrência por pontos externos e observar resultados via worker/CLI e provedor falso.

Separar falha anterior ao envio de resultado desconhecido. Teste local não comprova exatamente uma entrega sem suporte do canal.

## Fixtures e avaliações

Cobrir físico B2C direto, digital, B2B direto e serviço consultivo; incluir variantes em português, correções e perguntas sem evidência. Não usar conversas/documentos reais do projeto antigo, credenciais ou dados pessoais.

Golden set versionado contém objetivo, configuração, contexto mínimo, evidência esperada, resposta factual ou abstenção, afirmações proibidas e operações permitidas. Relevância e existência de evidência são métricas distintas.

Separar:
- Prova determinística local.
- Contrato externo com servidor/processo falso.
- Integração real identificando backend, revisão e resultado.
- Dependência não executada.

Zero efeitos indevidos, vazamentos ou envios proibidos nos casos críticos. Limiares agregados são definidos antes da avaliação, sem ajustá-los aos resultados do candidato. Medir custo e latência; definir limites de piloto antes da ativação. Julgamento por modelo é auxiliar, nunca prova única.

## Conclusão por ticket

- Critérios observados pela seam confirmada e evidência red → green.
- Autorização preservada no motor, independentemente de skill/prompt.
- Histórico preservado e migração compatível quando houver dados persistentes.
- Provas externas ausentes declaradas; não concluir o requisito que depende delas.
- Documentação de configuração/operação atualizada quando a interface muda.
- Regressões proporcionais aprovadas; ampliar testes só por integração ou risco.
- Revisão separada antes da conclusão.
- Nenhum deploy ou envio público inferido da aprovação dos testes.

## Marcos integrados

Preservar precedentes de testes de conversa, CLI, configuração retomável, evidência, concorrência e adaptador HTTP. Não copiar acoplamentos internos de testes antigos.

Nos marcos, executar a verificação rápida do projeto em ambiente isolado: diagnóstico, testes, demo e avaliação. Para skills, validar instalação sem checkout. Registrar resultados da execução atual sem reaproveitar números antigos.

## Aprovação pendente

S1/S2/S3 são propostas. A skill tdd determina: “Test only at pre-agreed seams.” to-spec exige conferir essas interfaces e to-tickets exige aprovar a divisão antes de publicar. Os rascunhos permitem uma revisão final concreta.
