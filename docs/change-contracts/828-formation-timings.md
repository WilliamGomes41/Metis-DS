# Formation: per-task timings and checkpoint size

Change class: B
Promise: After a processing attempt the trace MUST show, per source task, its index and the planned task count, the time spent in the model call (`transport_seconds`), in the whole provider call (`provider_seconds`), in validation afterwards (`validation_seconds`) and in the checkpoint writes before and after the task, including the last task of a run. Tasks skipped by a budget stop MUST appear as `not_started`. Every checkpoint record MUST carry its size in bytes. The formation itself, provider evidence and the replay identity MOGEN NIET change.
Proof: `tests/test_bounded_formation_v1.py` (plan and timings per task, validation time on rejection, transport time apart from provider validation, `not_started` on a budget stop) and `tests/test_processing_trace_v1.py` (export and cleaning without text, checkpoint size, and a full console resume in which every task, the last one included, has `checkpoint_after_seconds`).
Touches lifecycle invariants: no
Rewrite risk: none

Decided by William (2026-10-23): GO for step 1 of the architecture analysis, measure before speeding up. Definition of done agreed on 2026-10-23: after deploy and one Smetten resume, the trace shows how each task's time splits over model, validation and storage. Out of scope: speeding up, merging tasks and extra fields such as tokens and characters.

Measurements are attempt-owned diagnostics. They never enter provider evidence or the replay identity, so existing progress stays resumable.
