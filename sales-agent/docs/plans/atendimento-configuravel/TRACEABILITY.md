# Matriz de rastreabilidade — atendimento configurável

Atualizada em 20/09/2026. A matriz liga cada ticket ao comportamento
observável, à seam aprovada e à evidência local disponível. `local` não
significa integração de produção; contratos externos continuam classificados
separadamente.

| Ticket | Comportamento observado | Implementação principal | Evidência | Limite |
|---|---|---|---|---|
| T01 | pausa humana/recusa silenciam e cancelam respostas incompatíveis | `conversation.py`, `storage.py` | `test_conversation_contract.py` | canal real não executado |
| T02 | entrega revalida estado; lease expirado vira `unknown` | `delivery.py`, `storage.py` | `test_delivery_and_governance.py`, `test_storage_reliability.py` | janela residual depende do provedor |
| T03 | revogação sobrevive reimportação e restart; fontes removidas do snapshot ficam inativas | `knowledge.py`, `storage.py`, `config.py` | `test_delivery_and_governance.py`, `test_knowledge_and_configuration.py` | — |
| T04 | seleção usa negócio, escopo, público, assunto, vigência e promoção; legado e `pending_review` não entram sem revisão | `knowledge.py`, `storage.py` | `test_knowledge_and_configuration.py`, AC012 | — |
| T05 | cobertura parcial/conflito gera lacuna explícita | `conversation.py`, `knowledge.py` | `test_conversation_contract.py`, AC013 | — |
| T06 | catálogo instalado e diagnóstico de skills | `skills.py`, CLI | `test_skills_and_configuration.py` | fontes externas são apenas referências |
| T07 | descoberta por checkpoint e impedimento | `config.py`, `skills.py` | `test_turns_and_profiles.py`, CLI | — |
| T08 | inspeção, diff, simulação, promoção e restauração versionada | `config.py`, CLI | `test_knowledge_and_configuration.py`, `test_cli_and_evaluation.py` | — |
| T09 | skills declaradas/disponíveis/selecionadas/aplicadas no trace | `skills.py`, `conversation.py` | `test_skills_and_configuration.py` | prompt não concede permissão |
| T10 | fatos, correções e perguntas abertas são persistidos | `conversation.py`, `storage.py` | `test_conversation_contract.py`, `test_turns_and_profiles.py` | — |
| T11 | mensagens consecutivas agrupam-se com urgência e debounce durável | `turns.py`, `storage.py` | `test_turns_and_profiles.py` | canal HTTP real não executado |
| T12 | resposta cobre fatos e nomeia lacunas necessárias | `conversation.py` | `test_conversation_contract.py`, golden set | — |
| T13 | perfis e objeções não ampliam autonomia | `conversation.py`, `config.py` | `test_turns_and_profiles.py` | — |
| T14 | evidência pendente é revalidada antes do envio, assim como fingerprint, versão e capability do pacote | `delivery.py`, `governance.py` | `test_delivery_and_governance.py`, `test_channel_pilot_supervisor.py` | — |
| T15 | geração Farol é validada e promovida atomicamente; intervalo inválido e duas revisões ativas são rejeitados | `knowledge.py`, `storage.py` | `test_knowledge_and_configuration.py`, `test_delivery_and_governance.py` | contrato estável do upstream pendente |
| T16 | adaptador estável não anuncia contrato não verificado | `knowledge.py`, CLI | `test_knowledge_and_configuration.py` | bloqueado: cliente/revisão estáveis não disponíveis |
| T17 | 38 expectativas independentes, modelo e limiares no relatório | `evaluation.py`, CLI | `test_cli_and_evaluation.py`, `evaluation/golden_set.json` | remoto/Farol/Chatwoot `not-executed` |
| T18 | entrada Chatwoot autenticada, durável, idempotente e com identidade externa vinculada ao ledger | `channel.py`, `storage.py` | `test_channel_pilot_supervisor.py` | servidor usado é fixture local |
| T19 | mensagem, nota, transferência, confirmação e redirecionamento same-origin são distintos | `channel.py`, `delivery.py` | `test_channel_pilot_supervisor.py` | Chatwoot real não executado |
| T20 | observação/assistência/piloto têm coorte, limites, interrupção, expiração, reservas persistentes e métricas | `governance.py`, `storage.py`, CLI | `test_channel_pilot_supervisor.py`, `test_storage_reliability.py` | ativação pública exige autorização |
| T21 | supervisor observa sem alterar resposta e mede dimensões; timeout fica registrado como `timeout` | `governance.py` | `test_channel_pilot_supervisor.py` | juiz externo não executado |
| T22 | uma correção seletiva é revalidada e fica vinculada ao candidato original | `governance.py`, `conversation.py` | `test_channel_pilot_supervisor.py` | adoção pública exige critérios externos |

## Classes de evidência

- `local`: SQLite temporário, simuladores e adaptadores determinísticos do
  pacote.
- `contrato local`: fixture HTTP/transport falso que exercita autenticação,
  ACK, idempotência e limites sem tocar serviço externo.
- `not-executed`: cliente, credencial, serviço ou versão estável que não foi
  disponibilizado nesta execução. Não é convertido em aprovação.

Nenhuma linha autoriza deploy, cobrança, envio público ou uso de dados reais.
