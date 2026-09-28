# TK-014 review

Baseline: `3864792`; reviewed committed baseline, working diff, and new privacy module/tests.

## Standards

No blocking findings. Subject operations are scoped by business and exact contact, erase runs in one SQLite transaction, pseudonyms use HMAC with a private local key, and metrics remain unchanged. The API redacts common Brazilian identifiers from evaluation and operator reports. Final full regression: 238 passed; Ruff passed.

## Spec

No blocking findings for AC-045–AC-048. EV-111–EV-118 cover scoped export, erase with effect pseudonym and stable metrics, report redaction, and 30-day purge retaining pending outbox. A fifth test covers queued inbound messages before conversation creation. The regex redactor is a best-effort guard for the listed identifier forms; operator exports intentionally contain the requested subject's data.
