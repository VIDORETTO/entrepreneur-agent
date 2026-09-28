# Verification

<!-- GENERATED from evidence/*.json. Evidence records are canonical. -->

## EV-001 — stale

- Ticket: `TK-001`
- Acceptance: `AC-001`
- Procedure: `.venv/bin/python -m pytest -q tests/test_knowledge_and_configuration.py::test_farol_manifest_normalizes_offset_dates_and_replaces_previous_generation`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:a8d4e0af5e216d97289288ba9a398d7e555c581ce51f56bb3b6fb2cf96b4a10f`
- Timestamp: `2026-09-28T14:13:45+00:00`
- Observations: Farol source with validity ending 2026-09-22 returned under injected 2026-09-20 clock; 1 passed
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

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

## EV-005 — stale

- Ticket: `TK-003`
- Acceptance: `AC-004`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:4441451e31e9451129aac10301596fb38abf8603b4bbbdd364881fefd3c286fe`
- Timestamp: `2026-09-28T14:32:59+00:00`
- Observations: Timestamped HMAC request admitted once; replay returns duplicate; 39 contract/regression tests passed
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-006 — stale

- Ticket: `TK-003`
- Acceptance: `AC-005`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:879b9e47216358c6655be86fd44d278e2e30d2399d31d3932d000bc94cec7617`
- Timestamp: `2026-09-28T14:32:59+00:00`
- Observations: Body-only signature returns 401 with default binding; explicit legacy-body admits it; doctor reports legacy_signature without secret; 39 tests passed
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-007 — stale

- Ticket: `TK-003`
- Acceptance: `AC-006`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:4441451e31e9451129aac10301596fb38abf8603b4bbbdd364881fefd3c286fe`
- Timestamp: `2026-09-28T14:32:59+00:00`
- Observations: Timestamp 301 seconds old returns 401 and no queued inbound; same message later accepted with current signed timestamp; 39 tests passed
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-008 — stale

- Ticket: `TK-004`
- Acceptance: `AC-007`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:5a9cea82d598a32c1772fd698c7be2696e3dd3118a1f04227883c0a2d19dd143`
- Timestamp: `2026-09-28T14:41:40+00:00`
- Observations: Sent response got provider ID 42; after reopening SQLite, outgoing echo returned self_authored without human pause; 37 tests passed
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-009 — stale

- Ticket: `TK-004`
- Acceptance: `AC-008`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:83e38f1e08e3d1ff07ce2282f7bca841449a3f63adedf1b28114bef7a5d47641`
- Timestamp: `2026-09-28T14:41:40+00:00`
- Observations: Unknown outgoing message 99 from user with different content returned human_message and human_paused; 37 tests passed
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-010 — stale

- Ticket: `TK-004`
- Acceptance: `AC-009`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:286f00b25c90dfadeb8abf073eb6221d9db8bbd630c041eb70b5f55106ca36c9`
- Timestamp: `2026-09-28T14:41:40+00:00`
- Observations: Synchronous echo before provider ACK matched in-flight content; no human pause; after 121 seconds same content was human_message; 37 tests passed
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-011 — stale

- Ticket: `TK-001`
- Acceptance: `AC-001`
- Procedure: `.venv/bin/python -m pytest -q tests/test_knowledge_and_configuration.py::test_farol_manifest_normalizes_offset_dates_and_replaces_previous_generation`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:df01aa83e5cb114e91c4acc7086bdc67b930a9259c900bb16be91a341231be73`
- Timestamp: `2026-09-28T14:44:43+00:00`
- Observations: After additive outbound ledger migration, fixed-clock Farol validity test passed again
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-012 — stale

- Ticket: `TK-003`
- Acceptance: `AC-004`, `AC-005`, `AC-006`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:8a591fec839adf30710d062b1d20db646b5c592246113467ddfee505e9a8eb32`
- Timestamp: `2026-09-28T14:44:43+00:00`
- Observations: After echo correlation changes, timestamped HMAC, legacy opt-in and stale timestamp contract cases remained green; 43 passed
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-013 — stale

- Ticket: `TK-004`
- Acceptance: `AC-007`, `AC-008`, `AC-009`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:ed99d7a6444a16a2acea2603475bfa69a50d1112dd665b837e0cf8dfec103420`
- Timestamp: `2026-09-28T14:44:43+00:00`
- Observations: Local HTTP Chatwoot server returned IDs and echoed signed webhooks before ACK; ID match persisted after restart; unknown human message paused; 120-second fallback bound; 37 passed
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-014 — passed

- Ticket: `TK-001`
- Acceptance: `AC-001`
- Procedure: `.venv/bin/python -m pytest -q tests/test_knowledge_and_configuration.py::test_farol_manifest_normalizes_offset_dates_and_replaces_previous_generation`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:fadb1d3e26fc3f77078d33b3aa755c15a9dd2f54cf9c1fed87874ee41663ece1`
- Timestamp: `2026-09-28T14:46:42+00:00`
- Observations: Fixed-clock Farol validity test still passes after outbound ledger lease check
- Evidence refs: none
- Limitations: none recorded

## EV-015 — passed

- Ticket: `TK-004`
- Acceptance: `AC-007`, `AC-008`, `AC-009`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:be8086c1be1eba8dffb5436cb9fa652be215d30e2f1f483ac68e6b3c26dfbe00`
- Timestamp: `2026-09-28T14:46:43+00:00`
- Observations: Local HTTP server contract verifies ID correlation, human takeover, synchronous echo race and 120-second bound after lease check; 37 passed
- Evidence refs: none
- Limitations: none recorded

## EV-016 — stale

- Ticket: `TK-005`
- Acceptance: `AC-010`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:387cc32c992b096f21fefb9f12e67ac512ec9586ec75f20141665e7ff085fb9f`
- Timestamp: `2026-09-28T14:59:58+00:00`
- Observations: HTTP webhook returned 200 before Chatwoot received any POST; fake Chatwoot then received one public response.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-017 — stale

- Ticket: `TK-005`
- Acceptance: `AC-011`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:387cc32c992b096f21fefb9f12e67ac512ec9586ec75f20141665e7ff085fb9f`
- Timestamp: `2026-09-28T14:59:58+00:00`
- Observations: Ready endpoint returned 200; interrupted channel and temporary SQLite foreign-key violation each returned 503 with specific reason; health stayed 200.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-018 — stale

- Ticket: `TK-005`
- Acceptance: `AC-012`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:387cc32c992b096f21fefb9f12e67ac512ec9586ec75f20141665e7ff085fb9f`
- Timestamp: `2026-09-28T14:59:59+00:00`
- Observations: SIGTERM during held fake Chatwoot POST, then restart on same data directory, yielded exactly one POST and public outbox sent or unknown.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-019 — passed

- Ticket: `TK-003`
- Acceptance: `AC-004`, `AC-005`, `AC-006`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:a5145c8b45cb2a991115c6ca6a13fe9e2225d294e985a870c92a68da722bb7fb`
- Timestamp: `2026-09-28T15:02:27+00:00`
- Observations: After serve CLI addition, HMAC, legacy opt-in, stale timestamp and pilot channel contracts remain green; 43 passed.
- Evidence refs: none
- Limitations: none recorded

## EV-020 — passed

- Ticket: `TK-005`
- Acceptance: `AC-010`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:d7f69e5f92a8498d760cd196a185b77b93bb4b425bbfeba8eff0f14a969de427`
- Timestamp: `2026-09-28T15:02:27+00:00`
- Observations: Webhook ACK preceded fake Chatwoot POST; one public response arrived after turn window.
- Evidence refs: none
- Limitations: none recorded

## EV-021 — passed

- Ticket: `TK-005`
- Acceptance: `AC-011`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:d7f69e5f92a8498d760cd196a185b77b93bb4b425bbfeba8eff0f14a969de427`
- Timestamp: `2026-09-28T15:02:28+00:00`
- Observations: Ready endpoint was 200, then returned 503 with interruption or SQLite integrity reason; health remained 200.
- Evidence refs: none
- Limitations: none recorded

## EV-022 — passed

- Ticket: `TK-005`
- Acceptance: `AC-012`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:d7f69e5f92a8498d760cd196a185b77b93bb4b425bbfeba8eff0f14a969de427`
- Timestamp: `2026-09-28T15:02:28+00:00`
- Observations: SIGTERM during a held provider POST, followed by restart, produced one POST and outbox sent or unknown.
- Evidence refs: none
- Limitations: none recorded
