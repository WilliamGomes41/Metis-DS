# T8 materialisation and Admission integrity

Change class: A
Rewrite risk: high
Touches lifecycle invariants: yes

## Promise and authority
A selection is processing evidence until deterministic materialisation succeeds against the retained authoritative extraction. knowledge_materialisation_v1 alone resolves ordered source spans and builds identity, text and provenance. semantic_transform_generic_v1 validates candidate integrity before canonical transformation. apply_admission_gate uses that same integrity check before creating Admission evidence. Selection origin, eligibility, object type and syntactic spans are routing inputs, never source authority. Explicit beslisboom construction remains separate.

## Writers, readers and topologies
Semantic selection writes decisions; the materialiser writes complete candidates; the transformer writes canonical projections; Admission writes domain decisions only for source-valid candidates. Existing OperationsConsole ingest/reprocess commands and workflow transaction own durable bundle mutation. recoverable_formation_v1 isolates precisely located invalid selections and preserves independent valid selections. Existing review/publication readers remain consumers of verified-source authority. File and PostgreSQL stores and Azure adapters share these kernels; no store, schema, transaction or infrastructure change.

## Lifecycle transition
Initial state: immutable source and retained extraction, selection/processing evidence, and possibly an existing working revision.
Trigger: ingest, reprocessing, recovery or Admission projection.
Authorization: existing command roles and source/snapshot guards.
Validation: actual block resolution, strict integer bounds and ordered non-overlapping spans; reconstructed text, nonempty resolvable fragment references and raw mapping; exact candidate text/mapping/references; current source checksum/version at Admission.
Success: completely materialised candidate can receive allowed or blocked domain Admission. A blocked valid candidate stays available for repair and cannot enter content review.
Failure: original materialisation reason/finding is processing evidence; no new candidate, Admission decision, content review or publication authority. Independently valid candidates survive the existing recovery isolation path.
Mutable entity: current WorkingRevision through its existing atomic bundle transaction. Immutable entities: source bytes, historical candidates/bindings and published releases.
Release/serving state before and after: unchanged; no deployment or publication.
API failure: controlled domain processing error retaining the original reason, rather than an unhandled ValueError or fabricated blocked Admission.
Restart: existing durable revisions and exact bindings remain unchanged; failed preparation does not replace the previous bundle.

## Compatibility, migration and rollback
Pre-T7 ordered-span identity and complete-row duplicate selection remain intact. No backfill, historical hash or binding rewrite. Legacy/forged rows that cannot demonstrate source integrity receive no new Admission authority. Optional forensic source_span_id is not required. Published history remains immutable. Rollback reverts these unmerged commits; recovery uses existing snapshot/source transactions and stable identity. Cutover requires human review and complete green GitHub verification; no merge/deploy in this task.

## Proof matrix
Unknown block, invalid/bool/out-of-bounds/overlapping/reversed spans, text mismatch/empty text, missing/contradictory mapping, extra/missing/UNKNOWN provenance references, forged persisted candidate and wrong source revision/checksum: no Admission decision. Valid source-bound candidate failing domain rules: blocked remains a candidate. Error finding locates a candidate for existing independent recovery. Ingest failure leaves durable bundle/review evidence unchanged; restart and exact binding compatibility retained. Existing T5-T7, full matrix, Chromium and packaged real-PDF checks remain mandatory.

## Scope
T8 only after the repaired T7 boundary at cd6a5c352e7b2802a926cc934c7ecea76fdfbed6. No T9-T12, alternative creator/resolver/gate/store, live data migration, Azure edits, merge or deployment.

## Existing literal continuation repair
The existing correction transaction may retain an object's identity while creating a new revision. Its expanded source selection is validated/materialised before review mutation, and rematerialised within correction preparation. The revision consumes the materialiser's spans and mapping, retains its existing identity/history, and receives fresh Admission only if the complete revised canonical source binding matches. Arbitrary edits acquire no Admission from stale source metadata. Existing continuation fixtures now use actual split source spans/mapping and authoritative fragments; the repaired revision must receive allowed Admission. No new correction transaction or field-formation policy.
