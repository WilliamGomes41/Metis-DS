# D5 verification and bounded Class A reviews (#785 / #730)

Baseline: merged D4 `629d63c5f2ba8781f7b2c1307e8011c6476b63e2`.
D4b: `8f3d1fa`; product removal: `212b1d4`.
The [change contract](785-d5-pg-without-mirrors.md) records the supplied scope,
reader map, authority, lifecycle, rollback and recovery contract.

## Native evidence

Executed locally on a disposable PostgreSQL 16 server. Every `complete_postgres`
case owns and drops a separate database. No production state or runtime data was
used. Python versions: 3.12.14 and 3.13.5.

| Proof | Python 3.12 | Python 3.13 | What it establishes |
| --- | --- | --- | --- |
| D5 acceptance set | 18 passed | 18 passed | Both console classes; lifecycle, recovery, corrupt Blob, partial publication, process crash, code rollback |
| Two actual worker processes | 2 passed | 2 passed | Same PG and runtime; one review succeeds, one revision conflict; zero mirror access |
| Transaction/savepoint/rollback regression | — | 87 passed | Original failure survives recovery failure; no writes after rollback; caught participant fault; concurrency |
| Supplement | — | 159 passed | Source context, strict revision lineage, delete rollback, publication, withdrawal/recovery, persistence, architecture, participation, telemetry |
| Proxy-sensitive SSRF suite | — | 21 passed | Same tests with injected host proxies disabled, as required by their pinned-socket test setup |

The acceptance sets and worker proofs have **zero skipped or xfailed cases**.
Each of the two console classes completes all fifteen lifecycle phases in each
of control, guarded empty/read-only, and poisoned-existing-file mode. All six
runs per Python version register zero workflow mirror, projection or manifest
accesses. PostgreSQL tables are compared at every phase; poisoned files remain
byte-for-byte unchanged.

The rollback subprocess imports the actual `git archive` of `629d63c`, restores
the same PG snapshot, seeds obsolete copies, and continues review → publish →
withdraw. It compares the complete normalized PG export and decoded Product API
JSON with the same continuation on D5. Normalization excludes per-run clocks,
review chain hashes and credential salts/hashes; each exported chain is checked
independently. It does **not** claim byte-identical HTTP responses.

The crash subprocess calls real `os._exit(73)` after envelope and unbuffered
ledger writes inside an open PG command. Exact PG table equality before startup
proves rollback independently of normal reconciliation writes. Fresh startup
then sees the original objects, envelope and ledger.

Old `629d63c` delete does read existing object bytes as an opaque file backup.
They are not parsed or passed to PG writers. Unreadable old copies can block that
old delete command. The general old-code zero-read claim is false and is not
marked green. D5's zero-access promise includes delete; the demonstrated old-code
rollback route retains PG authority and does not lose workflow state.

## Test environment corrections

The first broad run used some old mirror expectations and was started before
all test adaptations were complete. Additional legacy suites also reset the
same supplied scratch DB, causing schema races; those results are not a green
full-suite claim. Later runs use separate owned DBs. The initial supplement's
three SSRF failures came from host proxy injection; all 21 security cases pass
with proxy variables cleared. Missing optional telemetry test dependencies were
installed in the execution venv, without changing runtime dependency files.

The final whole-suite result and final-revision check results are recorded below
when the current run completes. Earlier red artifacts are retained in the task
workspace for traceability, not presented as product regressions or waived tests.

## Bend and LAWS.bend

The [bounded D5 evidence model](../../experiments/bend/pr-d5/README.md) receives
actual native JUnit observations, retained with their SHA-256 digests. Bend's
standard checker returns `ALL PROOFS CHECK`; a deliberately false zero-access
claim with one access is rejected on the Boolean equality. Existing Bend
experiment tests: 4 passed; D2 `PROOF.bend`: passed. Existing laws were unchanged.

[Retained classification result](../../experiments/bend/pr-d5/verification.json).
This checks evidence classification, not Python semantics, exhaustive reader
coverage or an independent-kernel proof.

## Lex

Bounded attack round: no new proven product blocker. PG publication status,
audit, Blob validation, native events and savepoints remain. No alternate route
was found in inspected MRO, class-change, second-review and ledger paths. The
bindings-only commit retained its stale-map rebase before guard/write; a targeted
attack confirmed another snapshot's newer bindings survive. Guard unit cases:
8 passed independently on Python 3.13.

The follow-up inspected the old delete backup and confirmed it cannot supply
PG workflow content. The review covers inspected code and artifacts; it is not
an independently repeated complete lifecycle run.

## Sherlock

Bounded code review: no material finding. Checked file-topology compatibility,
PG status/audit idempotence, partial-publication startup repair, savepoints,
event buffering, post-commit source cleanup and PG-only recovery wrappers.
Follow-up checked real archived-code rollback and real process-crash setup.
Rollback establishes normalized PG and decoded API equality, not byte-identical
wire responses. No merge-GO was issued from these bounded findings alone.

## Argos

| Gate | Verdict | Evidence boundary |
| --- | --- | --- |
| Continue implementation | GO | D4b and supplied scope decisions are present |
| Content reviewable | GO | No new proven product blocker |
| Merge | Pending final checks and human review | Current full suite and final revision must be closed; old-code delete-read limitation must stay explicit |
| Deploy | NO-GO | #695 restore proof on the final D5 code with real Azure authorities |

Argos inspected the native JUnit artifacts, source changes, rollback/crash
setup, Bend output and architecture check. No new broad review is required;
only the final suite/revision closes this bounded gate report.
