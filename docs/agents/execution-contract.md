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
5. `docs/agents/lifecycle-vsa.md` when the issue changes ingest, document/version identity, review, repair, readiness, publication, serving, migration, reconciliation, recovery, supersession, withdrawal, or lifecycle UI/API state.

Architecture conflicts must be surfaced, not silently overridden.

## Vertical-slice completeness

When a user promise crosses architectural layers, the implementation must be completed and verified as a vertical slice. Trace the behavior through the layers that are actually required by that promise:

`trigger -> authorization -> validation -> domain transition -> API/backend -> durable write -> concurrency/recovery -> deterministic follow-up -> observable result`

A frontend-only, API-only, backend-only, or storage-only implementation is incomplete when other layers are necessary for the promised behavior. Do not substitute process memory for durable PostgreSQL-backed state when persistence is required.

For lifecycle work, this generic path is necessary but not sufficient. `docs/agents/lifecycle-vsa.md` is normative and defines the entities, authorities, allowed states, immutability rules, successor-version semantics, supersession, withdrawal, restart/recovery requirements, mandatory slice fields, stop conditions, and black-box lifecycle proof.

A lifecycle vertical slice is one exact lifecycle transition, not one technical component. A status, page, endpoint, database column, helper, migration, or isolated gate is not by itself a complete lifecycle slice.

## Completion gate

A task is not complete merely because a UI, endpoint, or happy-path code branch exists. Where relevant, the implementation must cover and verify:

- backend behavior;
- durable persistence;
- deterministic state transitions and follow-up actions;
- concurrency and recovery behavior;
- failure/abstention paths;
- an observable result consistent with the user promise;
- tests that prove the promised behavior end to end where practical.

For lifecycle work, every relevant Definition-of-Done item in `docs/agents/lifecycle-vsa.md` must be proven. Any relevant `FAIL`, `UNKNOWN`, or `NOT TESTED` means the slice is not done.

The agent must run the normal repository verification sequence before opening a PR and must not merge its own PR.

## Fail-closed lifecycle rule

For lifecycle work, the agent must stop before implementation when the assigned issue leaves a required lifecycle, identity, authority, supersession, withdrawal, migration, or recovery decision undefined. The agent must not fill such a gap with a reasonable assumption.

Published work must not be mutated in place. Current serving eligibility is determined only by the publication registry. Successor work, policy re-evaluation, supersession, and withdrawal must follow `docs/agents/lifecycle-vsa.md`.

## Infrastructure boundary

The default agent run is repository-only. It must not deploy, mutate Azure or production resources, rotate secrets, or incur new paid infrastructure without an explicitly scoped issue and human approval.
