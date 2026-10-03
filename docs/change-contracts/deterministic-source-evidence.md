# Deterministic positioning of literal source evidence

Change class: B
Promise: Exact, unambiguous source evidence survives model character miscounts;
absent or ambiguous evidence is rejected before any candidate activation.
Proof: Recorded Smetten failure, provider/validator integration, local persisted
objects and restart/replay, plus adversarial exact-match tests.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing path and authority

`semantic_source_blocks` / `_reconstructed_blocks` normalize reconstructed visible
prose once for the canonical semantic block. `_request_payload` serializes those
strings; `semantic_units_from_proposal` reconstructs the same strings. The recorded
Smetten block is 131 Python code points at both boundaries, with `Sterk – voor`
at 119–131. Recorded 0–133 fails `semantic_span_bounds_invalid`. The supplied dump
and current code establish no whitespace/Unicode discrepancy explaining +2.
The model's internal reason for choosing 133 remains unknown.

Existing execution is `_provider_proposal -> semantic_units_from_proposal ->
attach_relation_proposals -> existing objectset/run commit`. Model offsets are
currently checked for bounds, but bounds alone cannot verify intended source
selection. The new provider contract copies a literal source substring. A pure
resolver inside the existing kernel boundary calculates its exact span before
all unchanged candidate, field, recommendation, context and relation checks.

## Domain and invariants

Source evidence is a reproducible reference to canonical source text, not newly
authored prose. Semantic selection remains model-proposed and subject to human
review. Positioning is stateless; the existing WorkingRevision and processing
attempt remain stateful and owned by the kernel. No console-owned truth, new
workflow state, schema migration or publication/serving authority is introduced.

- `block_id` must exist; one ID cannot have conflicting canonical text.
- A nonempty literal must match exactly, without normalization or fuzzy repair.
- Null occurrence requires exactly one match. Repeated text requires an explicit
  zero-based occurrence, counting overlapping matches; invalid indices fail.
- Offsets accompanying a literal are hints only; they never choose an occurrence.
- Resolved spans satisfy `0 <= start < end <= len(text)` and reproduce the literal.
- Existing validators retain eligibility, containment, source order, semantic
  consistency and provenance checks. A resolvable literal is not admission proof.

## Transaction, failure and concurrency

All references, including relation endpoints/evidence, resolve before validation
and existing atomic objectset activation. The resolver performs no writes.
Invalid resolution uses `semantic_evidence_*` validation findings and the existing
failed-attempt/recovery path. Existing work/replay is preserved; no automatic
retry, destructive reset, migration or historical repair occurs. Duplicate inputs
produce identical spans. Existing replay identity and revision concurrency checks
remain responsible for duplicate processing and concurrent commits.

## Compatibility and provenance

The wire schema uses `block_id`, `literal`, `occurrence` for every reference in
both semantic provider modes, including field/context evidence and relations.
The provider boundary also accepts offset-only legacy proposals, which undergo
unchanged strict validation. They cannot be repaired without explicit literals.
This compatibility path is useful for existing injected transports and diagnostic
records; it is not offered by the new structured-output schema.

Replay stores the resolved, validated existing proposal format. Raw provider JSON
remains in `provider_evidence.response.output_text`; attempt diagnostics retain
the raw `proposal` and its hash separately from `resolved_proposal` and its hash.
Diagnostic replay runs the same pure resolver against recorded canonical input;
validator identity pins its implementation. Changed prompt/schema and resolver
contract version invalidate old execution reuse, without deleting old records.
Stored object evidence, span identity and raw-source mapping remain unchanged.

Rollback: revert producer/resolver changes for new processing. Existing resolved
objects and replay proposals remain readable by the old span contract. Old prompt
identity cannot reuse the new replay; it must make its own fresh call. No backfill
or cleanup of historical evidence is needed.

## Review and scope limits

Adversarial checks cover repeated/overlapping literals, missing/changed evidence,
Unicode dash/normalization/whitespace distinctions, conflicting block text, offset
hints, unknown IDs, field containment and recommendation direction/strength.
The unchanged validator continues to decide eligibility and semantic consistency.

Literal selection can still be semantically wrong. Full candidate text ending in
a strength label remains subject to the existing `incomplete_sentence` admission
rule. The storage acceptance test selects the complete recommendation sentence
and binds the label separately as strength evidence, without relaxing that rule.
No live model/provider, production or Azure test is implied by injected responses.
