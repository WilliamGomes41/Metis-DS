# Forensic trace v1

Change class: B
Promise: A named reviewer can project one recorded source span through extraction, reconstruction, formation, provider decision, validation, transformation and admission, then a review-queue projection. The package does not export the review ledger, so this is not a human review decision. The trace follows the producing run whose semantic identity equals the active replay, that run's attempt, and the bounded provider call whose target produced the span. An open call failure with target spans, call id, error code and failure reason stays on that source span, including after a ZIP reload. Root and supplementary calls stay separate; their rejections retain call-local provenance. A rejected source assessment keeps an empty span list for recovery; its location is diagnostic evidence only. Validator identity is taken only from the producing attempt. An initial task plus a later recovery task is history, not a conflict. A rejection covered by the validated selection stays historical and does not replace the current provider decision. Verified derived reconstruction is allowed only when all retained reconstruction inputs reproduce both the recorded reconstruction version and source-blocks hash. CSV formula escaping round-trips a leading apostrophe. Rejected proposals and separate spans of one object stay on their own source span. The first stage that diverges from an explicit gold case is reported.
Proof: tests/test_forensic_trace_v1.py, including a processing-evidence ZIP written to disk and reloaded by the CLI. The known Smetten background sentence stays a RED diagnostic baseline. No provider call, database write, or workflow mutation.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing path and authority

Recorded evidence already lives on the WorkingRevision: semantic replay, provider evidence, source fragments, formation tasks, admission and the passage register. `scripts/replay_recorded_formation.py` replays a failed attempt. `processing_evidence_export_v1` already projects those authorities to CSV.

The gap is that those tables are not one span-keyed trace, so a visible review object is easy to treat as the origin of a bug.

## What this change does

`forensic-trace-v1` is a read-only projection. `scripts/trace_recorded_formation.py` reads a processing-evidence ZIP or a `forensic-evidence-v1` JSON file and writes `forensic_trace.jsonl`, `forensic_trace.csv` and `forensic_summary.json`. With a gold file it also writes `first_divergence.csv`.

Source-span identity is the source hash, reconstruction hash and canonical raw fragment ranges; when reconstructed block coordinates are recorded they are part of the primary identity so spans that differ only across an inserted separator cannot collapse. A legacy raw-range id is used only as an unambiguous compatibility alias for older gold cases. Text does not join spans. A missing stage stays `UNKNOWN`. An expected runtime that differs from the recorded runtime stops the comparison with `TRACE_IDENTITY_MISMATCH`. A different reconstruction is `INCOMPATIBLE_RECONSTRUCTION` or `RECONSTRUCTION_IDENTITY_MISMATCH` when current derived reconstruction cannot prove equality with the recorded replay.

`forensic_trace.csv` in export v11 is the same join. It adds no workflow state and no publication authority.

## Non-changes

No formation mode change. No V4 cutover. PR #524 is not part of this change. V3 product semantics are unchanged. The background baseline is expected to stay FAIL until a later semantic change is proven against this trace.
