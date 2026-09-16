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

## 2. VSA means user-promise completeness, not PR size

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

## 3. Cost-control rules

These rules apply to all classes.

- MUST NOT create a new architecture rule unless it prevents a named failure mode or protects an explicit invariant.
- MUST NOT create a new durable source of truth when the value can be derived reliably from an existing authority.
- MUST NOT add a new abstraction layer merely to make one implementation look cleaner. Prefer the existing boundary unless it cannot safely express the required behavior.
- MUST NOT add a new gate without stating the failure it blocks and the evidence that proves the gate works.
- MUST NOT broaden an issue to clean adjacent code unless that code blocks the promised behavior.
- SHOULD prefer deletion, consolidation, and reuse over parallel mechanisms.
- SHOULD prefer one strong behavioral/integration test over several tests that only restate implementation details.
- MUST distinguish a regression in an existing contract from discovery that the contract itself is wrong. The latter requires a model/ADR decision before further patching.

## 4. Stop-loss rule

Stop implementation and return to design when any of these occurs:

- the same invariant requires a second independent source of truth;
- a fix requires mutating published history;
- a local feature requires redefining document/version identity;
- two consecutive fixes move the same lifecycle inconsistency to a different layer instead of eliminating it;
- the acceptance scenario cannot be stated without implementation-specific language;
- the proposed solution adds more lifecycle states or authorities because the existing states are ambiguous.

At that point, do not add another patch slice. Define or repair the domain boundary first.

## 5. Required issue header

Every implementation issue MUST begin with:

```text
Change class: A | B | C
Promise: <one sentence>
Proof: <the smallest observable acceptance evidence>
Touches lifecycle invariants: yes | no
```

For Class A, append the full mandatory lifecycle fields from `docs/agents/lifecycle-vsa.md`.

For Class B, no additional lifecycle template is required unless the work is reclassified.

For Class C, `Proof` may be a focused artifact/contract check plus existing repository checks.

## 6. Definition of continuous development

Metis is continuously developable when:

- ordinary Class B/C changes remain small and can move independently;
- Class A changes are rare and rigorously proven against the lifecycle invariants;
- main remains releasable after every merge;
- existing authorities are reused rather than multiplied;
- recovery/restart behavior is tested where durable state changes;
- governance grows only in response to a concrete invariant or failure mode;
- the cost of proving a change is proportional to the risk of the change.

The target is not maximum process. The target is the minimum evidence needed to keep the promised behavior trustworthy.
