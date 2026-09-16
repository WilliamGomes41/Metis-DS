# Repair 217 — published WorkingRevision immutability

Change class: A

Promise: once canonical publication authority contains a durable release for a SourceSnapshot, the corresponding WorkingRevision is historical and cannot be mutated in place.

Lifecycle transition: mutable WorkingRevision -> durably published, immutable WorkingRevision.

Authority boundary:
- canonical PostgreSQL `publication_releases` plus `release_published` audit lineage decides whether a snapshot has been durably published;
- the workflow envelope is a rebuildable publication projection and is not a second publication authority;
- PostgreSQL workflow object/reviewer state remains mutable only before durable publication.

Allowed after durable publication:
- exact reconciliation of `state`, `published`, `release_id`, `release_version`, `published_at`, and `published_by` from canonical authority.

Forbidden after durable publication:
- object/content changes;
- review or repair changes;
- reviewer/workflow metadata changes;
- startup migration reopening a published WorkingRevision;
- arbitrary envelope changes disguised as publication reconciliation.

Failure result: mutation fails closed with `published_working_revision_immutable`; object revision and payload stay unchanged.

Restart/recovery result: canonical publication authority seals the WorkingRevision even if a crash occurred after canonical commit but before workflow-envelope reconciliation. Startup legacy-review migration skips the snapshot. Exact publication metadata can then be reconciled without mutating working content.

Black-box proof:
- `tests/test_published_working_revision_immutable_v1.py::test_canonical_release_seals_review_before_workflow_envelope_reconciliation`
- `tests/test_published_working_revision_immutable_v1.py::test_postgres_authority_blocks_object_write_in_canonical_commit_crash_window`

Non-goals: successor v2 creation, document-level serving switch, supersession, withdrawal, and document-status UI redesign.
