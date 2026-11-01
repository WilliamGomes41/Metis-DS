# MET-36: native retained-history mutation proof

The actual local heavy HTTP save fell from22.654s (two red tests in commit
877e0bb) to0.363s in the latest focused run. Open/redirect/reopen/stale steps are
recorded individually in [local-results.json](local-results.json). This proves
that slice with synthetic retained history, not production recovery.

Prepared ordinary Review and one actual single source-context HTTP operation use
current raw heads and validated prefix inputs. The source operation is tested at
small,1500 retained revisions and1500 revisions plus independent documents,
events and bindings, prohibiting full/global readers and extraction on POST.
No timeout, readiness or publication rule was relaxed.

The latest ordinary outer hold is282.394ms and does **not** meet250ms; transaction
282.363ms meets500ms. Source outer holds78/111/108ms meet250ms. Total ordinary
save meets the unchanged3s budget. These distinct requirements remain distinct.
Full#729, D2/V3, group source operations and production existing-data acceptance
remain open. Oldm2 compatibility intentionally retains full objectset equality.

Reproduce using PostgreSQL16 and the repository's standard test environment:

```sh
bash scripts/test_postgres.sh
python -m pytest -q -s tests/test_met36_bounded_review_history.py tests/test_met36_source_command_scaling.py
python -m pytest -q tests/test_revision_frontier_store_v1.py tests/test_revision_frontier_migration_v1.py tests/test_revision_frontier_recovery_v1.py tests/test_met36_source_admission_context.py tests/test_met36_native_signin.py tests/test_review_command_freshness_v1.py
```

Tests assert strict anchor hash, physical/payload identity, hidden historical
protection, stale/forged carriers, native0/truncation invalidation, same-connection
extra writes, before-trigger changes or suppression, exact numeric JSON identity,
ordered transitions, actual unlinked clinical context, D1 and rollback. The
source-neighbour negative control failed at the intended assertion when adjacency
was deliberately removed through an isolated test-only patch. Product source
was not modified by that control. The restored final source-context test passes.

The [independent review](adversarial-review.md) records findings and subsequent
fix inspection. Native execution belongs to the owner's logs/results rather
than the reviewer's unavailable socket. The new BEFORE-trigger negatives passed
in the35-node focused run. The additional document-serialization and archive
preparation checks are recorded separately with the final suite outcome.

The SQL migration is additive identifier/index coverage. Existing snapshots need
explicit `scripts/prepare_revision_frontiers.py --snapshot <id>` and `--check`
after authorized migration/grant installation. Preparation changes derived input
only. It is not ingest, model processing, review approval or publication.


Full local suite:6804 collected;6754 passed,43 expected optional-profile skips,
zero PostgreSQL skips, seven failures. The failures identified five outdated
migration mocks and two real processing/admission lock regressions. These were
fixed by restoring default FOR SHARE and explicitly opting only the bounded
Review command into KEY SHARE. All84 affected processing/identity/migration tests
then passed. Exact final-tip full CI remains required; the earlier full run is
not all-green. The separate final Review/source regression result is in the PR.
