# Forensic trace v1

Change class: B
Promise: A named reviewer can project one recorded source span through extraction, reconstruction, formation, provider decision, validation, transformation and admission, then a review-queue projection. The package does not export the review ledger, so this is not a human review decision. A derived block-to-fragment map is used only when its reconstruction version and source-blocks hash equal the recorded replay identity. A different version or hash is `RECONSTRUCTION_IDENTITY_MISMATCH` and does not link a source span. Rejected proposals and separate spans of one object stay on their own source span. The first stage that diverges from an explicit gold case is reported.
Proof: tests/test_forensic_trace_v1.py, including a processing-evidence ZIP written to disk and reloaded by the CLI. The known Smetten background sentence stays a RED diagnostic baseline. No provider call, database write, or workflow mutation.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing path and authority

Recorded evidence already lives on the WorkingRevision: semantic replay, provider evidence, source fragments, formation tasks, admission and the passage register. `scripts/replay_recorded_formation.py` replays a failed attempt. `processing_evidence_export_v1` already projects those authorities to CSV.

The gap is that those tables are not one span-keyed trace, so a visible review object is easy to treat as the origin of a bug.

## What this change does

`forensic-trace-v1` is a read-only projection. `scripts/trace_recorded_formation.py` reads a processing-evidence ZIP or a `forensic-evidence-v1` JSON file and writes `forensic_trace.jsonl`, `forensic_trace.csv` and `forensic_summary.json`. With a gold file it also writes `first_divergence.csv`.

Source-span identity is the source hash, reconstruction hash, ordered fragment ids and exact offsets. Text does not join spans. A missing stage stays `UNKNOWN`. An expected runtime that differs from the recorded runtime stops the comparison with `TRACE_IDENTITY_MISMATCH`. A different reconstruction is `INCOMPATIBLE_RECONSTRUCTION`.

`forensic_trace.csv` in export v11 is the same join. It adds no workflow state and no publication authority.

## Non-changes

No formation mode change. No V4 cutover. PR #524 is not part of this change. V3 product semantics are unchanged. The background baseline is expected to stay FAIL until a later semantic change is proven against this trace.
