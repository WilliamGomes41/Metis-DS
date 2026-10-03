Change class: A
Rewrite risk: high
Assigned issue: #496
Promise: Preserve a complete literal recommendation core and separately bound necessary context, detect open recommendation ranges and retain both provider calls in the existing working revision. Admission does not confirm knowledge or publish it.
Proof: Versioned producer/transform/admission/review/export tests; bounded omission supplement; exact replay; local console ingest, restart and atomic failed replacement; adversarial stale/forged evidence checks. Live provider and PostgreSQL acceptance remain open.
Touches lifecycle invariants: yes, proposal admission and successor working revision; publication/serving authority remains unchanged.

## Domain, authority and transition

The existing source binary and extracted raw fragment hashes own source truth. The existing WorkingRevision/object-set commit owns candidates and their metadata. The existing review ledger owns human decisions; the publication registry alone owns serving eligibility. No new store, background worker, publication writer or duplicate authority is introduced.

Begin state: a verified immutable source with unpublished working state, or new ingest. Trigger: existing authorized ingest/re-extraction with METIS_PASSAGE_FORMATION_MODE=semantic-source-bound-v3. Existing account roles, named reviewers, source verification, processing reservation and stale-revision/CAS checks remain mandatory.

End state: the existing atomic object-set/envelope commit stores literal selected candidates, core/actor/target/scope evidence, separately bound context, source-range disposition and primary/supplementary call evidence. Candidates remain needs_review. Open possible recommendations retain the existing remainder and not_yet_assessed passage-register path. No serving effect occurs.

Invalid evidence, conflicting/overlapping supplementary selection or malformed provider output fails before applying the bundle. An unavailable supplementary call leaves the validated primary selection plus explicit open work. A failed primary/re-extraction retains the old working set; the existing processing-attempt record records failure. Restart reads stored metadata and validates exact replay identity. Recovery reuses existing authorized retry/re-extraction; it does not mutate published snapshots or reuse old review confirmations.

Historical v1/v2 objects are not reinterpreted as v3. Published work is immutable. Existing successor-version, supersession, withdrawal, four-eyes and registry rules are unchanged. No schema migration or historical backfill runs.

## Writer and reader map

- pre_review_semantic_v1 produces the closed v3 schema, literal references, same-provider bounded supplementary selection, combined validated replay and origin call evidence.
- semantic_passage_v1 checks source membership, contiguity and hidden gaps, binds context and then fields.
- semantic_transform_generic_v1 reconstructs source selections and rebinds fields and context before object formation.
- admission_gate_v1 dispatches by stored field version, rebinds field evidence from actual source, checks normative core and realized necessary context. Source scope cues are recomputed from source; stored coverage metadata cannot remove those checks.
- operations_console_v1 retains the sole existing durable commit, authorization, revision/concurrency and correction boundaries.
- source_bound_fields_v2 dispatches the successor reader without changing historical v2 semantics. Review HTML displays the successor fields. processing_evidence_export_v1 includes primary/supplementary origin calls and a separate additive recommendation_coverage dataset.
- passage_formation_policy_v1 and attempt_diagnostics_v1 recognize the mode and pin validator identity for replay/diagnosis.

## Contract and limits

source-bound-fields-v3 separates actor_span, target_group_span and scope_span; null/not_stated is permitted when the performer is implicit. Core action, goal and recommendation_evidence_span remain required. Core fields must be within the selected normative passage; designated actor/target/scope fields may reference allowed, bound context roles. Negations and clinical qualifiers cannot be hidden by a shorter core. Number/strength metadata may be outside the core only under exact checks. Terminal punctuation and an explicit grammatical subject are not independent vetoes for recognized literal imperatives. Predicate/type evidence, source fidelity, unresolved abbreviations/references and required context remain enforced.

recommendation-coverage-v1 detects potential numbered/imperative recommendations in named recommendation sections. It records selected, used_as_context or open, with detection_completeness=not_proven. It is accountability evidence, not a clinical gold standard. A descriptive body breaks scope-label adjacency. Each possible source-scope cue still requires source-bound realization. The detector cannot prove that every recommendation or scope relationship has been found.

At most one supplementary call occurs, sharing the original total time budget. It receives exact open-range hints and candidate blocks; evidence blocks remain available for source-bound external context. Identical proposals deduplicate; conflicting overlap fails. Both calls are retained without HTTP authorization headers. Supplementary failure evidence is checkpointed before rejection; budget exhaustion is explicitly recorded. Exact replay validates the combined proposal without new calls.

## Runtime, compatibility and cutover

Local and PostgreSQL adapters receive the same existing object/envelope payload; neither adapter changes. Local durable restart/failure behavior is tested. A real PostgreSQL black-box acceptance run is NOT TESTED here; existing PostgreSQL tests require an external test database.

The default remains semantic-source-bound-v2. v3 is a staged successor contract, not a deployed or complete remediation claim. Cutover requires a new actual-provider run on the controlled source, independent per-recommendation reference/context review, recovery/restart and PostgreSQL acceptance. The full private source and provider export are not committed. The recorded private request/proposal proves the detector identifies all five known omissions; it does not prove that a new model recovers them.

Rollback for new processing: select v2 using this v3-capable release. Retain v3 readers and historical evidence. Downgrading to a binary that cannot read v3 objects is unsupported without compatibility proof. No destructive migration or irreversible operation occurs. Remove the old writer only in a separately accepted cutover after historical reader compatibility and recovery are proven.

## Separate adversarial review

Checked: recomputed binding hash cannot legitimize out-of-bounds evidence; stale context invalidates fields; deleting coverage metadata cannot hide source-scope cues; scope alone cannot substitute for announced list items; shortened core cannot drop source qualifiers; invalid supplementary evidence cannot partially replace the bundle; exact replay pins prompt/schema/contract and avoids new calls; an incomplete replacement retains objects and revision after restart. Legacy v2 processing and direct legacy writers keep their own versioned contract and cannot be presented as v3.

Remaining gates: live provider acceptance, independent complete source/context review, PostgreSQL black-box persistence/concurrency and production cutover. These gates block a claim that the user's document is durably solved. They do not justify automatic migration, publication, deployment or merging this PR.
