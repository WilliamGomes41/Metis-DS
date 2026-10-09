# A02 durable source representations
Change class: A
Promise: accepted source blocks and exact mappings survive restart and all bound query routes read them without extraction, reconstruction or model calls.
Proof: native PostgreSQL and local compatibility, installed HTTP routes, forbidden reconstructors/providers after acceptance, restart, immutable bindings, concurrency and explicit legacy migration.
Touches lifecycle invariants: yes
Rewrite risk: high

## Domain and lifecycle
Lifecycle entity: SourceSnapshot-associated SourceRepresentation and existing processing attempt; WorkingRevision is a consumer, not a source producer during queries.
Lifecycle transition: verified prepared extraction -> validated immutable representation plus immutable snapshot binding; existing processing attempts reserve/run/fail/expire independently. Acceptance does not complete selection/review/publication.
Initial durable state: received snapshot without binding, or legacy snapshot with accepted extraction but no representation.
Trigger: explicit authorized processing command or explicit migration command. GET never triggers production.
Authorization: current existing researcher/named-reviewer selection authorization; migration requires researcher and named/uploader access. Validate again at acceptance. No new human/publication decision.
Validation: immutable source checksum, full extractor identity, reconstruction/block/schema versions, fragment content hash, document/source identity (fragment IDs depend on these), explicit correction revision, exact mappings, active lease where applicable, current revision and processing configuration.
Mutable entities: existing processing attempts and additive representation records during acceptance; existing candidates only under their normal guarded activation.
Immutable entities: source bytes; accepted representations and snapshot bindings; historical objects/reviews/releases.
Workflow state before: processing/in_review/blocked/ready/closed as current authority derives.
Workflow state after: representation acceptance alone leaves workflow semantics unchanged; candidate activation remains existing owner; missing representation is a technical unavailable/migration-required condition, never hidden GET processing.
Release state before/after: unchanged; no release writes.
Serving state before/after: unchanged; publication registry remains sole authority.
Expected API result: existing readers consume exact bound stored fragment/block payload; absent legacy binding returns explicit source_representation_migration_required; corrupt evidence returns source_representation_invalid.
Expected UI result: existing pages retain equivalent output when binding exists; missing binding gives actionable migration-required projection, no spinner/model work.
Failure result: no false successful acceptance; failed candidate processing cannot erase accepted source data; no automatic reconstruction.
Restart result: exact accepted ID, mapping and bindings remain available with zero reconstruction/model/extraction.
Recovery result: existing attempt fencing; explicit retry/migration may repeat unfinished work. One accepted result, not exactly one calculation. Complete immutable payload with failed document registration can be retained as unattached result; it conveys no successful receipt or publication.
Legacy-data result: explicit dry-run/apply migration. Prefer complete stored extraction; native historical extraction may require an explicit unpublished command. Published migration is allowed only from complete accepted historical extraction with equivalence proof; never re-extract or rewrite published work. Otherwise explicit successor is required.
Required black-box scenario: receive -> explicitly select -> accept -> reads with reconstructors/provider forbidden -> new kernel/cache removal -> same reads -> object review change/role revocation visible -> failed correction leaves historic binding unchanged. Native two-process/CAS and migration of published accepted extraction preserve release and serving.
Explicit non-goals: changing source-selection criteria, relaxing review, production 502 claims, paid calls, Azure changes, merge/deploy.
Rewrite risk: high

## Representation identity and invariants
Key: source_sha256 + document_id/source_id + complete extractor versions/config/fragment hash + reconstruction version + semantic block contract + schema version + explicit correction_revision. document/source identity is necessary because block and fragment IDs depend on it.
One accepted immutable payload per key; equal key/different payload is integrity conflict. Both heading-inclusive and candidate-only views retain their exact existing block IDs, positions, raw mappings and join separators.
No cached decisions/authorization/readiness. Bindings select exact version; never latest-run selection. A correction uses a new revision/key and successor working snapshot under existing lifecycle, never replaces a bound record. Object correction/rejection does not create new source representation.
Source bytes remain immutable; prepared representations contain full fragments and both block views. Hashes establish integrity, acceptance validates mappings and reference identity against those fragments.
Queries cannot produce, persist, migrate, re-extract or invoke model work. Missing/corrupt payload never falls back.

## Rewrite mitigation
Rewrite target: shared _read_source_fragments/_read_source_blocks boundary and source catalog, with immutable durable representation acceptance.
Why local patching is insufficient: ContextVar scopes are disposable; every request and restart repeats block construction. Request decorators cannot express a durable version/binding contract.
Current authority/writer/reader map: OperationsConsole.ingest/reextract_unpublished/_fragments_and_spec/record_processing and existing activation; pre_review_semantic configured strategy extracts then forms candidates; _commit_prepared_store (local) and native workflow write_bundle (Postgres) accept candidates; _read_source_fragments/review_source_fragments, publication_readiness/technical_publication_readiness, ReviewDuty/source_accountability, source_context_review/source_bound_fields, deterministic repair catalog/details. Includes MRO and installed UI overrides, startup and explicit migration.
Supported runtime topologies: existing local single-worker file compatibility; native Azure PostgreSQL workflow (existing one/two workers). Production uses PostgreSQL; local compatibility representation persistence uses SQLite, never a production substitute. Existing source Blob and canonical/registry authorities unchanged.
Persisted-state impact: additive workflow.source_representations (immutable key/payload), immutable workflow.source_representation_bindings (snapshot -> ID and acceptance provenance); complete payload stored transactionally in PostgreSQL, avoiding a split Blob/database payload commit. Local SQLite equivalent is independent source-artifact acceptance, not workflow authority.
Compatibility/migration plan: expand storage/producer, migrate via explicit command with dry-run and stable proof, cut readers over. New completed processing supplies representations. Published migration never modifies working envelope; independent immutable binding is required precisely because envelope mutation is prohibited.
Rollback/recovery plan: retain tables/artifacts/bindings; compatible binary can keep source query behavior. An old binary with reconstructing GET is not a compliant rollback. A representation-compatible rollback binary must retain fail-closed source reading. No delete/backfill on startup. Failed migrations retry explicit command. Local interrupted registration can leave accepted unreferenced artifact; retry verifies exact identity, never implies successful receipt.
Cutover trigger: all new source-processing producer paths and installed bound readers have route/restart and mapping proof; legacy absent binding remains explicitly migration-required.
Cleanup/decommission criteria: remove wrappers required solely for read reconstructing once durable callers covered; pure reconstruction helpers remain for explicit production/migration, not queries.
Failure blast radius: source artifact/one snapshot binding; no historic review, release or serving mutation.
Adversarial proof matrix: alternate readers/writers/MRO, headings/filter conversions, missing schema, corrupt payload, checksum mismatch, stale fragment carriers, equal key/conflicting result, changed snapshot/revision/lease/roles, restart, post-commit retry, published migration without accepted extraction, object correction/rejection, native cross-process duplicate acceptance and rollback.

## Transaction and evidence
Payload and immutable binding are committed together in native PostgreSQL; existing document/object activation shares the existing workflow transaction. SQL uniqueness protects key and snapshot binding. No process lock as production concurrency proof. Failed outer transaction cannot leave binding accepted. Local standalone artifact acceptance can precede file workflow commit; orphan acceptance is harmless/reusable and has no receipt/serving authority.
Long extraction/reconstruction happens outside write transactions. Prepared payload is passed explicitly to existing commit boundary and is not persisted as competing envelope truth. Provenance records source/contract/result hashes, command/actor/policy/attempt when present, migration reason and timestamp.
Migration apply rechecks source/revision/authorization under existing transaction; published semantically identical historic derivation is additive, never writes envelope/object/binding reviews.

## Acceptance
Zero extractor/full reconstruct/model calls after representation exists on /publish, /review workboard/overview/tasks/details/source passage and repair catalog, including restart and disabled transient cache. Equivalent HTML and block/mapping outputs. Next request sees current review and permissions. Missing legacy binding returns migration-required with zero work. Native CAS/transactions, failure at accept/commit, expired worker, content conflicts and explicit published migration require proof.
Normal repository preflight, release preflight, compile, architecture checker, invariants and full suite; separate adversarial review. No completion claim with relevant UNKNOWN/NOT TESTED. Implementation, developer proof, merge and production validation reported separately.
