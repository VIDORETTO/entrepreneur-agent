# TK-011 review

Baseline: `0c5dc47` plus the TK-011 working diff and new retrieval fixture/test. Reviewed after verification.

## Standards

No blocking findings. The index is rebuilt on schema migration, maintained by triggers, and all source governance predicates remain in SQL. Public result keys remain stable. Queries contain only extracted Unicode word tokens quoted as FTS literals. The fallback is explicit in `doctor`. `python3.12 -m pytest -q` passed (228 tests), and `ruff check src tests` passed.

## Spec

No blocking findings. AC-031 covers accent and case; AC-032 checks revocation, business, validity, audience, and symbol-only queries; AC-033 checks 5,000 sources and 100 queries against p95 < 50 ms; AC-034 checks 32/32 recall@5 and 8/8 abstention from a versioned 40-question set. Executed refs: EV-103–EV-106. Local SQLite and deterministic evaluation do not establish remote model quality.
