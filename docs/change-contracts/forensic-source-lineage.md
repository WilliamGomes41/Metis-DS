# Forensic source lineage projection

Change class: B
Promise: A selected candidate whose recorded coverage lineage is present gets that segment's source span and source text. A missing or conflicting lineage stays unresolved and is not filled in.
Proof: tests/test_forensic_trace_v1.py::test_selected_segment_keeps_its_own_source_span_when_block_map_is_absent and test_missing_lineage_stays_unresolved_and_does_not_fabricate_a_source_span. scripts/check_forensic_source_lineage.py reprojects a snapshot.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing path and authority

The forensic tracer stays a read-only projection. Authoritative joins, in order:

- formation task: `task_id`, target span containment on reconstructed `(block_id, start, end)`
- model call: `response.id`, same target-span containment
- semblock: reconstructed block id and block-local offsets
- coverage object: `object_id` with an exact span match; one semblock may have many segments
- lineage: `selected_raw_fragment_range` (`fragment_id`, raw fragment offsets)
- source stage: `current_object_raw_text` or `stored_admission_source_text` of that same object
- candidate, validation, admission, review: existing proposal, validator, gate and review-queue projection

Block offsets and raw fragment offsets are not the same coordinate space. Text is not a join key. A non-producing run is not a fragment source.

## What this change does

When the verified block map cannot slice a span, the projector follows the coverage object with the same block id and offsets. It uses that object's lineage ranges and that object's recorded segment text. `proposal_selected` and `coverage_remainder` stay separate rows. Ambiguous matches and conflicts stay unresolved.

`first_divergence_stage` stays empty without a gold case. That column is the gold comparison, not a route-exit inference. Recorded provider, validation, admission and review decisions remain on their own fields. This slice does not invent a second divergence model.

## Non-changes

No new source identity, no persisted provenance, no workflow mutation, no publication authority.
