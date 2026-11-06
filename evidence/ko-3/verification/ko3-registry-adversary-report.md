# KO-3 independent registry/retrieval audit

Final target: e74d438e50f2808622cb654e72627d17a0dddb04, base c6fa679b7c0cc630d24e32e4578e21398cb796c4. Initial audit target: d5febaafa3113139439f62f104f3bcff28f8107f.
Decision: PASS / READY WITHIN THE ASSIGNED REGISTRY AND RETRIEVAL BOUNDARY. F-1 was demonstrated on d5febaaf and is closed by the independently rechecked e74d438e fix. This is not an overall CI, performance, merge or deployment verdict.
Method: Code Quality Review CLOSURE plus risk-proportional verification. Actual PostgreSQL 17 at the test server; disposable per-test databases, actual canonical store and production console composition. No separate model or VM claim. Product worktree remained read-only except for one explicitly authorized mutation in its isolated throwaway audit checkout, restored afterward.

## F-1 — CLOSED: recorded withdrawal disappeared after same-tuple historical recovery

Publish R1 at T1; withdraw R1 at T3; recover R2 at T2 with the same snapshot/object ID/version/computed canonical hash, a separate release/working-revision identity, and preserve_newer_registry=True. The actual canonical writer keeps registry.state=emergency_unpublished and registry.release_id=R1; reopening the store still yields no active serving rows. The new reader chooses latest historical R2, which is published but explicitly recovery/preserved. object_release_status returns none instead of withdrawn. The existing recorded withdrawal is therefore lost in derived inventory presentation; canonical serving remains inactive.

Reproduction: tests/ko3_registry_adversary_tmp.py::test_recovered_same_tuple_does_not_erase_its_recorded_withdrawal, log /tmp/ko3-registry-recovered-tuple-d5febaaf.log. The test uses existing store commands, not a modified publication writer. Production recovery uses the same preserve flag in src/publication/legacy_canonical_recovery_v1.py:236.

Smallest remedy to investigate: recognize withdrawal of the exact selected tuple in current registry metadata before falling back to a later historical release record. Retain source/version/hash matching and do not add a serving gate or alter publication writes.

## Executed verification

Five independent PostgreSQL cases passed in 1.40 seconds, then again in 1.39 seconds after mutation restoration:
- Batched selectors do not borrow publication from another snapshot, unpersisted working version or wrong computed hash; forged stored hash aliases do not make the working version published.
- Wrong snapshot cannot borrow a withdrawn tuple's history.
- Legitimately deleted predecessor registry rows remain superseded, while subsequent history-only recoveries remain inactive.
- Actual canonical store output retains published parent context in retrieval; published retrieval does not call live workflow derivation, and active registry remains authoritative despite contradictory historical release status.
- Actual production readiness, publisher consideration and state inventory do not rewrite business rows (ctid/xmin included) or immutable source bytes. The real AzureBlobSourceStore adapter uses the existing disk transport fixture; this is not Azure production evidence.

An initial sixth test fixture error reused globally unique release_version=1 for two releases. The disposable helper was corrected to unique release-version labels; no product finding was inferred from that setup error.

## Decisive mutation check

Only in /workspace/Metis-ko3-audit, replace the SQL historical lookup's WHERE source.snapshot_id=%s with WHERE %s::text IS NOT NULL, preserving SQL parameter count/type. The actual wrong-snapshot test failed specifically because withdrawn was returned instead of none. There was no import, syntax or driver failure. Log: /tmp/ko3-registry-snapshot-mutant-d5febaaf.log.

Original canonical-store bytes restored (SHA-256 85673ea7d00aad8f1b723fea07962ccb080047295dc04cf8cbdcf9ace6547486). git diff --exit-code -- src passed. Restored five-case proof: /tmp/ko3-registry-restored-d5febaaf.log. F-1 remains a real failing sixth case; it was not filtered into an overall PASS claim.

## Targeted closure at e74d438e

Reviewed the actual d5febaaf → e74d438e production difference: two raw registry-withdrawal metadata columns and an exact selected-tuple registry match evaluated before the newer historical record. No publication writer or serving query changed. Active facts still win; emergency_unpublished now preserves the selected tuple's withdrawal.

All six independent actual-PostgreSQL cases pass in 1.45 seconds. The withdrawal test also challenges an unpublished working version, changed content hash and foreign snapshot, so the fix cannot borrow the old withdrawal for a different tuple. Physical ctid/xmin and immutable-source checks pass. Log: /tmp/ko3-registry-adversary-e74d438e-closure.log.

The mutation result remains scoped to the unchanged snapshot SQL predicate on d5febaaf; it was not repeated or relabeled as a new-head mutation. The exact predicate and its parameter contract are unchanged by e74d438e. Final git diff --exit-code -- src is clean; the only untracked audit file is the independent test harness.

## Limits

No timing, performance verdict, deployment, production database access, full-system suite or endpoint-authentication proof was performed by this lane. Parent owns combined gates/live evidence. No open demonstrated finding remains in this bounded pass. No main index edits, commits, pushes or production fixes were made. No test or child process remains active.
