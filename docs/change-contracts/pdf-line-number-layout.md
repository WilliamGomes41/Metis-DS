Change class: B
Promise: Recognize document-wide PDF line gutters in the derived reading view while retaining immutable raw text and exact evidence mapping.
Proof: Multi-page geometry fixtures, retained clinical/table numbers, strict hidden-gap rejection, a synthetic nineteen-recommendation provider/transform proof, and a private local replay of the recorded Smetten proposal.
Touches lifecycle invariants: no
Rewrite risk: none

Existing authority and path: extract_pdf_v2.extract produces immutable raw fragments, mark_pdf_layout annotates layout, reconstruct_source_fragments validates reversible source_text_view, semantic_source_blocks supplies the derived view to the provider, and semantic_units_from_proposal enforces exact evidence and contiguous passage selection. Raw fragment hashes remain authoritative. Existing derived-view support is reused.

Behavioral change: identify only a right-aligned outer numeric gutter with at least twenty markers across three pages, a single sequence starting at 5 on page 1 and increasing in five-step increments across the document, and predominantly five body baselines between markers. Short, discontinuous or body-aligned sequences remain ambiguous content. Every omission records its exact raw range, coordinates and recognition evidence. No proposal repair, inferred clinical text, relaxed gap checks, or persisted-source backfill occurs.

Affected functions: mark_pdf_layout and its pure geometry classifier; extract parser version. Existing extraction, reconstruction, provider and transform boundaries remain in place. Re-extraction is required for old fragments without geometry; old snapshots are unchanged.

State: fresh extraction may add source_text_view and layout findings. Raw text, fragment hash contract, published objects, review confirmation, lifecycle and serving registry remain unchanged. Existing v1 mapping serialization remains compatible.

Domain entity: extracted source fragment and reversible derived reading view.
Invariant: each retained character resolves to immutable raw text; no clinical number is deleted based on its value alone.
Durable before/after: existing snapshots unchanged; new snapshots retain raw fragments with additive verified layout annotations.
Transaction: existing ingest transaction; no new writer or migration.
Failure/recovery: ambiguous layouts retain content; malformed views fail existing validation.
Idempotency: deterministic classification for the same geometry and text.
Concurrency: N/A, pure extraction before existing snapshot persistence.
Audit: exclusions include raw bounds, geometry, classifier version and document-wide proof summary.

Rollback: retain existing snapshots; reverting extraction disables new classification. No persisted migration is required.

Validation scope: the recorded provider response is projected in a test fixture onto newly derived source views (only verified omitted raw ranges are removed); one pure strength label becomes supporting evidence rather than candidate prose. This proves all 19 corresponding selections and the provider-validation-transform path with a stubbed response. It does not claim a new live model run or deployment. The original raw response remains in the private local fixture and must still fail with semantic_span_hidden_gap.

Existing blocked-document retry: operations_console_v1 reextracts the verified immutable PDF bytes through _fragments_and_spec and _extract. The new parser version and derived-source hash invalidate reuse of an old semantic response. The existing reservation, stale-revision guard and commit transaction remain authoritative; no fresh upload or source-byte edit is needed.
