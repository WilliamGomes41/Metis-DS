# Slice 2 — issue #616

Change class: B
Rewrite risk: none
Touches lifecycle invariants: no
Promise: follow the existing accepted command through durable attempt, claim,
recorded checkpoints and outcome after restart, without executing processing.
Proof: real HTTP reservation/export, restart/duplicate/claim/rollback/fence
scenarios on local and native PostgreSQL stores; existing regression gates.

The existing workflow envelope owns processing_attempts and diagnostic evidence.
Reservation uses source_selection.reserve_selection -> processing_retry.reserve
inside _reprocessing_transaction -> _commit_prepared_store. HTTP runs it in
asyncio.to_thread. Dispatch notify is only a wake hint; pending discovers the
same durable attempts. claim chooses the worker in the existing row transaction.
_execute_source_attempt rechecks stored identity and authorization before slow
preparation. _diagnostic_writer uses a short transaction; extraction retains the
existing verified prepared_source_extraction. Activation rechecks source,
configuration, revision and permissions and commits through the existing owner.
PostgreSQL joins writes to the surrounding workflow transaction; a log emitted
on an operation return is therefore explicitly not proof of SQL commit.

| Context | Producer -> consumer | Existing owner/lifetime | Missing/stale |
| --- | --- | --- | --- |
| Generated HTTP request ID | RequestDiagnostics -> reservation/export | attempt.diagnostic; attempt lifetime | absent on legacy/CLI; never invented |
| Command/attempt/retry link | reserve -> dispatcher/export | processing_attempts | existing duplicate/conflict/fence rules |
| Source/version/revision/config | existing reservation -> preparation/activation | envelope and attempt | unchanged existing checks; operational values hashed |
| Claim token | claim -> execution | existing dispatch | never exported or logged |
| Checkpoint phase/time | diagnostic writer -> trace | existing diagnostic.checkpoints | partial history explicit; not a validated model replay |
| Retained extraction | preparation -> retry/read | prepared_source_extraction | existing integrity/identity/contract checks |
| Semantic continuation | activation -> compatible resume | semantic_replay | diagnostic checkpoints alone do not authorize resume |
| Runtime observations | existing execution boundaries -> logs | disposable telemetry | loss does not change domain result |

Stateful Class B overlay: the only added durable field is bounded request
correlation in existing attempt.diagnostic, atomic with reservation. No parallel
state is introduced. A repeated command preserves original correlation. Failed
reservation/commit leaves no accepted evidence. Concurrent claim has one winner;
reads do not expire, retry or claim work. Existing published/review/revision and
source/configuration fences remain unchanged. No migration or backfill.

Trace/export is a stateless bounded projection of stored evidence. It hashes
caller-controlled command/revision/version fields, excludes source/model prose
and credentials, and does not read/reconstruct source or objects. Missing logs,
historical correlation, incomplete history and derived expiry are explicit.
The existing processing ZIP and offline incident export reuse that projection.

Branch starts at 7cd6794 (slice 1 on fix/source-selection-diagnostics); main is
08f75f1. The delivery PR targets main and includes the unchanged reviewed #615 diff as
its prerequisite; its body must distinguish that prerequisite from new slice-2
work. Repository work only.
