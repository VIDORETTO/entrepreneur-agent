---
name: hybrid-implement
description: Execute one ready hybrid ticket as a focused vertical slice with behavior-first tests, minimal code, checkpoints, and honest status updates. Use when implementing an accepted ticket in a standard effort or the equivalent compact change.
disable-model-invocation: true
---

# Hybrid implement

The ticket is the execution context. Do not require the original planning conversation. Read [execution-package.md](../../shared/references/execution-package.md) and [testing.md](../../shared/references/testing.md), the applicable repository instructions, the ticket, its referenced contract/plan sections, and only the listed code paths first.

## Preconditions

For a standard effort, run `package --project . --effort <id> --ticket TK-xxx --json` and `graph --effort <id> --json`. For a compact effort, read and validate the active `change.md` directly; it has no ticket or graph. Confirm readiness, predecessors where applicable, paths/symbols, and input revisions. If a precondition fails, preserve edits and return a focused blocker. Move a standard ticket to `in_progress` through the runner; a state update is not evidence of implementation.

## Execute one behavior at a time

1. Write the next behavior case at the agreed seam with an independent literal, property, or accepted example. Do not mock internal Modules or verify a side channel.
2. Run it and confirm red is caused by missing/incorrect behavior. An environment or missing-file error is not valid red; fix the environment or return it.
3. Implement the smallest compatible change. Keep the executor's freedom to local reversible details, but never alter acceptance text, expected results, scope, or a public/data contract silently.
4. Run green and the focused regression. A small refactor is allowed only with the relevant suite green; a wide structural change becomes an explicit ticket.
5. Checkpoint the next concrete step. Keep task checkboxes and ticket status truthful; do not mark a reviewer checklist in the executor's name.

For bug, refactor, migration, prototype, UI, persistence, and external integration routes, follow the conditional contract in the ticket and preserve its limits. For a new decision, incompatible path, unplanned dependency, unavailable required resource, or repeated failure without new evidence, record completed work and return to the planner with path/symbol, step, impact, and decision needed.

Do not commit, publish, merge, deploy, or modify user-owned unrelated changes by default. Return changed files/symbols, ticket state, criteria addressed, executed evidence refs, pending work, and next action. Leave `implemented` until `hybrid-verify` supplies current evidence.
