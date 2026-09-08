# V&VN Data Services Protocol v2.33 — Passage disposition and proportionate human review

**Status:** Approved for project use  
**Protocol delta version:** 2.33.0  
**Approval date:** 2026-09-08  
**Approved by:** Project owner  
**Extends:** Protocol v2.32.0  
**Highest change class:** C3 canonical/review (passage disposition, review completeness and reviewer workload; does NOT reopen C5 publication/security, high-risk four-eyes, G2 or `publish()`)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.33 corrects one review-model ambiguity before further review functionality is built. Metis MUST preserve complete knowledge coverage without returning researchers to thousands of separate review actions.

The governing rule is:

> Every substantive source passage MUST receive an explicit disposition, and every knowledge object MUST receive human review before use. Human review per object does NOT mean one separate reviewer interaction per object.

This is a bounded supersession of Protocol v2.19 and Protocol v2.30 only where they can be read to make review-queue priority equivalent to knowledge eligibility, or to make an admission failure equivalent to substantive exclusion. All other v2.19 and v2.30 requirements remain law.

The four layers remain frozen source -> source passage -> knowledge object -> human review -> published projection. A knowledge object MUST NOT replace the source document. Capture is not publication. G2 remains BLOCKED and `publish()` remains G2-BLOCKED.

This protocol change is protocol-only. It MUST NOT implement product code, Azure, G2 activation, a new knowledge store, a new database architecture, a new serving type, or Protocol v2.14.

## 2. What remains unchanged

The following existing foundations remain mandatory:

- exact frozen source bytes, SHA-256 and source locators (v2.11);
- one confirmable semantic unit per knowledge object and closed relations (v2.13);
- human confirmation of the serving object type before publication (v2.12/v2.13);
- review bound to the exact object version/hash;
- high-risk four-eyes and the existing second-review mechanism (v2.13);
- fail-closed canonical import, publication and retrieval;
- published projection as a derived read-only layer;
- answerability and abstention when suitable approved evidence is absent;
- v2.19's prohibition on requiring researchers to open thousands of equal Inhoud cards one by one;
- v2.30's hard admission gate as a quality gate for candidate knowledge objects.

This delta MUST NOT add persistent `light`, `standard` or `strict` review levels. It MUST NOT add a duplicate `use_scope` truth alongside existing object type, risk and serving rules. It MUST reuse the existing first review plus `requires_second_review` / second review mechanism.

## 3. Every substantive passage gets an explicit disposition

The passage register is the coverage control for source passages.

Every substantive passage MUST eventually have exactly one applicable disposition from the existing closed set:

- `selected_as_candidate` — the passage carries a candidate knowledge object;
- `used_as_context` — the passage is required to understand another knowledge object;
- `linked_as_support` — the passage supports another knowledge object;
- `excluded_with_reason` — the passage is not a knowledge unit and the reason is explicit and auditable.

`not_yet_assessed` MAY exist while work is incomplete, but MUST NOT be treated as a completed terminal disposition for a substantive passage.

Metis MUST NOT silently drop substantive source content merely because it is not in the priority review queue.

Deterministic exclusion MAY be used for demonstrably non-substantive material such as site chrome/navigation, duplicate visible prose already represented from the same freeze, isolated page/list numbers, empty material, or other categories already prohibited by the extraction rules, provided the exclusion rule is explicit and regression-tested.

A substantive passage MUST NOT become `excluded_with_reason` solely because an automatic candidate parser, classifier, context scan or type contract failed.

## 4. Admission failure is not substantive exclusion

Protocol v2.30 admission remains a hard gate for whether a machine-created candidate is good enough to enter the ordinary knowledge-object review flow.

The following distinction is now normative:

`admission blocked != excluded_with_reason`

A blocked candidate means: the machine has not established a sufficiently complete, source-faithful candidate knowledge object.

It does NOT mean: the underlying source passage contains no relevant knowledge.

Therefore:

1. a substantive passage whose candidate is `gate_result=blocked` MUST remain `not_yet_assessed`, `used_as_context`, `linked_as_support`, or otherwise available for explicit disposition;
2. it MUST NOT automatically become `excluded_with_reason` merely from the admission result;
3. the admission reason codes MUST remain available as diagnostic evidence;
4. the passage MAY later be corrected, merged, reclassified, linked as context/support, or explicitly excluded with reason;
5. a blocked candidate MUST still NOT be published or served as a knowledge object.

This SUPERSEDES only the v2.30/Phase-4 reading that maps every admission-blocked substantive passage directly to `excluded_with_reason`. It does NOT weaken the hard admission gate for entry into ordinary object review.

## 5. All knowledge objects receive human review without 2,000 separate clicks

Every knowledge object that can become part of the usable knowledge layer MUST receive at least one human review on the exact object version/hash before approval.

Review completeness and reviewer interaction are different concepts:

- **review completeness** is object-level and auditable;
- **reviewer interaction** MAY be batch-level where one coherent human judgment validly covers multiple normal-risk objects.

Metis MUST NOT require one separate click/open/save cycle for every normal-risk knowledge object merely to preserve object-level auditability.

For coherent normal-risk content, including definitions, explanations and other non-action-bearing factual/background knowledge, the console MAY offer batch review by paragraph, section or another source-coherent group. A batch action MUST write an individual review result for every included object and MUST bind each result to that object's exact reviewed hash/version.

The reviewer MUST be able to remove an object from a batch, inspect it individually, correct it, reject it, defer it, or escalate it.

Batch membership MUST NOT cross an unresolved ambiguity, conflict, source mismatch, admission defect that changes the meaning of the object, or high-risk boundary.

A batch MUST NOT convert one review decision into an untraceable envelope-level approval. Existing object-level review binding remains the authority.

## 6. Risk determines additional control, not whether review happens

All knowledge objects require a first human review.

Existing high-risk logic determines whether an independent second review is also required. Protocol v2.13 four-eyes remains unchanged, including exceptions and existing high-risk fields such as dosage, thresholds, contraindications and escalation decisions.

Therefore:

- normal-risk knowledge object -> one required human review;
- object for which existing `requires_second_review` is true -> first review plus independent second review.

Recommendations, conditions, exceptions, actionable outcomes, high-risk objects, ambiguous objects and conflict cases SHOULD be prioritized and individually reviewed when the existing risk/semantic rules require it.

This delta MUST NOT create a researcher-facing `zwaar/licht`, `snel/langzaam`, `light/standard/strict` or equivalent safety switch.

## 7. Protocol v2.19 becomes queue-priority law, not knowledge-eligibility law

Protocol v2.19 remains correct that researchers MUST NOT be required to open 2,000 or 4,000 equal Inhoud cards one by one. That remains a hard UX/assurance constraint.

The v2.19 concept currently represented as `slow_review_duty` MAY continue as a priority/presentation mechanism during migration, but MUST NOT be interpreted as the normative boundary of which substantive knowledge is ultimately assessed.

Accordingly:

- priority individual work remains recommendation + condition + exception + high-risk and other escalated cases;
- definitions, explanations and other normal-risk substantive knowledge MUST have a regular review route;
- remaining substantive `unclassified` MUST NOT be a dead-end category;
- queue priority MUST NOT determine serving eligibility;
- `fast` / `slow` MAY describe UI/work routing only and MUST NOT become content-safety classes.

This is a bounded supersession of v2.19. It preserves the no-2,000-click rule and removes only the reading that non-duty substantive content may remain without a route to disposition/review indefinitely.

## 8. Publication and serving remain fail-closed

This delta does not loosen publication or retrieval.

A knowledge object MUST NOT become publishable/servable unless all existing applicable requirements are satisfied, including at least:

1. source identity, integrity and locator are valid;
2. object type is human-confirmed where required;
3. the exact object version/hash has an approved first human review;
4. any required independent second review is approved;
5. no blocking uncertainty/conflict remains;
6. the reviewed object is the same object version/hash proposed for publication;
7. existing publication/G2 requirements are satisfied.

Unreviewed, admission-blocked, rejected, conflicted or merely batch-presented content MUST NOT be served.

G2 remains BLOCKED. `publish()` remains G2-BLOCKED. This delta MUST NOT be cited as G2 PASS, GD-03 completion, publication authorization or clinical approval of any knowledge set.

## 9. Acceptance and regression requirements

A later implementation under a separate Metis GO MUST prove at least the following before merge:

1. a substantive definition or explanation always has a route to disposition and human review;
2. a substantive admission failure does not automatically become `excluded_with_reason`;
3. technical/non-substantive junk can still be explicitly and deterministically excluded with auditable reason;
4. `not_yet_assessed` substantive passages remain visible in coverage as open work;
5. unreviewed knowledge cannot be imported as approved, published or served;
6. existing high-risk/four-eyes behavior still requires an independent second reviewer;
7. one batch reviewer action can cover multiple eligible normal-risk objects while producing separate object-level, hash-bound review records;
8. an ineligible/high-risk/ambiguous object cannot be silently swept into a normal-risk batch;
9. a source with approximately 2,000 substantive passages does not imply approximately 2,000 separate reviewer interactions;
10. every substantive source passage can eventually be accounted for by an explicit terminal disposition;
11. existing source-integrity, object-hash, audit, publication, withdrawal, retrieval and abstention invariants do not regress.

The implementation MUST include an explicit reviewer-burden regression. Counting object-level review records is NOT sufficient evidence that the UI requires one human interaction per object; the test MUST distinguish backend audit records from human interaction count.

## 10. Next code after this protocol

This protocol delta itself MUST NOT implement code.

After a separate Metis GO, the smallest implementation wave is:

1. remove the automatic `gate_result=blocked` -> `excluded_with_reason` mapping for substantive passages;
2. preserve admission reason codes while returning such passages to an open disposition route;
3. make the passage register the complete coverage/disposition control;
4. reduce `slow_review_duty` semantics to priority/presentation only;
5. add a regular batch-review route for eligible coherent normal-risk content;
6. reuse existing exact-hash first review and existing second-review/four-eyes mechanisms;
7. add the section 9 regression tests before implementation changes.

Implementation SHOULD prefer DELETE -> REUSE -> CONFIGURE -> EXTEND. It MUST NOT create a new review service, new knowledge store, new database architecture or duplicate governance state merely to implement this delta.

## 11. Out of scope

Out of scope for this delta and its protocol-only PR:

- changing source bytes, locators or SHA-256 rules;
- changing the closed serving object types;
- weakening the v2.30 candidate admission contracts;
- weakening v2.13 four-eyes or second-review independence;
- adding `light` / `standard` / `strict` persistence;
- adding `use_scope` persistence;
- adding a new service, database or knowledge store;
- changing published-object immutability or release semantics;
- G2 activation or `publish()` PASS;
- Protocol v2.14;
- nurse-facing UI, Athena or Quire implementation;
- Azure deployment;
- rewriting historical protocol delta files except explicit index/conflict pointers if later required.

## 12. Change class and review

This is a protocol version change, not a C0 documentation edit. The highest change class is **C3 Canonical/review** because it changes review logic, passage disposition and the human-review route. Under the established governance matrix, C3 requires clinical + technical review for a later conformance decision.

This delta is owner-approved as protocol direction. It does NOT itself satisfy GD-03, publish a knowledge set, or substitute Metis/Implementation engineer/Auditor for required named reviewers.

Where this delta conflicts with the bounded v2.19 review-duty interpretation or the v2.30 admission-blocked-to-excluded mapping described above, v2.33 governs. For all other requirements, the stricter existing fail-closed rule remains in force.
