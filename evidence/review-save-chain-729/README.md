# Ordinary Review save, next and reopen — local evidence

This is a partial MET-36/#729 implementation, based on main `19a83d1`.
Runtime source identity, normalized request metrics and limitations are in
[local-results.json](local-results.json). No source content, secrets or production
telemetry is included. Local PostgreSQL17/Python3.13.5 is the supplied test stack;
CI's PostgreSQL16/Python3.12+3.13 remains separate required evidence.

The new HTTP proofs first failed on the actual lock and full-document navigation
paths (`01ad8819`). A second native byte-budget proof failed at3,969,244 bytes
for one object with512 retained successors (`2da87228`). Final selected read:
8,407 bytes,4 queries; the corrupt historical predecessor still refuses via the
original complete lineage check. No certificate is fabricated or repaired on GET.

The same existing1100-row/partial-formation HTTP chain observes persisted approval,
the retained decision on another passage, stale409 without writes, and continued
publication refusal. Final timings: open0.132s,save0.335s,next/overview0.696s,
reopen0.153s,stale0.125s. Actual outer lock163.387ms/TX163.356ms; unchanged
budgets3s/5s/250ms/500ms. This final run overlapped the full-suite partitions;
the baseline did not. Claim reduced selected-prefix bytes and removed in-lock
pure kernel work, not a statistically established POST speedup or Azure SLO.

Native tests cover actor/identity/roster/policy/source/quality/native0/binding/new
inbound races and late deferred-COMMIT rollback, including fresh runtime readback.
Existing source, passage, repair, failure and batch regressions are reused.
The separate independent adversarial review inspected current guards, fallback
paths, queue/source projection parity and transaction ownership; no concrete
blocking defect found. It executed no independent tests.

A disposable-copy mutation removed the current actor-identity guard: the native
identity-race test failed with `DID NOT RAISE ConsoleError`. Restoring the original
code made it pass. Removing only envelope/binding comparison did not defeat the
independent binding CAS, so that mutation is not reported as detection by that
particular removed guard. Deliberate mutations are absent from this branch.

Remaining limits: ordinary POST still records72 database calls in this workload;
database distance and remaining guard/write roundtrips need their own proof.
The end-of-queue overview redirect still reads14.6MB; it is not silently counted
as a bounded passage read. Optional/unprepared card navigation retains the full
compatibility reader. No production data conversion, merge, deployment, live
user acceptance or complete MET-36/MET-43/MET-44 closure is claimed.

Executed commands (test DSN supplied for an isolated local server):

```sh
python -m pytest -q tests/test_review_save_chain.py tests/test_review_passage_read_postgres.py
python -m pytest -q tests/test_prepared_review_batches.py tests/test_review_command_bounded_http_v1.py
python -m pytest -q tests/test_review_command_freshness_v1.py tests/test_review_command_repair_handoff_v1.py tests/test_review_command_source_failure_v1.py
python -m pytest -q -s tests/test_met36_bounded_review_history.py::test_native_retained_history_partial_formation_http_budget tests/test_review_save_chain.py::test_passage_read_keeps_lineage_without_downloading_retained_prefix
```

The final full-suite partition results and CI status are recorded in the PR.
An early full-suite attempt lacked `psql` on PATH and was stopped; the environment
was corrected. A partial earlier collection was stopped when the measured
retained-prefix overread required another implementation change. Neither is a
successful full-suite run. No PostgreSQL skip is treated as a pass.

The broad run found a real classification-repair/approval regression: after
same-path runtime reconstruction, the still-live original app resolved ledger
events through the peer's process-global registration. Main passed that test;
the first prepared ordinary implementation refused with forbidden preparation
I/O. The active matching command now supplies its own bound review store for
ledger reads, buffers and appends; outside the scope registry lookup is unchanged.
The new minimal HTTP regression was red before correction. After correction72
current-dependency, prepared-batch and actual classification/live-app tests passed.
The independent reviewer inspected this landed correction and found no blocker.
The actor-identity race additionally commits its winning change from a distinct
OS process before the original command's commit guard; the native proof passes.
