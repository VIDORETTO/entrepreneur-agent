---
name: hybrid-domain
description: Maintain the project's domain glossary and selective architecture decision records while preserving bounded-context language. Use when a term is resolved, terminology conflicts, or a hard-to-reverse technical decision needs durable context.
disable-model-invocation: true
---

# Hybrid domain

Own `CONTEXT.md`, `CONTEXT-MAP.md` when it genuinely exists, and ADRs. This skill does not write a feature spec, implementation plan, or ticket.

## Read and decide

Read [vocabulary.md](../../shared/references/vocabulary.md), [domain-records.md](../../shared/references/domain-records.md), the existing context map/glossary, applicable instructions, and the relevant code only to detect terminology conflicts. Keep definitions in the project's language.

When a term is resolved, update the appropriate `CONTEXT.md` lazily. Define what the concept is in one or two sentences, choose one canonical term, and list ambiguous alternatives under `_Avoid_`. If multiple contexts exist, use the map and edit the owner context; ask only when ownership is materially unclear. Do not add implementation details, generic programming concepts, or temporary brainstorming.

Offer an ADR only when all three conditions hold: the choice is hard to reverse, surprising without context, and follows a real trade-off. Number `docs/adr/NNNN-slug.md` from the highest existing number plus one. Record context, decision, and reason; add rejected options or consequences only when they will help a future reader. A reversible local preference belongs in `plan.md`.

If the code and the proposed language disagree, report the exact path/symbol and classify whether the code is observed behavior or a decision to change. Do not silently make the glossary describe the intended future behavior.

## Exit and resumption

The gate passes when affected artifacts use one consistent vocabulary and every new ADR has a durable reason. Preserve user edits and update the checkpoint when this is part of an active effort. A later phase reads these files by path and revision; it does not need the conversation.

Return changed paths/revisions, terminology conflicts, ADR refs, and the next owner. A request only to read a glossary does not enter this skill.
