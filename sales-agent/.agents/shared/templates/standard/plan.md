---
schema: hybrid/plan
schema_version: "1.0"
effort_id: [EFFORT_ID]
revision: 1
spec_revision: [SPEC_REVISION]
status: draft
---

# Plan: [TITLE]

## Summary

State how the chosen solution will satisfy the accepted behavior, after research.

## Technical context

- Language/runtime: [observed]
- Dependencies: [observed; consult current docs when relevant]
- Storage/data: [observed or N/A]
- Test command: [verified command or `identified but not executed`]
- Target/platform: [observed]

## Consumed contract

- Spec: `spec.md`, revision [N]
- Requirements and acceptance refs: [FR/AC IDs]

## Modules, interfaces, consumers, and seams

For each Module, name the Interface consumers need, the Implementation behind it, the existing consumers, and the highest seam that remains fast, deterministic, and diagnostic. Record predicted symbols and distinguish existing from new.

## Chosen approach and alternatives

Describe the selected design, why it fits this codebase, and real alternatives rejected. Keep behavior in the spec and technical choices here.

## Data, compatibility, and external dependencies

Describe migrations, expand–contract steps, adapters, retries, ordering, idempotency, concurrency, and compatibility obligations when applicable.

## Verification strategy

Map every AC to a behavior-level test or explicit manual procedure. State the independent oracle, environment, exact command, expected result, and what a failure means. A command observed in configuration is not an executed result.

## Change map

| Path | Existing/new | Symbol or section | Purpose | Reference revision |
| --- | --- | --- | --- | --- |
| [path] | existing/new | [symbol] | [reason] | [date or SHA] |

## Derived technical obligations

- **OT-001** → [FR/AC refs]: [obligation that a ticket must fulfill].

## Risks and gates

List blockers for the next slice, evidence required for G2/G3, and residual uncertainty. Do not hide a blocking design decision as an implementation detail.
