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

## EV-014 — stale

- Ticket: `TK-001`
- Acceptance: `AC-001`
- Procedure: `.venv/bin/python -m pytest -q tests/test_knowledge_and_configuration.py::test_farol_manifest_normalizes_offset_dates_and_replaces_previous_generation`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:fadb1d3e26fc3f77078d33b3aa755c15a9dd2f54cf9c1fed87874ee41663ece1`
- Timestamp: `2026-09-28T14:46:42+00:00`
- Observations: Fixed-clock Farol validity test still passes after outbound ledger lease check
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-015 — stale

- Ticket: `TK-004`
- Acceptance: `AC-007`, `AC-008`, `AC-009`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:be8086c1be1eba8dffb5436cb9fa652be215d30e2f1f483ac68e6b3c26dfbe00`
- Timestamp: `2026-09-28T14:46:43+00:00`
- Observations: Local HTTP server contract verifies ID correlation, human takeover, synchronous echo race and 120-second bound after lease check; 37 passed
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

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

## EV-019 — stale

- Ticket: `TK-003`
- Acceptance: `AC-004`, `AC-005`, `AC-006`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:a5145c8b45cb2a991115c6ca6a13fe9e2225d294e985a870c92a68da722bb7fb`
- Timestamp: `2026-09-28T15:02:27+00:00`
- Observations: After serve CLI addition, HMAC, legacy opt-in, stale timestamp and pilot channel contracts remain green; 43 passed.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-020 — stale

- Ticket: `TK-005`
- Acceptance: `AC-010`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:d7f69e5f92a8498d760cd196a185b77b93bb4b425bbfeba8eff0f14a969de427`
- Timestamp: `2026-09-28T15:02:27+00:00`
- Observations: Webhook ACK preceded fake Chatwoot POST; one public response arrived after turn window.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-021 — stale

- Ticket: `TK-005`
- Acceptance: `AC-011`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:d7f69e5f92a8498d760cd196a185b77b93bb4b425bbfeba8eff0f14a969de427`
- Timestamp: `2026-09-28T15:02:28+00:00`
- Observations: Ready endpoint was 200, then returned 503 with interruption or SQLite integrity reason; health remained 200.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-022 — stale

- Ticket: `TK-005`
- Acceptance: `AC-012`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:d7f69e5f92a8498d760cd196a185b77b93bb4b425bbfeba8eff0f14a969de427`
- Timestamp: `2026-09-28T15:02:28+00:00`
- Observations: SIGTERM during a held provider POST, followed by restart, produced one POST and outbox sent or unknown.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-023 — passed

- Ticket: `TK-001`
- Acceptance: `AC-001`
- Procedure: `.venv/bin/python -m pytest -q tests/test_knowledge_and_configuration.py::test_farol_manifest_normalizes_offset_dates_and_replaces_previous_generation`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:db257a7000f9072e660136d5078da709cfc24de8230c663b4e8b4aaae4f4f0c3`
- Timestamp: `2026-09-28T15:14:36+00:00`
- Observations: Farol clock test remained green after the added inbound timestamp read; 1 passed.
- Evidence refs: none
- Limitations: none recorded

## EV-024 — stale

- Ticket: `TK-004`
- Acceptance: `AC-007`, `AC-008`, `AC-009`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:6247dc072e7ac2818fb42acec3d7a88582cd8a81b275f6ac8fa5e5d50d582c04`
- Timestamp: `2026-09-28T15:14:36+00:00`
- Observations: Echo correlation and human takeover remained green after WhatsApp binding and delivery changes; 37 passed.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-025 — stale

- Ticket: `TK-003`
- Acceptance: `AC-004`, `AC-005`, `AC-006`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:dcde3f4f9acb655478d5f101d2920f6669bb017927ccc130728c31f8de1a4488`
- Timestamp: `2026-09-28T15:14:36+00:00`
- Observations: Timestamped and legacy webhook signature contracts remained green after binding change; 43 passed.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-026 — stale

- Ticket: `TK-005`
- Acceptance: `AC-010`, `AC-011`, `AC-012`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:3ff463f4b7fcdf23afd4ab291974342284df170b42ec1cd056f69cdf126da44f`
- Timestamp: `2026-09-28T15:14:37+00:00`
- Observations: Service HTTP, readiness and SIGTERM restart contracts remained green after window change; 4 passed.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-027 — stale

- Ticket: `TK-006`
- Acceptance: `AC-013`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:face85e3832e954de086b71673d207efa4d9a5bae0383aa0ea954e65a5835212`
- Timestamp: `2026-09-28T15:14:37+00:00`
- Observations: WhatsApp inbound at 23:59:59 and exactly 24:00:00 before delivery produced one public send.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-028 — stale

- Ticket: `TK-006`
- Acceptance: `AC-014`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:face85e3832e954de086b71673d207efa4d9a5bae0383aa0ea954e65a5835212`
- Timestamp: `2026-09-28T15:14:37+00:00`
- Observations: Inbound at 24:00:01 before delivery produced terminal window_closed and exactly one private attendant note; missing buyer timestamp also closed.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-029 — stale

- Ticket: `TK-006`
- Acceptance: `AC-015`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:face85e3832e954de086b71673d207efa4d9a5bae0383aa0ea954e65a5835212`
- Timestamp: `2026-09-28T15:14:37+00:00`
- Observations: Scheduled follow-up revalidation after the WhatsApp window returned send false, reason window_closed, and cancelled the pending task.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-030 — stale

- Ticket: `TK-006`
- Acceptance: `AC-013`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:dfe90dfa54285cecf80ecbc78b8da51d34437127e9b05368cf2600877d8b2412`
- Timestamp: `2026-09-28T15:17:23+00:00`
- Observations: At 23:59:59 and exactly 24:00:00 after last buyer message, one public Chatwoot send was observed.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-031 — stale

- Ticket: `TK-006`
- Acceptance: `AC-014`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:dfe90dfa54285cecf80ecbc78b8da51d34437127e9b05368cf2600877d8b2412`
- Timestamp: `2026-09-28T15:17:24+00:00`
- Observations: After 24:00:01, no public send; outbox terminal window_closed and one private note to attendant; missing timestamp failed closed.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-032 — stale

- Ticket: `TK-006`
- Acceptance: `AC-015`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:dfe90dfa54285cecf80ecbc78b8da51d34437127e9b05368cf2600877d8b2412`
- Timestamp: `2026-09-28T15:17:24+00:00`
- Observations: A scheduled Chatwoot follow-up after the WhatsApp window ended was window_closed at delivery and revalidation returned reason window_closed.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-033 — stale

- Ticket: `TK-006`
- Acceptance: `AC-013`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:ca685b7a73d9eab23e1fb0ac5119c719caba228ffaf8e00f29a803824d39ceb4`
- Timestamp: `2026-09-28T15:20:26+00:00`
- Observations: At 23:59:59 and 24:00:00 after buyer admission, public delivery succeeded.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-034 — stale

- Ticket: `TK-006`
- Acceptance: `AC-014`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:ca685b7a73d9eab23e1fb0ac5119c719caba228ffaf8e00f29a803824d39ceb4`
- Timestamp: `2026-09-28T15:20:26+00:00`
- Observations: After 24:00:01, public delivery became window_closed and exactly one private note was sent, including in observation mode; absent buyer timestamp closed safely.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-035 — stale

- Ticket: `TK-006`
- Acceptance: `AC-015`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:ca685b7a73d9eab23e1fb0ac5119c719caba228ffaf8e00f29a803824d39ceb4`
- Timestamp: `2026-09-28T15:20:27+00:00`
- Observations: A scheduled Chatwoot follow-up outside the window became window_closed during delivery, with no public POST, and revalidation returned window_closed.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-036 — passed

- Ticket: `TK-003`
- Acceptance: `AC-004`, `AC-005`, `AC-006`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_channel_pilot_supervisor.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:c850523524393c3d8b078b12d59cafa2148ab56160edf78cddb0083b84a7cf3e`
- Timestamp: `2026-09-28T15:33:16+00:00`
- Observations: 43 passed after media admission changes; timestamped, legacy and stale HMAC contracts remain green.
- Evidence refs: none
- Limitations: none recorded

## EV-037 — stale

- Ticket: `TK-004`
- Acceptance: `AC-007`, `AC-008`, `AC-009`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:525e51334d8698013f76a6ee45c928d5e94e932ef38802c69d8257a60dd57e46`
- Timestamp: `2026-09-28T15:33:16+00:00`
- Observations: 37 passed after media admission and conversation changes; own echo and human takeover contracts remain green.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-038 — passed

- Ticket: `TK-005`
- Acceptance: `AC-010`, `AC-011`, `AC-012`
- Procedure: `.venv/bin/python -m pytest -q tests/test_service.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:10561296e09db80c68146157dcc11a80d60d48204a2c8fa2b1fa5a3bcea3a93c`
- Timestamp: `2026-09-28T15:33:16+00:00`
- Observations: 5 passed after optional transcriber config; service ACK, readiness and SIGTERM restart contracts remain green.
- Evidence refs: none
- Limitations: none recorded

## EV-039 — stale

- Ticket: `TK-006`
- Acceptance: `AC-013`, `AC-014`, `AC-015`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:a5f5a380d1426cd98faf379cff4a6df9b8c13d892f3384f45d7c7165b70eede4`
- Timestamp: `2026-09-28T15:33:16+00:00`
- Observations: 29 passed after media event changes; WhatsApp window and follow-up remain green.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-040 — stale

- Ticket: `TK-007`
- Acceptance: `AC-016`
- Procedure: `.venv/bin/python -m pytest -q tests/test_non_text_messages.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:63336220dbeac5f18fd322cd7153b22ff9d7999db6c1aff8402a2116c6fd7e63`
- Timestamp: `2026-09-28T15:33:17+00:00`
- Observations: Audio without text was authenticated, admitted and answered by ask_text; metadata persisted in public state. offer_human package policy also passed.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-041 — stale

- Ticket: `TK-007`
- Acceptance: `AC-017`
- Procedure: `.venv/bin/python -m pytest -q tests/test_non_text_messages.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:63336220dbeac5f18fd322cd7153b22ff9d7999db6c1aff8402a2116c6fd7e63`
- Timestamp: `2026-09-28T15:33:17+00:00`
- Observations: Scripted audio transcription URL was sent to the transcriber; model interpreted transcript, trace marked transcribed, and buy effect required text confirmation.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-042 — stale

- Ticket: `TK-007`
- Acceptance: `AC-018`
- Procedure: `.venv/bin/python -m pytest -q tests/test_non_text_messages.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:63336220dbeac5f18fd322cd7153b22ff9d7999db6c1aff8402a2116c6fd7e63`
- Timestamp: `2026-09-28T15:33:17+00:00`
- Observations: Image with payment-proof caption left payment_verification pending and produced no confirmed payment or commercial action.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-043 — stale

- Ticket: `TK-004`
- Acceptance: `AC-007`, `AC-008`, `AC-009`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:f8034be3f80ef7d230d5adf013712fbbd0334b0b3b09ad7a5ca9669954973665`
- Timestamp: `2026-09-28T15:46:17+00:00`
- Observations: 37 passed after model trace changes; echo and human takeover contracts remain green.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-044 — stale

- Ticket: `TK-006`
- Acceptance: `AC-013`, `AC-014`, `AC-015`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:43444680222a16ba0a6c0b84bb5cdcb1fc7997abea761f47731c39899daf0225`
- Timestamp: `2026-09-28T15:46:17+00:00`
- Observations: 29 passed after model trace changes; WhatsApp delivery window remains green.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-045 — stale

- Ticket: `TK-007`
- Acceptance: `AC-016`, `AC-017`, `AC-018`
- Procedure: `.venv/bin/python -m pytest -q tests/test_non_text_messages.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:0dccfda1367d6f4a3588c8b1e6bde57bbaa4d0b3a50740886ff76dc6235b87ca`
- Timestamp: `2026-09-28T15:46:17+00:00`
- Observations: 33 passed after model trace changes; attachment and transcription policy remain green.
- Evidence refs: none
- Limitations: Evidence invalidated because an input changed.

## EV-046 — stale

- Ticket: `TK-008`
- Acceptance: `AC-019`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:7f62754b8c7cbf992cce862665de816bd7236024279d081fa21e403bfe3cbb9d`
- Timestamp: `2026-09-28T15:46:17+00:00`
- Observations: Captured Chat Completions body separates system instructions from delimited buyer message and sends strict JSON schema.
- Evidence refs: none
- Limitations: OpenAI real API not called; local fake HTTP contract only Evidence invalidated because an input changed.

## EV-047 — stale

- Ticket: `TK-008`
- Acceptance: `AC-020`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:7f62754b8c7cbf992cce862665de816bd7236024279d081fa21e403bfe3cbb9d`
- Timestamp: `2026-09-28T15:46:17+00:00`
- Observations: Scripted invalid then valid responses produced two calls, one repair instruction and accepted proposal.
- Evidence refs: none
- Limitations: OpenAI real API not called; local fake HTTP contract only Evidence invalidated because an input changed.

## EV-048 — stale

- Ticket: `TK-008`
- Acceptance: `AC-021`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:7f62754b8c7cbf992cce862665de816bd7236024279d081fa21e403bfe3cbb9d`
- Timestamp: `2026-09-28T15:46:18+00:00`
- Observations: Two invalid responses produced model_contract_failed trace, pending failure and no commercial action.
- Evidence refs: none
- Limitations: OpenAI real API not called; local fake HTTP contract only Evidence invalidated because an input changed.

## EV-049 — stale

- Ticket: `TK-008`
- Acceptance: `AC-022`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:7f62754b8c7cbf992cce862665de816bd7236024279d081fa21e403bfe3cbb9d`
- Timestamp: `2026-09-28T15:46:18+00:00`
- Observations: 1000 input and 200 output tokens with configured prices 1 and 5 per million produced cost 0.002.
- Evidence refs: none
- Limitations: OpenAI real API not called; local fake HTTP contract only Evidence invalidated because an input changed.

## EV-050 — stale

- Ticket: `TK-008`
- Acceptance: `AC-023`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:7f62754b8c7cbf992cce862665de816bd7236024279d081fa21e403bfe3cbb9d`
- Timestamp: `2026-09-28T15:46:18+00:00`
- Observations: Local response contract passed in openai and openai-compatible profiles; profile and model identity were reported. Real credential call not run.
- Evidence refs: none
- Limitations: OpenAI real API not called; local fake HTTP contract only Evidence invalidated because an input changed.

## EV-051 — stale

- Ticket: `TK-008`
- Acceptance: `AC-019`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:8cc7eb43689a1870ea1268ae584e3868bf15d9473fb5ff6e5e9c60168bc05397`
- Timestamp: `2026-09-28T15:48:13+00:00`
- Observations: System and user roles separated; buyer text inside buyer_message; strict schema in captured request.
- Evidence refs: none
- Limitations: Only local fake HTTP contract; no real OpenAI credential call Evidence invalidated because an input changed.

## EV-052 — stale

- Ticket: `TK-008`
- Acceptance: `AC-020`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:8cc7eb43689a1870ea1268ae584e3868bf15d9473fb5ff6e5e9c60168bc05397`
- Timestamp: `2026-09-28T15:48:13+00:00`
- Observations: One invalid then valid fake response required exactly two model calls and accepted the repaired proposal.
- Evidence refs: none
- Limitations: Only local fake HTTP contract; no real OpenAI credential call Evidence invalidated because an input changed.

## EV-053 — stale

- Ticket: `TK-008`
- Acceptance: `AC-021`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:8cc7eb43689a1870ea1268ae584e3868bf15d9473fb5ff6e5e9c60168bc05397`
- Timestamp: `2026-09-28T15:48:14+00:00`
- Observations: Two invalid fake responses produced model_contract_failed trace, pending failure, no action.
- Evidence refs: none
- Limitations: Only local fake HTTP contract; no real OpenAI credential call Evidence invalidated because an input changed.

## EV-054 — stale

- Ticket: `TK-008`
- Acceptance: `AC-022`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:8cc7eb43689a1870ea1268ae584e3868bf15d9473fb5ff6e5e9c60168bc05397`
- Timestamp: `2026-09-28T15:48:14+00:00`
- Observations: Configured prices 1 and 5 per million with 1000 and 200 tokens yielded cost 0.002.
- Evidence refs: none
- Limitations: Only local fake HTTP contract; no real OpenAI credential call Evidence invalidated because an input changed.

## EV-055 — stale

- Ticket: `TK-008`
- Acceptance: `AC-023`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:8cc7eb43689a1870ea1268ae584e3868bf15d9473fb5ff6e5e9c60168bc05397`
- Timestamp: `2026-09-28T15:48:14+00:00`
- Observations: Both openai and openai-compatible fake HTTP profiles returned model and profile; real API was not called.
- Evidence refs: none
- Limitations: Only local fake HTTP contract; no real OpenAI credential call Evidence invalidated because an input changed.

## EV-056 — passed

- Ticket: `TK-004`
- Acceptance: `AC-007`, `AC-008`, `AC-009`
- Procedure: `.venv/bin/python -m pytest -q tests/test_chatwoot_contract.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:4bd0fe0ae4a354872964b17d573a304cd61952e3192c73a0b6f003b3a1d5428c`
- Timestamp: `2026-09-28T15:50:47+00:00`
- Observations: 37 passed with latency trace added; echo and takeover behavior unchanged.
- Evidence refs: none
- Limitations: none recorded

## EV-057 — passed

- Ticket: `TK-006`
- Acceptance: `AC-013`, `AC-014`, `AC-015`
- Procedure: `.venv/bin/python -m pytest -q tests/test_channel_window.py tests/test_delivery_and_governance.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:af9d196cb2ed43243758eb794722df6e36bfbcf099a7b3832cee26a336aaec22`
- Timestamp: `2026-09-28T15:50:47+00:00`
- Observations: 29 passed with latency trace added; WhatsApp window unchanged.
- Evidence refs: none
- Limitations: none recorded

## EV-058 — passed

- Ticket: `TK-007`
- Acceptance: `AC-016`, `AC-017`, `AC-018`
- Procedure: `.venv/bin/python -m pytest -q tests/test_non_text_messages.py tests/test_conversation_contract.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:2396a4a193a4de0b1172e44e40517305e902a6e42bbcf9b9a6498b140754d96b`
- Timestamp: `2026-09-28T15:50:47+00:00`
- Observations: 33 passed with latency trace added; non-text handling unchanged.
- Evidence refs: none
- Limitations: none recorded

## EV-059 — passed

- Ticket: `TK-008`
- Acceptance: `AC-019`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:abe6e9a2f2d85eb6329df42355ebfe81a3873b6c480c8624a3612c1fd99f0913`
- Timestamp: `2026-09-28T15:50:48+00:00`
- Observations: System and user roles separated; buyer text delimited and strict JSON schema sent.
- Evidence refs: none
- Limitations: Local fake HTTP only; real OpenAI call not run

## EV-060 — passed

- Ticket: `TK-008`
- Acceptance: `AC-020`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:abe6e9a2f2d85eb6329df42355ebfe81a3873b6c480c8624a3612c1fd99f0913`
- Timestamp: `2026-09-28T15:50:48+00:00`
- Observations: Invalid then valid response repaired with exactly two calls.
- Evidence refs: none
- Limitations: Local fake HTTP only; real OpenAI call not run

## EV-061 — passed

- Ticket: `TK-008`
- Acceptance: `AC-021`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:abe6e9a2f2d85eb6329df42355ebfe81a3873b6c480c8624a3612c1fd99f0913`
- Timestamp: `2026-09-28T15:50:48+00:00`
- Observations: Two invalid responses yielded model_contract_failed trace and no action.
- Evidence refs: none
- Limitations: Local fake HTTP only; real OpenAI call not run

## EV-062 — passed

- Ticket: `TK-008`
- Acceptance: `AC-022`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:abe6e9a2f2d85eb6329df42355ebfe81a3873b6c480c8624a3612c1fd99f0913`
- Timestamp: `2026-09-28T15:50:48+00:00`
- Observations: Usage 1000/200 with configured prices 1/5 per million yielded cost 0.002; latency tracked.
- Evidence refs: none
- Limitations: Local fake HTTP only; real OpenAI call not run

## EV-063 — passed

- Ticket: `TK-008`
- Acceptance: `AC-023`
- Procedure: `.venv/bin/python -m pytest -q tests/test_model_adapter.py`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.9.25
- Tested revision: `local:abe6e9a2f2d85eb6329df42355ebfe81a3873b6c480c8624a3612c1fd99f0913`
- Timestamp: `2026-09-28T15:50:49+00:00`
- Observations: Both OpenAI and compatible profiles passed local HTTP contract with model/profile metadata; no real API call.
- Evidence refs: none
- Limitations: Local fake HTTP only; real OpenAI call not run
