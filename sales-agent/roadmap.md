# Roadmap: Vendedor Adaptável

Roadmap candidates are strategic outcomes, not executable tasks. Promote a candidate to an effort only after its next slice meets the readiness contract.

| Candidate | Outcome/hypothesis | Depends on | Priority | State | Promoted effort |
| --- | --- | --- | --- | --- | --- |
| CAND-001 | Do alpha local ao primeiro piloto real confiável (canal, modelo, verificação, humano, LGPD) | — | P1 | promoted | `specs/001-piloto-real-confiavel` |
| CAND-002 | Checkout real com Pix/cartão (ex.: gateway brasileiro) mantendo `confirmed/pending/failed/unknown` e conciliação | CAND-001 | P1 | candidate | — |
| CAND-003 | Consulta ao Farol estável publicado (T16) via `KnowledgeBackend` | publicação do Farol estável | P2 | blocked_external | — |
| CAND-004 | Recuperação híbrida BM25 + vetores com RRF, se recall@5 < 0,9 em CAND-001 | CAND-001 (AC-034) | P2 | candidate | — |
| CAND-005 | Templates HSM do WhatsApp para retomada fora da janela de 24 h, com opt-in | CAND-001 (TK-006) | P2 | candidate | — |
| CAND-006 | Comprador simulado por modelo para ampliar avaliação (estilo τ-bench) sem substituir casos escritos à mão | CAND-001 (TK-012) | P3 | candidate | — |
| CAND-007 | Segundo modelo validado para comprovar portabilidade (plano §18 M5) | CAND-001 | P2 | candidate | — |
| CAND-008 | Segundo negócio real reproduzindo a instalação (plano §18 M5) | CAND-002 | P3 | candidate | — |
