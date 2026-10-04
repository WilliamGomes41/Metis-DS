Change class: A
Promise: New v3 proposals bind unambiguous adjacent strength labels and explicit condition context without relaxing source integrity.
Proof: The two supplied failed provider responses are replayed privately; synthetic producer/transform/admission regressions, negative ambiguity/context tests, existing durable restart/failure story.
Touches lifecycle invariants: yes
Rewrite risk: none

Assigned by owner: “implementeer” in this conversation. Narrow first implementation slice of #496. No Azure deployment, automatic publication, historical re-admission, partial object-set activation or additional model retry mechanism.

Existing path: pre_review_semantic_v1._provider_proposal -> source_evidence_resolution_v1 -> semantic_passage_v1 -> source_bound_fields_v3 -> semantic_transform_generic_v1 -> admission_gate_v1 -> existing atomic working bundle commit. Immutable source owns evidence; workflow storage owns objects; registry owns serving.

Two proven failures: repeated identical strength stamp with null occurrence; a literal heading supplied as condition context and condition_span rejected by v3 although scope_span accepts the same context.

Required behavior: only v3 may resolve a repeated directional strength stamp from the uniquely resolved normative-core field inside one selected candidate span when the stamp is immediately after that core with whitespace only. Do not use first-match, nearest-match, fuzzy matching or unrelated block context. Explicit occurrences retain existing behavior; unmatched/ambiguous references reject. Externally bound condition_span requires an exact validated context entry with condition role. Core/action evidence cannot borrow external context. Bind/rebind and review evidence remain mandatory. Pin changed validation policy in replay identity; do not reinterpret existing saved proposals under an old identity.

Lifecycle entity: existing unpublished WorkingRevision.
Lifecycle transition: existing authorized ingest/retry activates a fully validated bundle, or retains prior working state on rejection.
Initial durable state: immutable source, new or failed/unpublished working state.
Trigger: existing ingest/retry/re-extract command.
Authorization: existing roles/source/published guards.
Validation: exact block/literal/offset, allowed context role, same source, existing admission and revision CAS.
Mutable entities: newly prepared objects/evidence and existing attempt record.
Immutable entities: source bytes, previous versions/reviews and published releases.
Workflow state before: processing/blocked or unpublished in_review.
Workflow state after: in_review only on existing successful atomic commit; failed attempt otherwise.
Release state before: unchanged.
Release state after: unchanged.
Serving state before: unchanged, registry authoritative.
Serving state after: unchanged, registry authoritative.
Expected API result: existing receipt or exact rejection.
Expected UI result: existing source-bound review projection; no new UI state.
Failure result: no partial bundle or lost prior objects.
Restart result: stored evidence rebinds under the compatible reader.
Recovery result: existing retry, budget and concurrency semantics.
Legacy-data result: no backfill or published mutation; old v1/v2 dispatch unchanged.
Required black-box scenario: producer -> context/strength binding -> transform -> admission -> durable store -> restart -> exact same objects; failed replacement retains prior revision.
Explicit non-goals: partial candidate activation, production cutover, clinical approval, changing publication/serving or storage authorities.

Acceptance: both original failures reproduced before changes, then report all downstream errors exposed (never claim full source solved merely because the first errors disappear). Private clinical files stay outside GitHub. Preserve four combinations of explicit strength/direction; wrong/missing context remains blocked.


## Additional observed timing-list defect

The complete offline transform/admission proof exposed an existing false rejection: an explicitly bound bullet list with role timing did not count as the announced evaluation list. Accept a bound timing entry only when it has actual bullet-list content; a bare time, list marker or scope heading does not satisfy the list requirement. Prompt/schema and replay identity cover the new condition binding. Existing table-reference resolution is not relaxed.

## Verification limits

The first private recorded proposal passes the repaired strength reference, then correctly rejects a later nonliteral field. The second private proposal passes source validation; offline formation uses that frozen response and an explicit supplementary abstention (no paid model calls). A real new-provider run, full clinical reference review, and production PostgreSQL acceptance remain required. Partial candidate storage and bounded correction calls remain a separate, unimplemented slice; this repair preserves atomic fail-closed bundle activation.

## Separate adversarial review

Tested: all four directional strength labels, second rather than first occurrence, intervening prose, repeated candidate core, cross-block references, wrong evidence field, label-prefix ambiguity, invented literals, missing/wrong-role context, external context incorrectly used as action, bare timing versus a list. Existing tests cover stale context, forged offsets with recomputed hash, exact replay, restart and atomic failed replacement. No new writer/store/authority or backfill; existing v1/v2 ambiguity behavior is preserved. The changed replay identity prevents reuse of old proposals as new-policy inference.

## Results

- Final focused verification: 91 passed.
- Broad suite: 2666 passed, 180 skipped, 5 failed. All five failures reproduce on the unchanged local snapshot of main: subprocess worker detection, three proxy-sensitive SSRF tests, and subprocess dependency discovery. They are not presented as passing checks.
- Repository preflight, architecture dependency check, compileall and release-control diff check pass.
- Frozen second provider response: 13 recommendations reach admission, 12 allowed and one unresolved table reference. The timing bullet list is preserved and accepted. This is not full-document recall or clinical acceptance.
- Frozen first provider response: original repeated-label failure is repaired; a later nonliteral condition-target reference still correctly rejects the bundle.
- Repository publication was explicitly approved by the owner after review of the local patch and verification results. No source PDF, raw provider response or private export is included in the patch.

## PR review corrections

The adjacency anchor is the bound recommendation_evidence_span, contained in the selected candidate, including when that candidate contains its strength stamp. Missing or external core evidence cannot disambiguate a label. Timing-list recognition also accepts the preserved middle-dot marker. Both policy identities are advanced for exact replay. Producer-to-admission regressions cover candidates with and without the stamp; negative cases cover missing and external cores.

The PR contract uses the exact required field names and values, including separate before/after release and serving states. Local contract validation passes. Review-focused regressions: 67 passed. The original GitHub Python 3.13 suite passed 2842 tests with 14 skips. Final-head CI remains the merge gate.
