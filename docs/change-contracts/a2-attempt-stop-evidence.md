# A2 attempt stop evidence and structured logging

Change class: B
Promise: Every attempt finished by processing_retry_v1 MOET record an explicit stop_reason (done / budget_exhausted / error) and, for succeeded attempts, the semantic contract version of the replay it produced; processing traces MOETEN project both; the console entry MOET install one global JSON log handler that NOOIT emits secrets. Attempt state, retry, resume, publication and verdicts MAG NIET change.
Proof: Fail-first tests in tests/test_a2_attempt_records.py (21 red on 8db82cb, 21 green after), existing processing-trace, bounded-lifecycle and retry suites unchanged and green, and the full local suite compared with the same base.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18 (Metis `docs/BESLUITEN.md`). Rules below use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG.

## Change

Base: `8db82cb9a73da81bd1c9d8d0bbf20456dabb9bc7`. Scope set by Metis (CoS) for PR A2.

1. `src/processing_retry_v1.py`, `finish()` and `expire_running()`: the attempt
   record gets `stop_reason` and `semantic_contract_version` (additive fields).
   - `stop_reason = error` MOET hold for every non-succeeded finish and for expiry
     (`interrupted`).
   - `stop_reason = budget_exhausted` MOET hold only when the current replay's
     `provider_evidence.formation_incomplete` is `true` AND a call carries
     `source_task_budget_exhausted`. A resume that completes after earlier budget
     history MOET record `done`.
   - `semantic_contract_version` MOET be read from
     `semantic_replay.identity.components.semantic_contract_version` (built at
     `src/pre_review_semantic_v1.py` `build_replay_identity`). For non-succeeded
     attempts it MOET be `None`: the stored replay belongs to an earlier attempt
     and recording it would be stale.
   - The recorded fields MAG NIET change `state`, retry budget, resume offer or
     publication eligibility. Correcting `succeeded` on budget exhaustion is A3.
2. `src/processing_trace_v1.py`: `project_attempt` and `clean_trace` project
   `stop_reason` (closed set) and `semantic_contract_version` (bounded token).
   Legacy attempts MOETEN project `None`; there is NO backfill.
3. `src/structured_logging_v1.py` (new) and `src/console_asgi.py`:
   `install_structured_logging()` MOET run first in `build_app()` and installs
   exactly one root JSON handler (idempotent). Each record holds `timestamp`,
   `level`, `logger`, `message`, `commit` and only the fixed extras
   `request_id, event, attempt_id, snapshot_id, phase, reason_code`. Bearer
   tokens, password/secret/token/api-key/account-key/SAS/instrumentation-key
   assignments, URL credentials and `sk-` keys MOETEN be redacted. Exceptions
   MOETEN report `exc_type` only; exception prose and tracebacks MAG NOOIT be
   logged. The existing `metis.console.diagnostics` logger keeps its handler and
   `metis_diagnostic` format (it does not propagate).

## Not in this PR (stopped, see PR body)

- Publish-gate refusal audit event: this touches the publication gate. Forge
  MOET be informed first; no code before that.
- Per-document disposition-vs-object summary: OPENVRAAG-A2-1, see below.

## State and invariants

Only additive attempt fields and log formatting change. Source identities,
candidate text, verdicts, canonical hashes, publication gate, authorization and
retry/resume rules MAG NIET change. `src/operations_console_v1.py` and the
publication gate are NOT modified. No new dependency, migration or background job.

## Open questions

OPENVRAAG-A2-1: which "disposition" is meant (passage-register disposition,
definitive review disposition, or source-accountability classification), and on
which surface MOET the per-document summary appear (processing trace, console
page, or diagnostics log)?

OPENVRAAG-A2-2: MOET a failed attempt record the contract version it attempted?
That requires capturing the version at reservation time, which reads the
processing configuration in `src/operations_console_v1.py`; Forge MOET be informed
before that change.
