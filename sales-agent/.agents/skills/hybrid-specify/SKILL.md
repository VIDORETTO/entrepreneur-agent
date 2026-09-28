---
name: hybrid-specify
description: Write and evolve a versioned behavioral contract with stable requirements and acceptance criteria for a hybrid development effort. Use after discovery or when an existing spec/change needs creation, clarification, bug expectation, migration scope, or contract reconciliation.
disable-model-invocation: true
---

# Hybrid specify

Own the behavior contract. `spec.md` is canonical for standard/expanded efforts; `change.md` is canonical for a compact effort. Do not choose the whole technical architecture here.

## Read first

Read the discovery result, `CONTEXT.md`/map, applicable ADRs and repository instructions, current code facts needed to avoid describing the wrong system, and [operating-contract.md](../../shared/references/operating-contract.md). Read [the standard template](../../shared/templates/standard/spec.md) or [the compact template](../../shared/templates/compact/change.md) as appropriate.

## Write the contract

Capture:

- problem, desired result, consumer/actors, prioritized journeys or a direct function contract;
- included scope, explicit exclusions, errors, limits, compatibility, idempotency and concurrency when relevant;
- stable `FR-xxx` requirements and `AC-xxx` observable criteria, including primary, alternate, error, recovery, and relevant non-functional cases;
- hypotheses, dependencies, product decisions, and delivery-verifiable success separated from post-delivery metrics.

For a function, define inputs, outputs, invariants, errors, units, rounding, and compatibility directly. Do not invent a persona when the caller contract is clearer. Keep technical design, file structure, adapters, and test seams in `plan.md`; keep prototype state explicit.

Never renumber an existing ID because a new item was inserted. Increment contract `revision` for a meaningful update. A change to semantics requires reconciliation with plans, tickets, tests, and evidence; an editorial change may retain executable evidence with a recorded reason. If acceptance changes, stop downstream reuse until invalidation is evaluated.

Run `python <package-root>/scripts/hybrid.py validate --project . --effort <id> --json` after editing. In compact mode do not create parallel `plan.md`, `tasks.md`, or tickets merely to imitate standard ceremony.

## Gate and output

G1 passes only when behavior and criteria are coherent, testable, bounded, and no critical choice is silently assumed. The user's already-given behavior and authorization remain valid; ask only for a material missing decision.

Return the protocol with contract path/revision, unresolved questions, affected dependents, and next action (`hybrid-plan`/`hybrid-slice`, or compact implementation). Do not publish remotely in this local version.
