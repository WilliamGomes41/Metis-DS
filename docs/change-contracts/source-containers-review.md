# Source containers — implementation and adversarial review, issue #518

This review distinguishes implemented behavior from clinical completeness. No production state, release, or source bytes were changed by this implementation run.

## Proven transition and ownership

Given an immutable source with metadata, an applicable context passage and two recommendations, an authorized ingest prepares one atomic revision. A faulty second proposal remains source work. Restart preserves the first proposal. Authorized recovery selects only unfinished source. After exact knowledge review, publication serves two knowledge objects, including their bound context; source records return 404 through the Product API. Restart preserves the release. Reviewed/published work rejects recovery.

`test_recoverable_formation_v1::test_recover_review_publish_restart_and_published_projection` exercises that chain through the durable publication console and real Product API router. The same file tests failed activation, stale revision, concurrent/duplicate commands and reviewed-work guards. `test_source_containers_v1` tests exact context boundaries, metadata reversal, both local and native PostgreSQL restart, separate kernel/UI/export access, and stale context at serving.

One authority remains: the existing revision object bundle plus exact review evidence. Ingest, reextract and resume all call `semantic_spec_from_fragments`; local `_commit_prepared_store` and the PostgreSQL workflow override still commit the bundle/envelope/evidence. No second source store, workflow state, approval writer or serving registry was introduced. UI, exports and readiness derive the containers. The source discriminator continues to exclude source records from knowledge admission/review/retrieval.

## Adversarial pass

- **Context-only reselection:** task validation restricts candidate block ids; exact range restriction runs before the joint merge. A producer cannot replace an earlier validated selection using context input. Independent valid selections survive a bad one.
- **Partial use:** source gaps split at exact context boundaries. A context covering the first sentence cannot close the second. Target rejection or changed literal identity reopens the usage. No context proposal approves its target.
- **Automatic classification:** only complete version/date, dotted navigation and complete edition-footer patterns qualify. Section location, a model metadata label, ordinary clinical text and table captions cannot independently grant closure. Existing reviewer reset records permanently override these automatic rules.
- **Missing table content:** preserving a caption is insufficient; the existing unresolved-reference gate remains. Bounded tasks carry the complete referenced section or remain explicitly blocked when it exceeds the task limit.
- **Reconstruction reuse:** the recorded Smetten validation took 7.377 seconds for one joint proposal check before caching. Bounded tasks otherwise repeat that work. The cache is operation-scoped, keyed by the complete input, bounded to eight views and returns deep copies. Mutation-isolation and changed-source tests prove no stale reuse; it never persists or survives a restart.
- **Shared deadline:** each request uses at most 120 seconds and no more than the remaining task-run budget. Every unstarted task gets explicit source ranges and pending failure evidence. Partial success remains recoverable; a wholly failed new model run cannot replace existing validated work with remainders.
- **Alternate readers:** the end-to-end API test exposed that `build_projection` copied manually confirmed context but omitted source-bound context. The projection now includes context from the exact published anchor and rejects stale/malformed/unresolved bindings. Neither source records nor unpublished anchors become serveable.
- **Legacy and cutover:** source-accountability-v1 remains readable with its prior human-disposition semantics. New V3 work carries source-accountability-v2 and bounded-formation-v1 in replay identity. Resume requires that contract and matching identity. No startup conversion, backfill, or SQL migration. Reprocessing is explicit; reviewed/published work retains existing immutability guards.
- **Rollback:** stop new preparation or select the existing legacy formation mode while retaining the compatible readers and context-serving fix. Do not roll a new context-bearing release back to the older reader that omitted its context. Historical canonical releases remain unchanged; source policies do not migrate on startup.
- **Topology:** native PostgreSQL tests use the existing CI Postgres service; local tests use the existing compatibility store. No permanent environment was built. Native checks must pass before merge.

## Smetten evidence and limits

`source-containers-smetten-proof.json` records offline reconstruction of the supplied snapshot `snap-97f71a51fc4911ff-6fca1f91`. Reproduce with the diagnostic JSON extracted from its processing evidence ZIP:

```
PYTHONPATH=. python scripts/verify_source_container_diagnostic.py diagnostic.json --bounded --output proof.json
```

The 14 recorded proposals are preserved (13 recommendations, one definition). Admission changes from 12 allowed / two blocked to 13 allowed / one blocked. The remaining block is missing table content. All seven context entries receive separate usage; 639 source records remain preserved, split into 117 document-information records, seven linked-context records and 515 unknown-use records. The detector still reports eight open signals alongside 13 selected signals. These are not independently established clinical recall numbers.

Task planning over the recorded input yields 69 bounded tasks; maximum candidate text is 10,383 characters and maximum separate context is 8,779 characters, with no oversized task. Routing the recorded provider outputs through the new orchestration completes 134 fixture calls (initial and targeted recovery), retains all 14 proposals, and reports no unfinished formation. This proves deterministic planning and source preservation, not model output quality or end-to-end production latency. No new live model run over Smetten was performed. The clinical reference remains unvalidated; do not claim that the remaining source contains no missing knowledge.

The full local suite also exercises browser-related contracts where the runtime supports them. Native PostgreSQL/browser/Docling acceptance is provided by the repository CI. Four environment-specific tests fail identically on unchanged main: the PID-namespace child-process inspection test and three proxy-sensitive SSRF loopback tests. No security or transport production code was changed to hide those failures.

## Local verification

Repository preflight, architecture-boundary check, compileall and six architecture-invariant tests pass. The full suite before reconstruction caching reported 2,725 passed, 189 skipped and the four baseline environment failures described above. The final full-suite rerun with reconstruction caching reports 2,726 passed, 189 skipped and the same four baseline environment failures. Subsequent focused recovery tests pass (15 passed, one native test skipped). Native CI results are recorded on the PR. Focused container/recovery/source-mapping tests pass (49 passed, two native PostgreSQL tests skipped locally).
