# W1 source-resolution implementation review

Target: `c914bd8f1b9227082e31913d1b3deca436e61fa5` against
`c4db3bd84bfe722ab235eff67d2ccf69b60a785b`, #729 / MET-36.
This is a separate adversarial pass by the implementer, not an independent human
approval. Quality method: Code Quality Review, QUALITY mode. Release readiness
still requires the repository checks, review and separate deployment decision.

Contract: one source-units repair leaves a new open revision, with discrepancy
bound to the reviewed version and repair audit bound to its successor. Source,
retained meaning, authority and exact whole-set precondition remain unchanged.
The complete workflow write either commits or rolls back. Canonical publication
and serving authority cannot be changed by this operation.

| Challenge | Enforcement and evidence |
|---|---|
| Alternate ingress / MRO bypass | Public ReviewClosure dispatch encloses its repair-spec evidence and deterministic repair. Direct researcher correction and other repair kinds retain the existing kernel. Nested owned commands use serial execution; raw unowned transactions retain their original refusal. |
| Current identity / rights / roster / policy | Existing capture and locked current-role/KEY SHARE checks plus full input comparison. Native races for role, display identity, roster and policy refuse without overwriting the winning state. |
| Source and selection identity | Existing immutable-source reader and materialisation remain owners. Source change race refuses. Same, different-block and multi-block selection results equal the original serial kernel on the exact same baseline after native rollback. |
| Caller-owned mutable parameters | Review found that the selection list could change after dependency discovery. The adapter now detaches submitted arguments before discovery. A native test mutates the caller's list during preparation and proves the captured selection and stored result remain aligned. |
| Whole-set m2, retained versions, native0 | Public token is checked in repeatable-read capture. Existing all-identity mutation epochs only avoid a redundant full read when unchanged. Any difference or unsupported witness invokes full comparison again. Unrelated-object, missing-witness and retained-version mutation races refuse. No GEN substitution. |
| Guard effectiveness | Removing the full public-precondition check makes stale replay succeed and fails `test_complete_evidence_is_atomic_and_version_bound[repair_evidence]`. The first concurrent-winner mutant remained refused by other guards; it was not accepted as proof of this specific guard. Both experimental mutations were restored. |
| Durable participants / final failure | Object successor, invalidated bindings, facts/frontiers and all evidence use the existing prepared native transaction. Faults at final repair evidence and deferred COMMIT roll back all recorded participants; retries commit once, then the old token is stale. Existing A09 native final-commit/restart/concurrency tests passed. |
| Partial preparation / compatibility | NULL frontier certificates select the original full serial path; no empty or truncated prepared set. Successful legacy result survives fresh-runtime reconstruction. No migration, GET backfill, dual writer or new authority. |
| Supported topologies / restart | Real HTTP succeeds under both production PostgreSQL console compositions. A09 includes fresh-process reconstruction; the larger performance fixture independently checks unchanged source/canonical state and restart persistence. Local engine is PG17.11, not the CI PG16 service. |
| Shared executor and rollback observer | Existing prepared review/batch suite passed. An old rollback test injected at an obsolete source commit entrance; injection now follows the real prepared native writer and still requires the original failure and unchanged durable state. |

No remaining demonstrated functional defect was found in this bounded pass.
The new documentation link initially used the old explanation's pinned revision,
which did not contain the W1 contract (`git cat-file -e` failed). Its reference
revision now pins the inspected W1 commit, where that file exists.
The private staged workspace remains request-local; `without_workflow_io` and
the original document/review owners enforce preparation/commit separation.
The only new reader uses the existing frontier table; schema and public API do
not change. Reverting the binary leaves ordinary committed rows readable.

Exclusions: production/Azure latency, deliberate DBA disabling of integrity
triggers, deployment, wider W2–W6 work and certification of every existing-data
cutover. Performance and full-suite results belong to the accompanying evidence
record, not to this static review verdict.

UI handoff: the existing document-storage explanation and composition diagram
were updated. Impeccable context and detector ran (no detector findings).
The existing Chromium check was targeted locally at the document-storage model;
desktop 1440px, mobile 390px, light/dark and no-JavaScript checks passed. The
local probe waits for fragment navigation before asserting it; its initial
immediate URL assertion raced navigation. No browser harness change was retained.
