# Holdout manifest correction review

Baseline: `fb3935d`; reviewed all changed, staged and new files for the holdout checksum correction.

## Standards

No blocking findings. `PilotController.readiness` reads the versioned checksum and file metadata, without opening the reserved holdout corpus. The evaluator reads the corpus only for the `holdout` split, checks the published SHA-256, and rejects a file changed during its read. The checksum is included in the wheel. The focused suite passed 24 tests, the full suite passed 246 tests, and Ruff passed.

## Spec

No blocking findings. This corrects the GOAL-PROMPT rule that only `evaluate --split holdout` may read `evaluation/holdout.json`. AC-035–AC-037 and AC-038–AC-040 have current executed evidence EV-139–EV-140. The local holdout passed 30/30 cases across 120/120 runs; it does not establish remote model quality. AC-003 still depends on GitHub Actions after a push, which the goal prohibits.
