# Verification

<!-- GENERATED from evidence/*.json. Evidence records are canonical. -->

## EV-001 — passed

- Ticket: `—`
- Acceptance: `AC-001`, `AC-002`, `AC-003`, `AC-004`, `AC-005`, `AC-006`, `AC-007`, `AC-008`, `AC-009`
- Procedure: `.venv/bin/python -m pytest -q tests/test_agent_workspace.py && .venv/bin/python -m pytest -q && .venv/bin/ruff check src tests`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:c7c867e3fad8d790cdc3637e42eddd7fac1eda982bda08c11dca9886a39aebac`
- Timestamp: `2026-09-29T11:50:19+00:00`
- Observations: 14 testes novos passam (red inicial: 'invalid choice: install'); suíte completa 260 passed; ruff ok; 14 passed também com --clock-shift-days=400; evaluate --split dev 50/50
- Evidence refs: none
- Limitations: none recorded

## EV-002 — passed

- Ticket: `—`
- Acceptance: `AC-010`
- Procedure: `python -m build --wheel; venv limpo com pip install da wheel; vendedor skills doctor/list/install --target all/status em diretório vazio; unzip -l da wheel`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:db70fa0e6c27b82f4bdc63f291fb1520feb7f570b043c9350f9280a0341776f0`
- Timestamp: `2026-09-29T11:50:19+00:00`
- Observations: wheel contém sales_agent/resources/workspace/AGENTS.md e as 6 skills novas em share/vendedor-adaptavel/skills; skills list=11; install grava 42 arquivos, status ok=true
- Evidence refs: none
- Limitations: none recorded

## EV-003 — passed

- Ticket: `—`
- Acceptance: `AC-001`, `AC-002`, `AC-003`, `AC-004`, `AC-005`, `AC-006`, `AC-007`, `AC-008`, `AC-009`
- Procedure: `.venv/bin/python -m pytest -q tests/test_agent_workspace.py && .venv/bin/python -m pytest -q && .venv/bin/ruff check src tests`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:4dbb6df258fe4496e919cb007f3e8b61924901199e7bbd1ba41ad01b6029e9f2`
- Timestamp: `2026-09-29T11:52:13+00:00`
- Observations: 14 passed in 0.49s; suíte completa: 260 passed in 97.17s (0:01:37); ruff: All checks passed!; red inicial observado: 'invalid choice: install'
- Evidence refs: none
- Limitations: none recorded

## EV-004 — passed

- Ticket: `—`
- Acceptance: `AC-010`
- Procedure: `python -m build --wheel; venv limpo com pip install da wheel; vendedor skills doctor/list/install --target all/status em diretório vazio; unzip -l da wheel (executado nesta sessão contra o mesmo código-fonte)`
- Execution: `executed`
- Environment: OS=Linux-5.14.0-687.36.1.el9_8.x86_64-x86_64-with-glibc2.34; Python=3.12.14
- Tested revision: `local:8ac89dbb6867860e05bbf0f94c255d7316537bcbb1a80b1ef35d5a69a7608f2d`
- Timestamp: `2026-09-29T11:52:13+00:00`
- Observations: wheel contém sales_agent/resources/workspace/AGENTS.md e as 6 skills novas em share/vendedor-adaptavel/skills; skills list=11; install grava 42 arquivos, status ok=true
- Evidence refs: none
- Limitations: none recorded
