---
name: hybrid-slice
description: Decompose an accepted hybrid contract and plan into vertical execution tickets with stable IDs, real blockers, concrete code context, and generated task views. Use when a standard or expanded effort is ready to become executable by a fresh session or a lower-cost AI.
disable-model-invocation: true
---

# Hybrid slice

In the standard profile, ticket files are the single editable source for delivery, subtasks, and ticket state. `todo.md` is generated from them. `backlog.md` is generated from efforts. In compact mode, keep all work in `change.md` and do not create parallel tickets.

## Build the graph

Read `spec.md`, `plan.md`, referenced research/contracts/data model, domain language, applicable instructions, and [execution-package.md](../../shared/references/execution-package.md). Choose the first valuable or risk-reducing behavior. Each ticket is a demonstrable vertical slice through the modules it actually uses; a library function may be one public function and its behavior tests. Do not split database/backend/frontend by habit.

For each ticket use `python <package-root>/scripts/hybrid.py next-id --project . --effort <id> --prefix TK --json`, then fill [the ticket template](../../shared/templates/standard/ticket.md). Preserve IDs and include:

- objective, explicit exclusions, ordered reading with verified paths and symbols, decisions already resolved, freedom left to the executor, and existing/new change map;
- exact inputs, outputs, invariants, errors, effects, compatibility, concurrency/idempotency;
- independent examples for every `AC` ref, real dependencies, sequence of red → green steps, exact validation, and return-to-planner conditions;
- `requires` edges only for genuine blockers. Use expand–contract for a wide mechanical migration. A predecessor is executable only after `done`.

Do not mark a ticket `ready` while it asks the executor to choose authentication, concurrency, a public contract, or another material design. Set it `blocked` or return the choice to planning.

## Validate and project

Run `validate`, `graph`, and `package` for each candidate. The graph must be acyclic, every acceptance in the selected scope must have a ticket, and the frontier must be explainable. Treat `owned_area_overlaps` as a coordination signal: serialize the tickets or add a real blocker when concurrent writes could conflict. Run `render --view todo` and `render --view backlog`; generated views are not edit targets. A write conflict means preserve the existing edit and reconcile explicitly.

G3 passes only for current inputs, satisfied blockers, verified references, and complete execution packages. Return ticket paths/revisions, graph/frontier, generated views, findings, and next action. No tracker or remote publication is performed in this version.
