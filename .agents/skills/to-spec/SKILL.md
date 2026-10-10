---
name: to-spec
description: Turn a settled engineering conversation into an executable Metis GitHub issue by synthesizing decisions already made, grounding them in the current repository, classifying the change, and recording proof and readiness. Do not restart discovery or ask the user to repeat settled context.
---

# To Spec

Turn an already-developed engineering discussion into a durable Metis specification. This skill is a synthesis step, not a second interview.

## Non-negotiable behavior

- Do not ask the user to restate or re-decide information already present in the conversation.
- Treat the conversation as the source of intent and the repository as the source of current behavior.
- Inspect the repository only as needed to verify the existing mechanism, authority, domain language, constraints, and test seams.
- Do not invent lifecycle, persistence, authority, migration, recovery, or product decisions that remain unresolved.
- If a material decision required by Metis governance is unresolved, publish the specification with `needs-info` instead of `ready-for-agent`.
- Do not broaden the requested change into adjacent cleanup.
- A specification may describe implementation decisions, but it must not silently redefine existing domain law.

## Read before drafting

Read the following repository guidance:

1. `AGENTS.md`
2. `docs/agents/issue-tracker.md`
3. `docs/agents/triage-labels.md`
4. `docs/agents/domain.md`
5. `docs/agents/continuous-development.md`
6. `docs/agents/abstraction-boundaries.md`

Also read the relevant `CONTEXT.md` / `CONTEXT-MAP.md` and ADRs when they exist. Follow `docs/agents/domain.md` when those files are absent.

For Class A work, also read `docs/agents/lifecycle-vsa.md` and apply it in full.

## Process

### 1. Synthesize the settled context

Extract only what is already supported by the conversation and repository evidence:

- the concrete problem;
- one user/system promise;
- the desired externally observable behavior;
- decisions already made;
- constraints and non-negotiables;
- rejected alternatives when they explain an important boundary;
- explicit out-of-scope items;
- unresolved questions that materially block execution.

Do not turn preferences into invariants. Do not turn a possible implementation into an agreed decision.

### 2. Classify the change

Apply `docs/agents/continuous-development.md` before describing implementation.

Record:

- `Change class: A | B | C`
- `Promise: ...`
- `Proof: ...`
- `Touches lifecycle invariants: yes | no`
- `Rewrite risk: none | high`

If rewrite risk is `high`, include every mitigation field required by the continuous-development contract.

If the work is Class B and changes shared extraction, review, retrieval, semantic, persistence, or cross-layer behavior, establish the existing mechanism, authority, affected functions/types/call path, permitted state changes, preserved behavior, and smallest observable proof before proposing the change.

If Class B creates or mutates durable domain state, include the Stateful Class B domain-first overlay before implementation decisions.

If Class A, include the lifecycle contract required by `docs/agents/lifecycle-vsa.md`. Do not downgrade Class A work to make the issue easier to execute.

### 3. Establish the current mechanism and authority

Use the repository to distinguish established behavior from proposed behavior.

Prefer existing domain owners and operations from `docs/agents/abstraction-boundaries.md`. Do not propose a parallel status writer, gate, source of truth, lifecycle, or persistence authority when an existing owner already governs the behavior.

When the current mechanism or ownership boundary cannot be established, record that as a blocker. Do not guess.

### 4. Choose the proof seam

Choose the highest existing seam that can prove the promise from observable behavior.

- Prefer one strong behavioral or integration proof over many implementation-detail tests.
- Reuse an existing seam before proposing a new one.
- For Class A, include the required black-box lifecycle proof and restart/recovery evidence.
- For stateful Class B, prove the transaction, recovery, duplicate-execution, and concurrency behavior where applicable.
- If a new seam is genuinely required, state why the existing seams cannot prove the promise.

### 5. Draft the specification

Use this structure:

<spec-template>

## Change Contract

Change class: A | B | C  
Promise: <one sentence>  
Proof: <smallest observable acceptance evidence>  
Touches lifecycle invariants: yes | no  
Rewrite risk: none | high

## Problem Statement

Describe the problem from the user or system perspective. State the current failure or limitation without smuggling in the solution.

## Solution

Describe the intended externally observable result. Keep this at product/domain level before implementation mechanics.

## User / System Stories

Provide a numbered set of distinct scenarios sufficient to cover the promised behavior. Include relevant failure, retry, recovery, authorization, or concurrency scenarios when they are part of the promise. Do not inflate the list with duplicates.

## Existing Mechanism and Authority

State what currently owns the behavior, how the relevant call path works, and which existing domain contracts must remain authoritative.

For Class B changes covered by the program-design gate, include:

- existing mechanism and authority;
- affected functions, types, and call path;
- state that may change;
- state that must remain unchanged;
- behavior that must remain unchanged;
- smallest observable proof.

## Domain / Lifecycle Decisions

Include only the subsection that applies.

### Stateful Class B

Domain entity/aggregate:  
Invariant(s):  
Durable state before:  
Durable state after:  
Transaction boundary:  
Failure/recovery result:  
Duplicate execution / idempotency result:  
Concurrency result: <or N/A with reason>  
Audit/evidence requirement:

### Class A

Include the mandatory lifecycle, authority, transition, recovery, and proof fields required by `docs/agents/lifecycle-vsa.md`.

### Rewrite risk: high

Include every mitigation field required by `docs/agents/continuous-development.md`.

## Implementation Decisions

List decisions that are already settled or directly implied by the repository contract, including relevant modules, domain operations, interfaces/contracts, schema/API implications, and cross-layer interactions.

Do not include speculative file paths. Do not include code snippets unless an existing prototype captures a decision more precisely than prose; if so, keep only the decision-rich fragment and identify it as prototype evidence.

## Testing Decisions

State:

- the acceptance proof;
- the chosen test seam;
- relevant prior-art tests in the repository;
- failure/recovery cases that must be demonstrated;
- any required architecture-boundary or lifecycle checks.

Tests must prove externally meaningful behavior rather than implementation details.

## Out of Scope

List adjacent work that this specification intentionally does not include.

## Open Decisions / Further Notes

List only material unresolved decisions, evidence gaps, or constraints that a future implementer must know.

</spec-template>

### 6. Apply the readiness gate

Apply `ready-for-agent` only when all of the following are true:

- the required change classification is complete;
- the promise and observable proof are concrete;
- required Class A, stateful Class B, or high-rewrite-risk fields are complete;
- no material domain, lifecycle, authority, migration, recovery, or destructive-operation decision remains unresolved;
- the issue does not contradict an ADR or governing Metis contract without explicitly resolving that conflict;
- an implementer can begin without inventing product or domain decisions.

Otherwise apply `needs-info` and state the exact blocker(s) in `Open Decisions / Further Notes`.

Never use `ready-for-agent` merely because the issue is long.

### 7. Publish to the project issue tracker

Follow `docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md`. Create one GitHub issue for the specification and apply exactly the readiness label determined above.

Creating the issue does not start implementation.

Return the issue number, title, URL, change class, rewrite risk, and readiness label.
