---
name: hybrid-check
description: Analyze hybrid artifacts for cross-document inconsistencies or implementation gaps, persist actionable findings, and deduplicate repeated convergence work. Use before implementation for consistency or after changes for convergence.
disable-model-invocation: true
---

# Hybrid check

This skill has two explicit modes. `consistency` compares contract, plan, tickets, IDs, references, ownership, and graph. `convergence` compares accepted behavior with current code/evidence and detects missing or stale coverage. Neither mode edits the contract to conceal a gap.

## Run deterministic checks

Read the relevant effort, state, instructions, and [operating-contract.md](../../shared/references/operating-contract.md). Run:

```text
python <package-root>/scripts/hybrid.py validate --project . --effort <id> --json
python <package-root>/scripts/hybrid.py check --project . --effort <id> --mode consistency --json
python <package-root>/scripts/hybrid.py check --project . --effort <id> --mode convergence --json
```

Use `--write` only when the user authorized maintaining local findings. Finding records use `FD-xxx`; before adding one run the same key through `finding add` or let `check --write` deduplicate it. The identity is effort + origin + gap type + affected area, with an explicit semantic discriminator only when two real gaps share that key. Existing open correction tickets remain canonical.

## Semantic analysis

Report requirements without tickets, acceptance criteria without a strategy/evidence, tasks without a reason, contradictory revisions, cycles, stale generated views, stale evidence, scope expansion, and code behavior that is missing, partial, contradictory, or unrequested. A checked box, passing schema, or sentence in a skill is not proof that behavior works. Code review and convergence findings must cite path/symbol, criterion or rule, consequence, severity, and correction owner.

Do not change `spec.md`, `plan.md`, or acceptance markers in this skill. A consistency request reports only; an authorized implementation cycle can route routine documentation fixes to their owner. If repeated convergence has no new evidence, revisit the hypothesis instead of creating another identical task.

Return mode, findings, created/deduplicated IDs, evidence refs, and the next gate. Preserve `state.json` and use `invalidate --write` when an input change affects evidence.
