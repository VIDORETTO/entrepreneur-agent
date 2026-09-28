---
name: hybrid-plan
description: Design the technical solution for an accepted hybrid contract by mapping modules, interfaces, consumers, seams, risks, compatibility, and executable verification. Use when a standard or expanded effort needs a plan, research, data model, contract, migration strategy, or technical decision.
disable-model-invocation: true
---

# Hybrid plan

Own the technical solution. It consumes a sufficiently clear contract and produces `plan.md` plus only the research, data model, or contracts that the next slices need.

## Explore

Read the accepted `spec.md` (or the compact plan section), current code and tests around the affected behavior, applicable instructions, `CONTEXT.md`, ADRs, and [testing.md](../../shared/references/testing.md). Verify paths and symbols; label existing and new symbols. Use the smallest context that supports the next slice.

Identify Modules, their Interfaces, consumers, effects, compatibility, and the highest seam that remains fast, deterministic, and diagnostic. Use depth, leverage, locality, and the two-adapter rule. Choose production/test adapters only where a real variation exists. For persistence, concurrency, external integration, visual behavior, or public compatibility, state the representative evidence required.

When a library, SDK, API, CLI, or cloud service affects the decision, use Context7: resolve the library ID, query the complete question, and record the version and source. If the result is insufficient, retry with research mode when available or consult primary documentation; report a missing tool when it prevents verification. Do not turn research into an undigested documentation dump.

## Plan

Write `plan.md` with the consumed spec revision, chosen approach and real alternatives, module/interface map, change locations, derived technical obligations, data/migration and external dependency strategy, seams and independent oracles, exact validation commands, environment requirements, risks, and G2 gate. Distinguish a command observed in project configuration from one actually executed. A path is a locator, not permission to edit the whole area.

For wide refactors/migrations use expand–contract and real batches. Create only prerequisites that the next vertical slice needs. If implementation discovers a behavior change, return to `hybrid-specify`; a reversible local detail can update the plan with its reason.

Register any new canonical input with `checkpoint write --input plan=specs/<id>/plan.md`, then run `validate --effort <id> --json` and prepare the next ticket context. Return findings, research refs, plan revision, and limitations. Do not implement application code or change the contract to make the plan fit.
