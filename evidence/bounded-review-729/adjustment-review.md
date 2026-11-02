# Independent adversarial review of the PR965 adjustment

Read-only review of current uncommitted object_delta/full-writer, batch/group/reset and current-read integration on2026-11-02. No product/test/external edits. A pure existing-fixture probe was executed for automatic source-context group eligibility; no native DB executions by this reviewer.

## Findings reported and current fixes inspected

### Automatic span-based group eligibility (blocking in first reviewed snapshot; fixed structurally)

Original source_group_candidates→partition→source_accountability determines source usage by overlapping source_bound_context.entries[].span block/range. These targets need no object-ID relation and may be nonadjacent. The first scoped group adapter omitted such targets and could permit excluding an already linked source.

Pure existing-fixture reproduction: context_story(); select the linked_context source from partition(rows). Its OID is absent from source_group_candidates(rows), but present in source_group_candidates([linked_source]); its relations are empty and it has no manual confirmed_source_context. This proves the old proposed capture scope was incomplete, not merely theoretical.

Current capture_histories now gathers block IDs from actual source evidence in pending raw heads and adds existing review_neighbor_ids(snapshot,[],blocks) before adjacency/graph capture. Migration031 already indexes exactly the source_bound_context entry block dependencies. The original partition still filters actual ranges and eligibility, so the lookup is a safe candidate superset rather than a replacement rule. It includes shown but unchecked group members. Current span collection also tolerates malformed span rows, letting the original invalid-source predicate refuse rather than raising an accidental KeyError.

Required decisive test remains a native group command with a nonadjacent automatic span target and no OID edge: compare complete-bundle group eligibility and require source_group_members_changed/no mutation for the stale or manually submitted group. An adjacency-only fixture does not prove this patch.

### Reset fragment-failure condition (blocking in first reviewed snapshot; fixed in latest code)

execute_review_command deliberately captures source preparation errors into source_failure and may retain verified bytes even when fragments failed. A reset body does not itself consume fragments. The first _stage_source_batch checked bytes only, so it could commit after a fragment/extraction error, unlike the original _source_batch's unconditional _read_source_fragments call.

Current _stage_source_batch now refuses captured source_failure as well as missing source bytes/path before invoking the body. This preserves the old non-replayed availability condition. Completed receipt replay remains earlier, preserving original idempotency semantics. Require a native reset negative with verified bytes plus controlled fragment failure, asserting original error and unchanged object/binding/frontier/event/counter state.

## Shared physical delta proof assessment

The proposed owner shape is implemented directly, rather than a dirty-subset special case:

- capture reads actual physical identity/position/payload FOR UPDATE and records frontier epochs; it rejects physical/payload identity mismatch and missing positions.
- PhysicalObjectHistory is tied to its actual store/connection/snapshot. A lost plain-list baseline is independently recaptured and exact-JSON compared; wrong owner/connection is refused.
- write derives the actual diff from the captured physical rows. Every own DELETE/UPDATE/INSERT requires exactly one RETURNING row with planned snapshot/OID/version/position and raw payload. This covers BEFORE rewriting/suppressing a former head, inserts and deletes.
- seal compares the entire snapshot epoch mapping to captured epochs plus actual own rowcounts. Extra same-connection/AFTER writes to an unchanged OID or new OID cannot be silently certified. The final metadata identity/order list must equal the intended full replacement result.
- VerifiedObjectDelta now detaches following and affected counts; validated final current heads must match the frozen planned heads before certificate issuance. Complete prefix inputs are derived from that verified intended state without a second full payload/lineage read.
- Both concurrent and base-runtime full writers use the same boundary and original validator return. Ordinary bounded apply_review_changes retains its existing current/prefix guard. Metadata-only writes do not invalidate object frontiers and do not try to invent a new object proof.
- Unsupported frontier schema captures no epoch capability and seals no positive certificate, retaining the named legacy behavior. It still verifies every touched SQL row. Such mode is not claimed as bounded performance or prepared-frontier availability.

No additional blocking defect found in this shared store integration under supported normal callers. Operation-local classes are private trusted implementation inputs, not a new public authorization credential. Direct SQL/schema mutation is not made trustworthy merely by using their constructors. Native fault tests should include new-OID AFTER writes, deletion suppression and metadata-only behavior; the supplied tests already cover several actual native faults and wrong-connection capture.

## Batch/group/reset ownership and contracts

Exclusions retain explicit ID bounds and proposed metadata/structure plus original/literal checks. Groups retain all SHOWN IDs, current path/reason eligibility and members_hash, applying only selected IDs. No whole-section membership fence was added. The source-role writer remains unchanged. Reset scope comes from its durable original group receipt; the receipt is reread under lock, and old_version payloads are point-read through the indexed physical identity. These old rows are inputs to register restoration, never editable prefix rows.

The native adapter uses existing execute_review_command plus apply_review_changes/seal_delta. No global reload/event scan/full-history writer is required on the prepared path. Current actor, roster, policy, canonical sealing, exact relevant bindings and audit remain under existing owners. Original-source preparation/opening occurs before the outer lock and is keyed to actual current raw objects. Full group delta and final ledger flush stay atomic.

Legacy m2 replay-before-equality remains distinct from generation stale-before-replay. Source APIs still require a nonempty expected_revision; ordinary Review's None is not silently introduced as a source contract. The supplied actual legacy m2 HTTP1.062s/outer1.005s is an improvement but not250ms outer acceptance; source UI's generation token path must be measured separately after actual current-only read wiring.

Decisive negative nodes still needed beyond source happy paths: stale unchecked shown member; member failure after earlier member preparation; final audit fault; original-group receipt mismatch/missing old version on reset; current participant/retirement change; canonical committed/projection-pending refusal. Existing domain suites can supply these if they exercise the new native adapter rather than a compatibility or file path.

## Current-only read completeness and retry boundary

review_document_window requires an already bound snapshot and selects active OIDs from the covered frontier index. The validated deferred FK prevents an authoritative object key from disappearing from that index. capture checks every selected current head/certificate and preserves first-occurrence order. Missing/corrupt preparation returns None and takes the existing full read adapter; no GET seals data.

read_review_document(current_only=True) captures document envelope/generation, all current heads and bindings in one repeatable-read read-only transaction. The original current_revisions anchor validator runs after SQL closes. It returns an explicit generation token, not a head-only value masquerading as public whole-objectset m2, and avoids populating the full-history objects cache with that abbreviated input. Current-object/binding/envelope caches remain operation-owned. The production factory constructs the concurrent store implementing these new read APIs.

_read_current_objects uses the pure current adapter; within existing workflow transactions current_document_objects deliberately retains the original full path and does not change enclosing isolation. This preserves processing authorization/activation/retry fences. Source progress omits full m2 hashing only for UI states that render no start command. The UI branch order agrees with that predicate: running/waiting/completed/unchecked states do not render a start form; an actual start/resume form still receives objects_revision, and reserve_selection still checks its original complete m2 under the reprocessing transaction and default SHARE authorization. No processing retry-precondition weakening found.

## Bounded assessment

At this inspection point the two new concrete adapter regressions have structural fixes and no further blocker was found. Native negative tests for those fixes and exact-tip affected/full suites remain necessary evidence. This is not system-wide bounded-performance certification: legacy m2, complete required operations, formation/diagnostics routes and unprepared compatibility must retain individually reported costs. No merge/deploy/publication authorization is implied.

## Root verification after review

The native regressions now cover the distant automatic span target at the
actual native capture/group-oracle seam, reset source-fragment failure,
unexpected AFTER-trigger new identities, metadata-only and absent032 schema,
late deferred audit failure and an unchecked shown member changed under a fresh
generation. See test_source_batch_bounded_commands.py and
test_full_writer_delta_proof.py. The first capture/partition test is not claimed
as a complete nonadjacent group HTTP reproduction. Production acceptance and
whole-project closure remain separate.
