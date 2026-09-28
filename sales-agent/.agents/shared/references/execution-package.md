# Pacote de execução

O próprio ticket enriquecido é o pacote que pode ser entregue a uma executora em contexto novo. O comando `python <package>/scripts/hybrid.py package --project . --effort <id> --ticket TK-xxx --json` verifica sua prontidão e pode gerar uma cópia de leitura em `.hybrid/packets/`; essa cópia é projeção, nunca contrato concorrente.

Um ticket `ready` precisa conter, em ordem que facilite a execução:

1. Identidade: ID, esforço, revisão do ticket e revisões de `spec.md`/`plan.md`.
2. Objetivo e limites: comportamento observável, aceites associados e exclusões específicas.
3. Leitura em ordem: caminho, símbolo ou seção e motivo; caminhos são verificados durante o planejamento.
4. Decisões já resolvidas: abordagem, motivo curto, restrições e alternativas relevantes.
5. Mapa de alterações: arquivos existentes e símbolos, arquivos novos previstos e áreas fora da fatia.
6. Contrato técnico: entradas, saídas, tipos, invariantes, erros, efeitos, compatibilidade, concorrência e idempotência quando aplicável.
7. Exemplos de aceite: estado inicial, entrada, resultado e efeito permitido/proibido, com oráculo independente.
8. Sequência: passos pequenos de red → green, dependências e checkpoints.
9. Validação: diretório, comando ou procedimento exato, ambiente e interpretação de falha.
10. Condição de retorno: incompatibilidade, referência desatualizada, decisão nova ou recurso indisponível.
11. Relatório de saída: alterações, aceites atendidos, evidências, pendências e desvios.

O caminho ou comando identificado na configuração não equivale a comando executado. A evidência deve registrar `execution_status: executed` para resultados `passed`, `failed` ou `partial`; `not_run` registra impedimento sem alegar aprovação.

A executora pode escolher detalhes locais reversíveis. Ela preserva o contrato e devolve uma dúvida específica quando faltar decisão de comportamento, contrato público, modelo de dados, dependência não prevista, autorização ou recurso necessário. Exemplo:

```text
Ticket: TK-002
Passo: TK-002.2
Bloqueio: a Interface atual não permite a consulta exigida por AC-002.
Evidência: caminho, símbolo e resultado observado.
Trabalho concluído: teste de AC-002 adicionado e falha registrada.
Decisão necessária: forma de representar e consultar a chave.
Impacto: AC-002 não pode ser implementado pela abordagem atual.
```
