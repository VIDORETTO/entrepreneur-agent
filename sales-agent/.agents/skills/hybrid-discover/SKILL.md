---
name: hybrid-discover
description: Clarify a development demand, its outcome, constraints, hypotheses, and material decisions before specification. Use for vague ideas, new projects, ambiguous features, research, prototypes, bugs with uncertain expectations, or migrations with open compatibility questions.
disable-model-invocation: true
---

# Hybrid discovery

Turn the demand into enough shared understanding for the next deliverable. Keep discovery proportional; a clear small function does not need a product interview.

## Inputs and reading

Read the request, the `hybrid-start` reconnaissance, existing project instructions, relevant glossary and ADRs, and only the code/documents needed to test the stated assumptions. Read [routing.md](../../shared/references/routing.md) and [vocabulary.md](../../shared/references/vocabulary.md).

## Process

1. Classify facts that can be inspected from choices that belong to the user. Check facts against the repository instead of asking for them.
2. State the problem, actors/consumer, desired result, included and excluded scope, constraints, non-goals, dependencies, and success signal.
3. Build a decision tree. Rank questions by impact × uncertainty, group independent questions, and wait for a dependent answer. Recommend an option and state its consequence. Never invent a critical choice to keep moving.
4. For an idea, include evidence for and against it, the cost of inaction, a bounded alternative, and a continue/stop criterion. For a bug, distinguish expected behavior from observed behavior and record the reproduction. For research, define an experiment and stopping limit. For migration, list consumers and expand–contract assumptions.
5. Record resolved decisions, reversible hypotheses with a check, and material questions. Do not implement while interviewing.

Write the local discovery/brief artifact only when it has information a later phase must consume; preserve existing text and revisions. Hand domain terms and durable decisions to `hybrid-domain`, then hand behavior to `hybrid-specify`. Do not put technical solution details in the behavior contract.

## Exit gate

Finish when no unresolved ambiguity materially changes the next behavior, validation, or authorization. Future-work questions may remain open. If the user decides not to build, record the reason and close the evaluation without manufacturing a spec.

Return the shared protocol, including `needs_input` for a material choice and `blocked` for an external resource. A resumed discovery reads its checkpoint and does not repeat answered questions.
