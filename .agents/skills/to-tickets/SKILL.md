---
name: to-tickets
description: Break an approved Metis specification, plan, or settled engineering conversation into a dependency-aware set of executable GitHub issues. Use when work spans multiple implementation units and each ticket must preserve Metis change classification, lifecycle/rewrite-risk governance, blocking edges, and observable proof.
---

# To Tickets

Turn an approved plan into a small dependency graph of implementation tickets that Metis engineers can execute without inventing missing product or domain decisions.

This skill decomposes decided work. It does not reopen settled design, dilute lifecycle rules, or turn one coherent promise into layer-by-layer busywork.

## Non-negotiable behavior

- Work from the existing specification, plan, or settled conversation.
- If the user provides an issue number or URL, read the full issue body and comments before decomposing it.
- Treat the parent specification as the source of intent and the repository as the source of current behavior.
- Do not invent missing lifecycle, authority, persistence, migration, recovery, destructive-operation, or product decisions.
- Every implementation ticket must satisfy the required Metis issue header in `docs/agents/continuous-development.md`.
- A ticket may be `ready-for-agent` only when it can be implemented without making a new domain/product decision.
- Do not close, rewrite, or repurpose the parent specification.
- Do not broaden the work into adjacent cleanup.

## Read before drafting

Read:

1. `AGENTS.md`
2. `docs/agents/issue-tracker.md`
3. `docs/agents/triage-labels.md`
4. `docs/agents/domain.md`
5. `docs/agents/continuous-development.md`
6. `docs/agents/abstraction-boundaries.md`

Also read the relevant `CONTEXT.md` / `CONTEXT-MAP.md` and ADRs when they exist.

For any Class A ticket, also read and apply `docs/agents/lifecycle-vsa.md` in full.

## Process

### 1. Gather the approved source

Accept one of:

- a Metis spec issue;
- another approved plan;
- the settled current conversation.

If a source issue exists, capture its number and URL for use as the parent reference.

Extract:

- the parent promise;
- accepted solution;
- implementation decisions;
- testing decisions;
- Class A/B/C classification;
- lifecycle impact;
- rewrite risk;
- stateful Class B requirements;
- explicit out-of-scope items;
- unresolved decisions.

If an unresolved decision would force an implementer to choose domain semantics, authority, lifecycle behavior, migration, recovery, or destructive behavior, do not hide it inside a ticket.

### 2. Verify the current code path where needed

Explore only enough repository code to make the split truthful.

Confirm:

- existing mechanism and authority;
- relevant domain operations and abstraction owners;
- real integration seams;
- current tests or acceptance seams;
- whether a proposed prerequisite is actually required.

Do not create a ticket for speculative prefactoring. Prefactoring gets its own ticket only when it is necessary to keep later work safe, small, or green.

### 3. Choose the decomposition strategy

Prefer narrow vertical slices that produce independently observable behavior.

A good ticket:

- has one concrete promise;
- has one smallest observable proof;
- fits in one fresh implementation context;
- changes all layers necessary for that promise;
- leaves `main` releasable;
- names only genuine blockers.

Do not split by technical layer such as "database", "API", "UI", then "tests" when none is useful or verifiable alone.

Metis explicitly allows staged delivery when one end-to-end promise cannot safely land in a single PR. In that case, use the smallest safe sequence, for example:

```text
safe domain/storage prerequisite
-> behavior/API integration
-> UI/observable result
-> end-to-end acceptance proof
```

The parent promise is not complete until the end-to-end proof passes.

### 4. Handle wide or high-risk change explicitly

For a wide mechanical refactor that cannot land green as a vertical slice, use expand -> migrate -> contract:

1. expand beside the existing form;
2. migrate callers in independently safe batches;
3. contract only after all callers have moved.

For `Rewrite risk: high`, preserve the staged migration, compatibility, rollback/recovery, cutover, cleanup, blast-radius, and adversarial-proof requirements from `docs/agents/continuous-development.md`. Do not split them away into tickets that individually pretend the risk no longer exists.

For Class A work, decomposition must preserve the lifecycle transition as the governing unit. A schema helper, page, flag, or migration is not by itself proof of lifecycle correctness. Required restart/recovery and black-box lifecycle proof must remain represented in the graph.

### 5. Classify every ticket independently

Every implementation ticket must begin with:

```text
Change class: A | B | C
Promise: <one sentence>
Proof: <smallest observable acceptance evidence>
Touches lifecycle invariants: yes | no
Rewrite risk: none | high
```

Use the lightest correct class for that ticket, but never downgrade a ticket whose behavior actually changes a Class A truth.

Then include any conditional governance required by the ticket:

- Class B shared-behavior program-design gate;
- Stateful Class B domain-first overlay;
- full Class A lifecycle fields;
- full `Rewrite risk: high` mitigation fields.

If those fields cannot be completed from the approved source and repository evidence, the ticket is not executable. Mark it `needs-info` or keep it out of the executable graph until the blocker is resolved.

### 6. Build the dependency graph

For each proposed ticket record:

- **Title**
- **Change class**
- **Promise**
- **Proof**
- **Blocked by**
- **What it delivers**
- **Readiness**: `ready-for-agent` or `needs-info`

Blocking edges must represent real execution gates, not preferred ordering.

A ticket with no genuine blocker belongs to the current frontier and may start immediately.

Prefer parallel tickets when they truly do not share a state/authority migration or other sequencing constraint.

### 7. Review the breakdown with the user

Before publishing, show the proposed graph as a numbered list.

For each ticket show:

- Title
- Change class
- Blocked by
- What it delivers
- Proof
- Readiness

Ask only about the decomposition itself:

- Is the granularity right?
- Are the blockers genuine?
- Should any tickets merge or split?

Do not restart the original product/design interview.

Publish only after the user approves the breakdown.

### 8. Publish GitHub issues in dependency order

Follow `docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md`.

Create blocker tickets before tickets that depend on them, so real GitHub issue identifiers exist for dependency links.

If there is a parent spec issue:

- reference it in each child ticket;
- when supported by the repository workflow, attach implementation issues as sub-issues without rewriting the parent body.

Use GitHub native blocking dependencies where supported. Fall back to an explicit `Blocked by: #...` line only when native dependencies are unavailable.

Apply the readiness label determined for each ticket. Do not label a ticket `ready-for-agent` merely because the decomposition was approved.

Do not close the parent specification.

## Ticket template

```markdown
Change class: A | B | C
Promise: <one sentence>
Proof: <smallest observable acceptance evidence>
Touches lifecycle invariants: yes | no
Rewrite risk: none | high

## Parent

#<parent issue> — <parent title>

## What to build

Describe the complete behavior this ticket delivers. Keep it at user/system and domain-contract level.

## Existing mechanism and authority

State the current owner/call path only when needed by the Metis program-design gate or to prevent a parallel authority.

## Required domain / lifecycle contract

Include the applicable Class B stateful, Class A, or high-rewrite-risk fields. Omit this section when none apply.

## Acceptance criteria

- [ ] Observable criterion 1
- [ ] Observable criterion 2
- [ ] Required failure/recovery or regression proof, when applicable

## Blocked by

None (can start immediately)

—or—

- #<issue> — <reason this issue genuinely gates the ticket>

## Out of scope

List only ticket-local exclusions needed to prevent scope creep.
```

Avoid specific file paths or code snippets unless an approved prototype fragment is itself the clearest durable statement of a decision.

## Completion

Return:

- parent issue or source;
- created ticket numbers and titles;
- dependency/frontier summary;
- readiness label per ticket;
- which tickets can start immediately;
- any blocked `needs-info` tickets and their exact unresolved decision.
