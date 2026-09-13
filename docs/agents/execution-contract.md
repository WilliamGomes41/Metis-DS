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
4. applicable ADRs.

Architecture conflicts must be surfaced, not silently overridden.

## Vertical-slice completeness

When a user promise crosses architectural layers, the implementation must be completed and verified as a vertical slice. Trace the behavior through the layers that are actually required by that promise:

`trigger -> authorization -> validation -> domain transition -> API/backend -> durable write -> concurrency/recovery -> deterministic follow-up -> observable result`

A frontend-only, API-only, backend-only, or storage-only implementation is incomplete when other layers are necessary for the promised behavior. Do not substitute process memory for durable PostgreSQL-backed state when persistence is required.

## Completion gate

A task is not complete merely because a UI, endpoint, or happy-path code branch exists. Where relevant, the implementation must cover and verify:

- backend behavior;
- durable persistence;
- deterministic state transitions and follow-up actions;
- concurrency and recovery behavior;
- failure/abstention paths;
- an observable result consistent with the user promise;
- tests that prove the promised behavior end to end where practical.

The agent must run the normal repository verification sequence before opening a PR and must not merge its own PR.

## Infrastructure boundary

The default agent run is repository-only. It must not deploy, mutate Azure or production resources, rotate secrets, or incur new paid infrastructure without an explicitly scoped issue and human approval.
