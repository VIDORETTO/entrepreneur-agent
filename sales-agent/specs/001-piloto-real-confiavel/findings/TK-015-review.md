# TK-015 review

Baseline: `fb39f90`; reviewed working diff and new readiness tests.

## Standards

No blocking findings. The pilot remains disabled without explicit authorization. Readiness checks the current package fingerprint, versioned holdout hash, selected model/profile, timestamped channel contract, hours, privacy and interruption evidence. Override requires a reason and persists it with the missing requirements. Existing local pilot tests now declare an override in setup; their delivery, accounting, and interruption assertions remain in place. Full regression: 243 passed; Ruff passed.

## Spec

No blocking findings for AC-038–AC-040. EV-119–EV-121 cover rejection of `rules-v1`, acceptance of a complete local evidence fixture, and CLI code 2 versus audited override. Tests do not represent real OpenAI or Chatwoot execution. Actual pilot readiness remains false until real evidence is supplied.
