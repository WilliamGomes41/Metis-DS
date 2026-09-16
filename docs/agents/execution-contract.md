# Agent execution contract

This repository separates **triage state** from **execution**.

`ready-for-agent` means an issue is sufficiently specified for an autonomous coding run. It does **not** start an agent by itself.

## Start condition

A coding run starts only when a human or approved orchestration layer explicitly assigns one issue to the `Metis Engineer` custom agent.

The agent must verify that the issue:

- is open;
- has `ready-for-agent`;
- does not also have `needs-triage`, `needs-info`, `ready-for-human`, or `wontfix`;
- is an implementation ticket rather than a parent spec, decision map, research task, or other `wayfinder:*` planning ticket.

If these conditions are not met, the agent must stop without modifying code.

## One issue, one run

Each run is scoped to exactly one explicitly assigned issue. The agent may read linked issues for context, but it must not absorb adjacent backlog items into the implementation.

## Required repository context

Before implementation, the agent reads:

1. `AGENTS.md` and relevant linked agent docs;
2. the assigned issue and comments;
3. `CONTEXT.md` or relevant `CONTEXT-MAP.md` entries;
4. applicable ADRs;
5. `docs/agents/continuous-development.md`, classifies the issue as A, B, or C, and determines `Rewrite risk: none | high`;
6. `docs/agents/lifecycle-vsa.md` in full when the issue is Class A.

Architecture conflicts must be surfaced, not silently overridden.

## Change-class and rewrite-risk rule

The default development model is `docs/agents/continuous-development.md`.

- Class A = lifecycle core. Apply the full lifecycle-VSA contract.
- Class B = normal product behavior. Prove the user/system promise with the smallest coherent implementation and relevant tests; do not add lifecycle-grade paperwork unless lifecycle semantics actually change.
- Class C = cosmetic/documentation/non-semantic maintenance. Keep the diff and proof proportionate to the change.

Every implementation issue also states `Rewrite risk: none | high`. Rewrite risk is semantic, not based on line count. Replacing or redefining a durable authority, persisted identity/schema semantics, a shared cross-topology mutation/read boundary, a lifecycle/publication/retrieval kernel, or a migration/cutover that affects restart/recovery is high risk.

High-risk rewrite work MUST complete the system map, compatibility/migration, rollback/recovery, cutover, cleanup, failure-blast-radius, and adversarial-proof fields in `docs/agents/continuous-development.md` before code changes. Prefer staged expand/migrate/contract or additive/strangler migration. Big-bang replacement is forbidden by default.

If Class B or C work reveals that a lifecycle invariant, document/version identity, durable authority, supersession, withdrawal, migration, reconciliation, or lifecycle recovery rule must change, the agent must STOP and reclassify the issue before continuing. If work initially marked `Rewrite risk: none` becomes high risk, the agent must STOP and rescope before adding more code.

## Vertical-slice completeness

When a user promise crosses architectural layers, the implementation must be completed and verified as a vertical slice. Trace the behavior through the layers actually required by that promise:

`trigger -> authorization -> validation -> domain transition -> API/backend -> durable write -> concurrency/recovery -> deterministic follow-up -> observable result`

A frontend-only, API-only, backend-only, or storage-only implementation is incomplete when other layers are necessary for the promised behavior. Do not substitute process memory for durable PostgreSQL-backed state when persistence is required.

Vertical slicing defines promise completeness, not mandatory PR size. Technical prerequisites MAY be delivered in multiple small PRs when that lowers risk, but the product promise MUST NOT be called complete until the required end-to-end proof passes.

For Class A lifecycle work, the generic path is necessary but not sufficient. `docs/agents/lifecycle-vsa.md` is normative and defines the entities, authorities, allowed states, immutability rules, successor-version semantics, supersession, withdrawal, restart/recovery requirements, rewrite-risk overlay, mandatory slice fields, stop conditions, and black-box lifecycle proof.

## Completion gate

A task is not complete merely because a UI, endpoint, or happy-path code branch exists. Where relevant, the implementation must cover and verify the layers required by the promise.

For Class A, every relevant Definition-of-Done item in `docs/agents/lifecycle-vsa.md` must be proven. Any relevant `FAIL`, `UNKNOWN`, or `NOT TESTED` means the slice is not done.

For Class B, tests and acceptance evidence MUST be limited to what is necessary to prove the stated user/system promise and prevent its relevant regressions.

For Class C, focused artifact/contract verification plus mandatory repository checks is sufficient unless the change modifies governance semantics.

For `Rewrite risk: high`, completion additionally requires a separate adversarial review pass that tries alternate writers/readers, inheritance/override/fallback paths, supported runtime/storage topologies, stale local versus durable state, duplicate authorities, partial cutover, restart, recovery, rollback, and failed cutover. Green CI alone is insufficient evidence that a high-risk rewrite is complete.

The agent must run the normal repository verification sequence before opening a PR and must not merge its own PR.

## Cost and architecture discipline

The agent MUST follow the cost-control, rewrite-risk, and stop-loss rules in `docs/agents/continuous-development.md`.

In particular, do not create a new architecture rule, durable authority, abstraction layer, gate, or adjacent cleanup program unless the assigned promise or a named invariant requires it. Prefer reuse, consolidation, and deletion over parallel mechanisms.

Temporary dual-read or dual-write behavior is acceptable only when one authority remains named, divergence is detectable, reconciliation is deterministic, and removal criteria are defined. A mirror, cache, envelope, projection, or fallback must not silently become a second source of truth.

Destructive or irreversible migration must not be executed autonomously. It requires explicit human approval and tested backup/recovery evidence before execution.

## Fail-closed lifecycle rule

For Class A work, the agent must stop before implementation when the assigned issue leaves a required lifecycle, identity, authority, supersession, withdrawal, migration, recovery, or high-risk rewrite decision undefined. The agent must not fill such a gap with a reasonable assumption.

Published work must not be mutated in place. Current serving eligibility is determined only by the publication registry. Successor work, policy re-evaluation, supersession, and withdrawal must follow `docs/agents/lifecycle-vsa.md`.

## Infrastructure boundary

The default agent run is repository-only. It must not deploy, mutate Azure or production resources, rotate secrets, or incur new paid infrastructure without an explicitly scoped issue and human approval.
