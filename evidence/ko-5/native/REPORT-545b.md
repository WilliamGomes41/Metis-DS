# Independent native / rollback verifier: PASS within stated scope

Exact target `545b9e4790f9b36e47f0dc3710deb9c01dc9258c`, clean immutable `/workspace/Metis-ko5-verify-fixed`. Base `07db5080666f0428a454f5a705e50825a4fc5506`; previous KO4 source version `c4db3bd84bfe722ab235eff67d2ccf69b60a785b`. Codex shared host, PostgreSQL17 UTF8, Python `/workspace/.venvs/metis-ds/bin/python`. Supplied root server left running; all disposable isolated databases owned/dropped through existing tests.postgres_support; every PG execution explicitly granted loopback network access. No production, owner-tree edits, external comments, merge or deployment.

## Resolved finding

The prior exact44de phantom tree work remains fully recorded in REPORT-44de.md, phantom-tree44de.json and receipts. 545b removes the obsolete Documenten/API compatibility tree badge and returns tree0 for all roles. Actual assigned personal Review projection remains the owner. No new global reads, status policy, or hidden readiness evaluation was added.

Independent legacy/compact checks `test_fixed_badges.py` prove: open personal review remains1 for named researcher/reviewer, publisher0; both production MRO and explicit OperationsConsole paths return tree0; after real review completion the fixture still has needs_review headings marked used_as_context, yet production personalReview0/tree0; stale clinical_rereview_required=true and forged review_passes cannot invent tree work; actual publish preserves active serving and zero production personalReview/tree. 2 passed in 2.88s (`focused-own545b-corrected.log`). No false claim that the deeper OperationsConsole base personalReview is itself identical to the optimized production projection: its preexisting completed-context review1/ingest1 discrepancy was reproduced on exact07db (`base07db-existing-counts.log`: 1 passed1.18s; JSON contains all roles). Those base review/ingest paths were untouched by this change.

## Focused verification

`scripts/test_postgres.sh` passed first at exact545b.

```
METIS_TEST_POSTGRES_DSN=postgresql://postgres@127.0.0.1:55440/postgres PYTHONPATH=/workspace/Metis-ko5-verify-fixed /workspace/.venvs/metis-ds/bin/python -m pytest -c /workspace/Metis-ko5-verify-fixed/pytest.ini -q -p tests.conftest /workspace/ko5-native-evidence/test_fixed_badges.py /workspace/ko5-native-evidence/test_distinct_prepared.py tests/test_ko_single_way.py tests/test_console_badge_counts_postgres_v1.py
```

In initial combined run, 21 production/policy tests passed and 2 external tests had an overly broad expectation that direct-base personalReview must equal the production projection after completion. Existing baseline reproduced that difference; external test corrected to scope tree0 on both paths and authoritative personalReview exactness on production. Corrected external tests2 then passed independently. Exact source diff inspection confirms no review, policy, prepared source, staged writer, transaction, registry, schema, recovery or concurrency code changed between44de and545b; the only production edits are waiting_task_counts and obsolete SQL badge predicate removal in two files. Prior independent84-pass native/policy/W1/epochs/two-worker/recovery proof therefore carries for those untouched functions. The exact545b run also independently re-executed singleway18, badge suite2 and distinct explicit ReviewClosureConsole prepared-source policy-refusal test1. The latter proves preparing=true/store lock depth0/no transaction plus no physical object/binding/event writes and reset buffers.

## Real old-code rollback and mutation

Two separate owned fixtures both PASS:

- `head-acts545b.log`, `head-acts545b/`: exact545b natively ingests/reviews/publishes ordinary prior release, produces high-risk ordinary+boom successor tuples 1.0→1.0.1, then actually completes independent second reviews. Before and after second reviews, separate head/base07db/previousKO4source processes read/start on that same committed database and immutable source bytes. Full object histories, exact bindings, KO states, readiness and own old schema validation results agree across all versions. Per-actor badge dictionaries also agree in both phases (tree0, open Review1/2→closed1/1 due to other genuine pending boom work).
- `old-acts545b.log`, `old-acts545b/old-action.json`: exact545b writes pending high-risk ordinary+boom successors; previous oldKO4 source version c4db process executes two genuine approve_second_review commands against those head-written tuples, current expected_revision and independent reviewer. Assertions require pending stage before, same tuple/version after, exact two approver identities, no old-schema errors. The old mutations add exactly two bindings/two review events. Subsequent head/base/oldKO4 readback agrees across all full views and badges. No fixture reconstruction/restore under old code.

Commands for the above use rollback_probe.py with `--head /workspace/Metis-ko5-verify-fixed --base /workspace/Metis-ko5-base --ko4 /workspace/ko5-native-evidence/old-ko4`, second proof additionally `--old-act /workspace/ko5-native-evidence/old-ko4`, and their respective output paths.

Physical invariant assertions retain complete payload+ctid+xmin for object/binding/event/canonical/source/release/items/registry/audit tables across reads/startups; existing published snapshot objects/bindings/events/envelope remain physically unchanged during old mutation. Existing baseline startup reconciliation is bounded exactly: one published workflow.documents row, revision+1, updated_at only, new ctid/xmin; any extra/unpublished row or increment fails. No serving, registry or historical publication mutation occurred. Source Blob transport is a disk synthetic fixture behind the real AzureBlobSourceStore verifier, not a live Azure claim; model source selections and initial hash-bound risk are explicit fixture setup.

## Remaining evidence boundaries

This PASS covers independent native guard/compatibility/rollback scope, not full CI or PG16. Root separately owns exact-head CI16, performance and broader review receipts. The codeowner's isolated genuine guard-omission mutant is a separate root-reviewed artifact; no claim here that this agent independently executed it. Old-version code acting on head-written data is now directly established, not inferred from read-only startup.
