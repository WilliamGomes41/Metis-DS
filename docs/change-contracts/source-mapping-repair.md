# Conservative source mapping repair

Change class: B
Promise: New extraction retains ambiguous clinical numbers and records every inserted reconstruction join separator in source mapping.
Proof: Dose-column PDF regression; two/three-fragment and partial-boundary mapping; transform/export round trip and forged-mapping rejection.
Touches lifecycle invariants: no
Rewrite risk: high

## High-risk mitigation before versioned-reader implementation

Rewrite target: additive derived passage-mapping evidence and its versioned transform/export readers, not source, review or lifecycle authority.
Why local patching is insufficient: retaining an unversioned row union makes old readers reject new durable evidence under the same advertised version; explicit old/new readers and rollback limits are required.
Current authority/writer/reader map: immutable Blob source and original extracted fragments remain input authority. Semantic coverage/proposal formation writes mapping into the existing spec; generic transform validates it; the existing object-bundle transaction persists metadata in local/PostgreSQL workflow storage. Diagnostics, processing CSV/projector/MCP export and review UI read object metadata. Pre-review replay identity already includes reconstruction/semantic contract versions. No store, writer, lock or publication registry is replaced.
Supported runtime topologies: existing local/PostgreSQL document storage and single-instance App Service; pure mapping/transform/export semantics are identical. No additional worker/instance support.
Persisted-state impact: newly formed evidence uses semantic-passage-v1.1.0; old v1.0.0 metadata and five-field range rows remain readable without rewriting. Transform advertises semantic-generic-v1.1.0. CSV v4 and projector v3 advertise their expanded lineage columns.
Compatibility/migration plan: expand readers to recognize both explicit passage versions before producing new v1.1.0 evidence. The v1.0.0 reader rejects separator rows and compares only original raw ranges; the v1.1.0 reader requires mapping and verifies the complete reconstruction range/separator sequence. Unknown versions fail closed. No backfill, startup migration, downgrade relabeling, second authority or historical review mutation.
Rollback/recovery plan: preserve a reader capable of v1.1.0 after any new write. Stop new processing commands on failure and forward-fix or deploy a compatible reader; do not deploy a raw-range-only old binary against new mapping or downgrade labels. Keep original source, objects, reviews and attempts. Restoring data is outside this PR and requires the existing verified backup/recovery procedure.
Cutover trigger: old/new/unknown/forged-version tests, actual downloadable CSV regression, repository controls, full GitHub CI and separate adversarial review pass; later authorized deployment only.
Cleanup/decommission criteria: no temporary store or dual-write introduced. Retain legacy reader support while any v1.0.0 objects/specs exist; no removal or data cleanup in this task.
Failure blast radius: one candidate/export may fail validation; no existing source, object, review, publication or serving state is rewritten by these pure functions.
Adversarial proof matrix: original 20/25/30 dose column; two/three-fragment joins; boundary-only/partial selection; forged/missing separator, neighbors, extra keys and unknown versions; v1.0.0 with new row rejection; old raw-range round trip; new JSON round trip and downloadable CSV version/header/README; replay version binding; existing transaction/restart native-PostgreSQL suite. Separate review challenges all mapping consumers, legacy/version/fallback paths and rollback.

## Existing mechanism and change

Immutable source bytes and original extracted fragments remain the input authority. `extract_pdf_v2.extract -> mark_pdf_layout -> reconstruct_source_fragments -> semantic_source_blocks/semantic_units_from_proposal -> transform -> processing_evidence_tables` is the affected path. Geometry/cadence cannot distinguish a line gutter from a clinical column. Automatic exclusion is therefore removed; possible markers remain content with findings. Explicit pre-existing text views remain readable and are not rewritten. This is a conservative removal of an unsafe heuristic, not a claim that original Smetten processing will succeed.

Reconstruction still inserts one separator between adjacent grammatical continuations. Mapping gains a closed `join_separator` record with literal space and neighboring original fragment IDs. It never invents a raw offset. Transform regenerates and compares the complete mapping. Export identifies the separator independently of a raw fragment range. The downloadable lineage CSV retains these three fields as additive columns; its regression reads the actual ZIP. Existing raw range records retain their shape. Tests challenge forged text, missing separators, unknown neighbors and extra keys.

## State and compatibility

Domain entity/aggregate: derived source passage evidence in the existing object bundle.
Invariant(s): ambiguous clinical text remains input; raw bytes/positions are unchanged; synthetic separators are explicitly labeled.
Durable state before: existing snapshots, objects and reviews.
Durable state after: unchanged unless the existing authorized ingestion/retry creates a new validated bundle with additive separator evidence.
Transaction boundary: existing object-bundle commit, unmodified.
Failure/recovery result: transform rejects forged mapping before commit; existing retry rollback remains unchanged.
Duplicate execution / idempotency result: deterministic pure reconstruction; existing command deduplication is unchanged.
Concurrency result: N/A for these pure functions; no writer or lock changes.
Audit/evidence requirement: original source ranges plus explicit inserted separator in existing processing export.

No database schema migration, automatic backfill, snapshot identity, review, publication, serving or retry lifecycle change. The expanded lineage export advertises CSV schema v4 and projector/MCP schema v3 so consumers can choose the correct reader. New code accepts old raw-range-only evidence. Do not downgrade processing/export code for newly created separator evidence without compatibility checks. Roll back new processing with a compatible reader; retain existing objects and source evidence. No production mutation is part of this task.

Scope limit from adversarial review: separator evidence covers grammatical fragment reconstruction. Candidate formatting between separately selected source-block spans is unchanged; mapping does not promise exact reconstruction of that inter-block formatting. No claim of complete candidate-text reconstruction is made.
