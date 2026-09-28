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

## EV-002 — stale

- Ticket: `TK-001`
- Acceptance: `AC-002`
- Procedure: `.venv/bin/python -m pytest -q && .venv/bin/python -m pytest -q --clock-shift-days=400 && .venv/bin/ruff check src tests`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:edbf5cb446eecda310a1194e679af0c10785c4edbaa13bb8b3c668e6f717d820`
- Timestamp: `2026-09-28T14:13:52+00:00`
- Observations: Normal and +400-day process clock suites: 172 passed each; Ruff all checks passed; CI job changed at parent .github/workflows/sales-agent-ci.yml
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-003 — passed

- Ticket: `TK-001`
- Acceptance: `AC-002`
- Procedure: `.venv/bin/python -m pytest -q --clock-shift-days=400`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:a656916fbfe6dfeaf23429291505bc4f751aa55f43ef9ea02fae5103a506bd53`
- Timestamp: `2026-09-28T14:19:32+00:00`
- Observations: After Python floor metadata change, 172 passed under +400-day process clock
- Evidence refs: none
- Limitations: none recorded

## EV-004 — partial

- Ticket: `TK-002`
- Acceptance: `AC-003`
- Procedure: `/tmp/vendedor-py310/bin/python -m pip install --dry-run --no-deps .; /tmp/vendedor-py311/bin/python -m pytest -q; /tmp/vendedor-py314/bin/python -m pytest -q; .venv/bin/python -m build; .venv/bin/twine check dist/*`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:df58e5cc38d8baacb60fb79205a92362f491d9600b26d44a81e907b0cf92f6b3`
- Timestamp: `2026-09-28T14:19:56+00:00`
- Observations: pip 3.10.21 rejects Python>=3.11; 3.11.16 and 3.14.7 each pass 172 tests; build and twine pass
- Evidence refs: none
- Limitations: GitHub Actions workflow not executed; goal prohibits git push

## EV-005 — passed

- Ticket: `TK-003`
- Acceptance: `AC-004`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:4441451e31e9451129aac10301596fb38abf8603b4bbbdd364881fefd3c286fe`
- Timestamp: `2026-09-28T14:32:59+00:00`
- Observations: Timestamped HMAC request admitted once; replay returns duplicate; 39 contract/regression tests passed
- Evidence refs: none
- Limitations: none recorded

## EV-006 — passed

- Ticket: `TK-003`
- Acceptance: `AC-005`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:879b9e47216358c6655be86fd44d278e2e30d2399d31d3932d000bc94cec7617`
- Timestamp: `2026-09-28T14:32:59+00:00`
- Observations: Body-only signature returns 401 with default binding; explicit legacy-body admits it; doctor reports legacy_signature without secret; 39 tests passed
- Evidence refs: none
- Limitations: none recorded

## EV-007 — passed

- Ticket: `TK-003`
- Acceptance: `AC-006`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:4441451e31e9451129aac10301596fb38abf8603b4bbbdd364881fefd3c286fe`
- Timestamp: `2026-09-28T14:32:59+00:00`
- Observations: Timestamp 301 seconds old returns 401 and no queued inbound; same message later accepted with current signed timestamp; 39 tests passed
- Evidence refs: none
- Limitations: none recorded
