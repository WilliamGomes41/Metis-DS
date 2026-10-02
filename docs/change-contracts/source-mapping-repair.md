# Conservative source mapping repair

Change class: B
Promise: New extraction retains ambiguous clinical numbers and records every inserted fragment join separator in source mapping.
Proof: Dose-column PDF regression; two/three-fragment and partial-boundary mapping; transform/export round trip and forged-mapping rejection.
Touches lifecycle invariants: no
Rewrite risk: none

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
