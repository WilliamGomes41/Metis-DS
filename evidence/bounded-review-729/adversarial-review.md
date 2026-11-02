# Final independent adversarial review: bounded ordinary/single-source slice

Read current concrete product files after earlier fixes on2026-11-01, not only design notes. Product edits remained with the owner. At the owner's explicit request this reviewer added only test_final_transition_requires_exact_json_not_python_numeric_equality[raw/window] to tests/test_revision_frontier_store_v1.py. Native preflight from this reviewer's execution context could not reach the shared socket and found no PostgreSQL16 binary; those two nodes were not executed/countedaspass here. A pure real-code probe confirmed the repaired strict-anchor self-hash refusal.

## Remaining blocker: actual former-head delta is not independently verified

seal_delta compares only the final actual head payload with the final proposed visible head and checks epoch==baseline+ownrowcount. That cannot detect a BEFORE trigger modifying or suppressing an own UPDATE to the former current head when this command also appends a successor.

Concrete counterexample:

1. Capture a valid prepared strict head.
2. Provide the valid ordered transitions: current governance update, then append a strict successor anchored to the unchanged canonical predecessor hash.
3. A BEFORE UPDATE trigger rewrites the old head's content, or returns NULL to suppress its intended governance update. The successor INSERT itself remains the exact proposed row.
4. Epoch delta still equals actual own rowcounts: a BEFORE rewrite adds no second DML, while a suppressed update reports0 and the implementation simply adds0.
5. Current last head matches proposed and physical identity checks pass for that final row. The unseen former head can now contain altered canonical content, old governance or wrong position; sealing derives prefix facts from proposed visible[:-1] instead of the actually stored rows.
6. A new certificate therefore asserts validity for a broken or semantically different historical prefix. Full current_revisions can reject a rewritten predecessor later.

Least needed fix: each intended delta UPDATE/INSERT must affect exactly one row and return the actual physical object_id, object_version, position and payload. Compare these O(delta) returned values against the intended row and original head position/chosen insert position before issuing the new certificate. Do not replace this with another full-prefix read or extra scalar counter. An AFTER trigger doing a separate object update is caught by epochs already; the missing proof concerns BEFORE rewriting the same DML or suppressing it.

Add native negative tests for former-head rewrite and suppressed update through a valid governance→append transition, checking complete rollback of rows/counters/frontiers. A pure planned-transition test cannot exercise this storage seam. No native reproduction was executed by this reviewer; the concrete code path and missing comparison are explicit.

## Earlier findings checked as repaired in current code

- Strict anchor now checks provenance.canonical_object_hash equals recomputed canonical hash before waiving unseen predecessor traversal. Real-code negative probe now raises revision_evidence_invalid; new native store test includes rollback comparison.
- seal_complete and explicit prepare select physical object_id/object_version and _check_physical rejects payload disagreement. Capture and final heads also check physical identity. Native negative fixtures now exercise both identity columns.
- Hidden-prefix publication/knowledge flags exclude boundary head and are combined in the original validator. Reseal ORs old hidden facts with final visible[:-1]. This preserves nonsticky current publication mirrors and current-head mutation semantics.
- Source adjacency capture selects original nearest non-document neighbors once, includes headings as sentinels, preserves stable (source_sequence,first_position) order, and follows graph closure separately. The new native source fixture compares changed-target admission to the original full-bundle oracle with an unlinked condition. Missing/unsupported ordering uses the explicitly named full compatibility path rather than silently omitting context.
- OID identifier seeding plus deferred no-action FK ensures index coverage without deleting authoritative history from a metadata operation. Existing raw writers create/invalidate entries with AFTER triggers; source unprepared check ignores tombstoned OIDs via indexed EXISTS.
- CHECK initially had SQL NULL acceptance for missing epoch. Current migration makes the full check IS TRUE, requires an object/non-null epoch, selector keys, numeric integer first_position and matching snapshot/OID, plus SQL JSONB hash. This closes the reported missing-epoch/null shape hole. Native malformed metadata tests were added; their actual execution results are the owner's evidence.
- Exact JSON comparisons now cover envelope field changes, commit_count0 and final transition equality. The latter formerly let Python-equal1→1.0 evade a validated transition list while the new raw-hash writer actually persisted a distinct value. Reviewer-added native test proves the real protected legacy case in raw/window variants; execution remains pending in the owner's working native environment.

## D1, privileges, optional schema and topology

FOR KEY SHARE authorization and Entra FOR NO KEY UPDATE preserve the explicitly approved next-command-after-retirement contract; they do not promise to cancel all in-flight commands on a role/retirement update. Native signin test pauses an actual protected Review and requires signin completion plus later retirement denial. Retain actual role-change/session tests too. No additional D1 domain decision is inferred from the lock matrix.

The032 migration grants only SELECT/INSERT/UPDATE on derived frontiers to existing explicit object writer roles holding those three privileges. DDL/grants are in the migration transaction. Deferred FK has no cascading delete from frontiers into objects. Optional027 remains optional, and a native production-migrations-only test exercises bounded mutation without it. When027 is present, supplied certified positions avoid re-counting complete histories.

The same store/working-revision owner issues and consumes frontiers. PostgreSQL still owns histories; source primitives and facts remain inputs rather than approval/closure/publication certificates. Named compatibility path remains available for existing unprepared state, but its latency is not covered by the bounded claim. No GET prepares it implicitly.

## Scope and acceptance limits

This is a first ordinary Review plus single source-context command slice. It does not prove bounded batch/group/other mutation paths, global lock removal, all closure/publication ingress or existing-data deployment acceptance. The owner's42 targeted passes substantiate their listed nodes, not the newly added nodes or pending final changes.

Derived frontiers are intentionally not included in the logical backup archive; authoritative object restore should reconstruct invalid/unprepared entries through triggers. Run the actual old/new archive restore→unprepared/check→explicit preparation→same source/reviews/publication evidence test before claiming restore parity. Existing canonical-commit/projection-failure seal and same-release retry tests remain necessary.

Earlier ordinary HTTP0.362s improved response latency but outer lock296.8ms exceeded250ms; latest heavy run was still pending when this review started. Source scaling74-106ms holds are separate evidence. Keep final ordinary/source costs and transaction/outer-hold/wait distinct, and preserve all#959 independent data/concurrency axes.

Conclusion at this snapshot: earlier anchor/adjacency/physical-identity/NULL/equality defects have concrete fixes, but the former-head BEFORE-trigger/suppressed-write seam remains a release blocker until independently checked and negatively tested. No merge/deploy approval is implied.

## Follow-up concrete fixes inspected

Owner implemented verify_written at each delta UPDATE/INSERT: RETURNING snapshot_id/object_id/object_version/position/payload, requiring rowcount1 and exact planned raw/physical values. Update position comes from the captured actual head frontier; insert position is chosen tail+offset. This addresses the former-head BEFORE rewrite/suppression issue without a full-prefix read. Reviewer added the explicitly authorized native tests test_before_trigger_cannot_change_or_skip_the_former_head_in_a_successor_delta[rewrite/suppress]; they prevalidate both actual semantic transitions and assert complete rollback. Syntax compilation passed, native execution is delegated to the owner's reachable test environment.

A further selector race was identified by the owner: a raw native0 edit of an unselected paragraph could commit a changed order while a command held only its existing document lock, because old invalidation did not take that lock. Current invalidate_revision_frontier first takes the same document row FOR UPDATE. This correctly serializes committed adjacency changes under the existing WorkingRevision boundary, without a new token or authorization decision. Supported runtime writers already acquire document first. Arbitrary raw SQL may acquire object row before document and encounter a PostgreSQL deadlock/rollback; no deadlock-free guarantee for arbitrary raw SQL is claimed. Existing native1 generation writes already acquire the document boundary.

Reviewer added the authorized native test test_native0_unselected_raw_writer_uses_existing_document_serialization: an actual document FOR UPDATE protects captured adjacency; an independent native0 unselected-object UPDATE receives55P03 from fixture-only200ms lock_timeout and rolls back unchanged rows/counters/certificates/view; after boundary release the same edit commits and invalidates frontier/adjacency, preserving unrelated physical rows and native0 document counters. Syntax compilation passed; native execution remains with owner.

At this later snapshot no unresolved code blocker from this review remains. This is conditional on the new negative tests and final affected suites passing against the exact tip. It is an assessment of the first bounded ordinary/single-source capability only. Existing-data preparation/restore, alternate ingress and final costs remain their separately named evidence requirements; this note grants no merge/deployment/publication approval.

## Final authorization-lock narrowing review

Inspected the concrete follow-up after the full6804-suite run exposed two processing revocation-fence regressions from globally replacing SHARE with KEY SHARE. Current code restores account_by_id(for_share=True) to FOR SHARE and adds a distinct for_key_share flag. Native _account/_require_role default key_share=False preserves every existing current=True caller's stronger behavior. Only execute_review_command opts current=True,key_share=True at protected reviewer authorization. Entra's FOR NO KEY UPDATE remains compatible with that bounded Review reader and conflicts with the restored processing SHARE fence.

This is a coherent scope correction: no global weakening of processing/source-preparation/publication authorization is needed to make the explicitly approved D1 Review/signin behavior work. Searches found no other key_share=True call site. Processing source_selection.authorize, publication evidence and other current=True callers retain the stronger default. Simultaneously requesting for_share and for_key_share selects SHARE, so the low-level adapter cannot silently downgrade the stronger explicit request. Ordinary non-current reads retain their original path.

The native mixin forwards the optional keyword through the updated OperationsConsole method; its base method forwards key_share to _account only when requested, preserving default compatible callers. No additional MRO override/signature bypass was found in the inspected source. Non-Postgres compatibility does not enter execute_review_command's native authority branch.

D1 scope remains next-command refusal after retirement, not cancellation of every authorized in-flight ordinary Review. Some other source/repair/second-review callers may still legitimately take the original SHARE lock; the first bounded ordinary/single-source slice must not claim universal signin independence across those unconverted paths.

No new blocking code finding from this narrowing. Approval remains conditional on the exact processing revocation, actual role-change/signin, retirement/session, migration and affected suite results; the running final-regression-repair log was not yet a complete result when inspected. No deployment/merge authorization is implied.


## Owner execution after the review

The reviewer-added native former-head BEFORE rewrite/suppression and exact numeric transition negatives passed in the35-node focused run. The additional native0 unselected serialization, actual archive/explicit preparation, source-context parity and MET-43 current-dependency tests passed:11 tests. Full-suite findings led to the explicit Review-only D1 narrowing above; the affected processing, Entra, retirement and migration suite passed84 tests. Final Review/source/current-dependency/storage/architecture tests passed35 tests. These results do not claim final-head full CI, ordinary250ms lock acceptance or production acceptance.
