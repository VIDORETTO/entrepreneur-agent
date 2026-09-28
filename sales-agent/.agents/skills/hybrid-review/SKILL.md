---
name: hybrid-review
description: Review a hybrid effort against repository Standards and accepted Spec in separate passes over a fixed baseline, including committed, staged, unstaged, and relevant new files. Use for pre-commit review, work-in-progress review, or a ready diff.
disable-model-invocation: true
---

# Hybrid review

Review is an evidence/reporting phase. It does not implement fixes, publish comments, merge, or deploy when the request is review-only.

## Fix the scope

Read the request, effort state, `review.md` if present, contract and plan, applicable `AGENTS.md`/standards, and [operating-contract.md](../../shared/references/operating-contract.md). Resolve and record one baseline before inspecting the diff:

- Git repository: use the supplied SHA/branch/tag or current `HEAD` only when that is the explicitly requested baseline; capture `git rev-parse`, `git diff <baseline>...HEAD`, `git diff --cached`, `git diff`, and `git status --short` so new files are not hidden.
- No Git: record an inventory fingerprint and the exact included paths. Do not claim a SHA.

Never call `git diff HEAD` alone evidence that there are no changes. Preserve the baseline across correction rounds.

## Two independent axes

Standards asks whether the diff violates documented project rules or exposes a contextualized design risk. A smell baseline is a judgement call and a repository standard overrides it. Spec asks whether accepted requirements/acceptance are missing, partial, incorrect, or exceeded; if no spec exists, report that limit instead of manufacturing one. Keep axes and severities separate. Every finding cites file/symbol/hunk, rule or `FR`/`AC`, consequence, and state.

Review tests for independent oracles and weakened expectations, review changed acceptance markers for ownership, and include code in commits, staged, unstaged, and relevant new files. Use `finding add` with origin `standards` or `spec` only for actionable local records; deduplicate before creating correction work. Correcting an in-scope finding is a separate authorized implementation action, followed by the affected checks.

Return the two-axis report path/revision, baseline, findings, evidence refs, limitations, and next action. A passing test suite alone does not make the Spec axis pass, and a style preference alone is not a blocking violation.
