# Metis continuous development operating model

This is the default operating model for repository work. Its purpose is to keep Metis safe where correctness is structural, while keeping ordinary product development small, fast, and inexpensive.

The rule is: **apply the lightest process that safely proves the user promise.** Do not apply lifecycle-grade governance to a change that does not alter lifecycle semantics.

## 1. Classify the change before implementation

Every implementation issue MUST be classified as exactly one of these classes.

### Class A — Lifecycle core

Use Class A when the change can alter any of these truths:

- logical document or version lineage;
- source snapshot identity or immutability;
- review closure required for publication;
- publication readiness semantics;
- creation of a canonical publication release;
- serving authority or active serving set;
- supersession;
- withdrawal;
- migration/reconciliation of published state;
- restart/recovery of lifecycle state;
- durable authority boundaries for the above.

Class A MUST follow `docs/agents/lifecycle-vsa.md` in full.

The five permanent lifecycle invariants are:

1. published work is immutable;
2. a live v1 may coexist with a working v2;
3. publishing v2 atomically replaces v1 in serving;
4. one LogicalDocument has at most one active serving release;
5. withdrawn content is not served, including after restart/recovery.

If a proposed change can violate one of these invariants, it is Class A regardless of file location or UI/backend label.

### Class B — Normal product behavior

Use Class B for user-visible or operational product behavior that does not change Class A lifecycle semantics.

Examples include ordinary console interactions, navigation, presentation, search/retrieval behavior, non-lifecycle workflow conveniences, exports, and bounded API behavior outside publication authority.

Rules:

- one issue MUST state one concrete user/system promise;
- implement the smallest coherent change that proves that promise;
- use vertical slicing where the promise crosses layers, but do not create lifecycle paperwork when lifecycle semantics are unchanged;
- technical work MAY be split across multiple small PRs when that reduces risk; the feature is not considered complete until the user promise is proven end to end;
- tests MUST cover the behavior changed, not unrelated architecture;
- do not introduce a new durable authority, lifecycle state, architecture layer, or framework to solve a local product problem;
- if implementation reveals that a Class A truth must change, STOP and reclassify before continuing.

### Class C — Cosmetic, copy, documentation, and non-semantic maintenance

Use Class C only when runtime/domain behavior does not change.

Examples include copy edits, documentation, comments, formatting, non-semantic styling, and repository housekeeping.

Rules:

- keep the diff minimal;
- verify the changed artifact and existing mandatory repository checks;
- do not add product architecture, new runtime state, or broad test suites to justify a cosmetic change;
- a documentation change that changes agent governance, release rules, lifecycle semantics, or development policy is NOT ordinary Class C; it requires a focused contract test for the rule being changed.

## 2. Rewrite-risk overlay

Every implementation issue MUST also state exactly one rewrite-risk value:

```text
Rewrite risk: none | high
```

Rewrite risk is semantic, not a line-count threshold. A change is `high` when it materially replaces, redefines, or cuts over any of the following:

- a durable authority or source of truth;
- persisted identity, lineage, or schema semantics that require migration/backfill;
- a shared mutation, read, authorization, or reconciliation boundary used by multiple entry points or runtime topologies;
- a lifecycle, publication, serving, retrieval, or review kernel whose old and new behavior must coexist during transition;
- a migration/cutover path that can change restart, recovery, rollback, or data-integrity behavior.

A large refactor that preserves all durable semantics and boundaries may still be `none`. A small patch that changes one of the items above is `high`.

### Required mitigation for `Rewrite risk: high`

Before implementation, the issue MUST define:

```text
Rewrite target:
Why local patching is insufficient:
Current authority/writer/reader map:
Supported runtime topologies:
Persisted-state impact:
Compatibility/migration plan:
Rollback/recovery plan:
Cutover trigger:
Cleanup/decommission criteria:
Failure blast radius:
Adversarial proof matrix:
```

The map MUST identify the one intended authority, every writer that can mutate the affected truth, every reader that can influence behavior, supported storage/runtime topologies, persisted state, and restart/recovery paths.

High-risk implementation rules:

- Prefer expand -> migrate -> contract, additive replacement, or a strangler-style cutover over a big-bang rewrite.
- A big-bang replacement is forbidden by default. It requires an explicit written reason that staged coexistence is technically unsafe or impossible and explicit human approval before implementation continues.
- Temporary dual-read or dual-write behavior MAY exist only when one authority remains explicitly named, reconciliation is deterministic, divergence is detectable, and removal/expiry criteria are written before the dual path is introduced.
- A compatibility mirror, cache, envelope, projection, or fallback MUST NOT silently become a second authority.
- Destructive or irreversible migration MUST NOT be executed autonomously. It requires explicit human approval and a tested backup/recovery path before execution.
- Where possible, behavior cutover and destructive contract/removal SHOULD be separate steps so rollback remains available until the new path is proven.
- If high rewrite risk is discovered after implementation started, STOP. Do not keep patching the branch; update/rescope the issue and complete the required mitigation fields first.

Before merge, high-risk work MUST receive a separate adversarial review pass that tries to break the promised invariant rather than only confirm the implementation. That review MUST explicitly challenge:

- alternate mutation/read entry points;
- inheritance, override, and fallback paths;
- all supported runtime/storage topologies;
- stale local state versus durable authority;
- duplicate or ambiguous authorities;
- partial migration/cutover states;
- concurrency where relevant;
- restart, recovery, rollback, and failed cutover behavior.

A green CI run proves the written tests passed; it is not by itself proof that the rewrite surface was complete.

## 3. VSA means user-promise completeness, not PR size

A vertical slice is the end-to-end proof of a user/system promise. It is not a requirement that every technical step be delivered in one large PR.

Allowed:

```text
PR 1: smallest safe domain/storage prerequisite
PR 2: behavior/API integration
PR 3: UI/observable result
=> promise complete only when the end-to-end acceptance proof passes
```

Not allowed:

```text
PR 1 passes locally
=> declare the product promise complete while required layers remain unimplemented
```

For Class A, the lifecycle transition itself is the slice and `lifecycle-vsa.md` defines completion.

For Class B, the issue's user/system promise defines completion.

## 4. Cost-control rules

These rules apply to all classes.

- MUST NOT create a new architecture rule unless it prevents a named failure mode or protects an explicit invariant.
- MUST NOT create a new durable source of truth when the value can be derived reliably from an existing authority.
- MUST NOT add a new abstraction layer merely to make one implementation look cleaner. Prefer the existing boundary unless it cannot safely express the required behavior.
- MUST NOT add a new gate without stating the failure it blocks and the evidence that proves the gate works.
- MUST NOT broaden an issue to clean adjacent code unless that code blocks the promised behavior.
- SHOULD prefer deletion, consolidation, and reuse over parallel mechanisms.
- SHOULD prefer one strong behavioral/integration test over several tests that only restate implementation details.
- MUST distinguish a regression in an existing contract from discovery that the contract itself is wrong. The latter requires a model/ADR decision before further patching.

## 5. Stop-loss rule

Stop implementation and return to design when any of these occurs:

- the same invariant requires a second independent source of truth;
- a fix requires mutating published history;
- a local feature requires redefining document/version identity;
- two consecutive fixes move the same lifecycle inconsistency to a different layer instead of eliminating it;
- the acceptance scenario cannot be stated without implementation-specific language;
- the proposed solution adds more lifecycle states or authorities because the existing states are ambiguous;
- an implementation classified `Rewrite risk: none` starts replacing or redefining an existing authority, persisted schema/identity semantics, or shared cross-topology boundary.

At that point, do not add another patch slice. Define or repair the domain boundary first. If rewrite risk is now high, rescope under the rewrite-risk overlay before additional code changes.

## 6. Required issue header

Every implementation issue MUST begin with:

```text
Change class: A | B | C
Promise: <one sentence>
Proof: <the smallest observable acceptance evidence>
Touches lifecycle invariants: yes | no
Rewrite risk: none | high
```

For `Rewrite risk: high`, append every mandatory mitigation field from section 2 before implementation.

For Class A, append the full mandatory lifecycle fields from `docs/agents/lifecycle-vsa.md`.

For Class B, no additional lifecycle template is required unless the work is reclassified.

For Class C, `Proof` may be a focused artifact/contract check plus existing repository checks.

## 7. Definition of continuous development

Metis is continuously developable when:

- ordinary Class B/C changes remain small and can move independently;
- Class A changes are rare and rigorously proven against the lifecycle invariants;
- high-risk rewrites are rare, staged, reversible where possible, and adversarially reviewed before merge;
- main remains releasable after every merge;
- existing authorities are reused rather than multiplied;
- recovery/restart behavior is tested where durable state changes;
- governance grows only in response to a concrete invariant or failure mode;
- the cost of proving a change is proportional to the risk of the change.

The target is not maximum process. The target is the minimum evidence needed to keep the promised behavior trustworthy.
