# Verification

<!-- GENERATED from evidence/*.json. Evidence records are canonical. -->

## EV-001 — passed

- Ticket: `TK-001`
- Acceptance: `AC-001`
- Procedure: `.venv/bin/python -m pytest -q tests/test_knowledge_and_configuration.py::test_farol_manifest_normalizes_offset_dates_and_replaces_previous_generation`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:a8d4e0af5e216d97289288ba9a398d7e555c581ce51f56bb3b6fb2cf96b4a10f`
- Timestamp: `2026-09-28T14:13:45+00:00`
- Observations: Farol source with validity ending 2026-09-22 returned under injected 2026-09-20 clock; 1 passed
- Evidence refs: none
- Limitations: none recorded

## EV-002 — passed

- Ticket: `TK-001`
- Acceptance: `AC-002`
- Procedure: `.venv/bin/python -m pytest -q && .venv/bin/python -m pytest -q --clock-shift-days=400 && .venv/bin/ruff check src tests`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:edbf5cb446eecda310a1194e679af0c10785c4edbaa13bb8b3c668e6f717d820`
- Timestamp: `2026-09-28T14:13:52+00:00`
- Observations: Normal and +400-day process clock suites: 172 passed each; Ruff all checks passed; CI job changed at parent .github/workflows/sales-agent-ci.yml
- Evidence refs: none
- Limitations: none recorded
