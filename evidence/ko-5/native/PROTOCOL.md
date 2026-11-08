# Independent KO5 native/rollback protocol

Environment: Codex shared host; Python `/workspace/.venvs/metis-ds/bin/python`; PostgreSQL 17, UTF8, loopback 127.0.0.1:55440. Not a PG16/CI or production claim. All PostgreSQL execution requests explicitly grant loopback network access. `scripts/test_postgres.sh` first passed on execution base.

Base: 07db5080666f0428a454f5a705e50825a4fc5506, `/workspace/Metis-ko5-base`.
Old KO4: c4db3bd84bfe722ab235eff67d2ccf69b60a785b, owned detached worktree `old-ko4`.
Target: await immutable owner head; no verification of moving worktree qualifies final evidence.

| Claim | Fault scenario | Observable proof | Boundary |
| --- | --- | --- | --- |
| Human KO commands enter central policy before durable writer | Public/base/MRO or repair command misses guard | Existing native policy-refusal test matrix; physical object/binding/events unchanged | Test-selected command routes |
| Policy test detects genuine omission | One actual command drops central guard | Isolated target archive; omission makes that command's refusal proof fail on missing expected refusal, no syntax/import failure | One planted omission |
| Prepared source keeps W1 | Resolution moved under lock/transaction or stale epoch commits | Prepared-source native suite and KO single-way preparing/depth assertions; stale-winner tests | Real source units, existing native fixture provider |
| Rollback reads head-written state | Required schema governance removed or boom duty lost | External rollback_probe.py seeds native ordinary review/publication plus high-risk boom successor; starts target/base/old-KO4 subprocesses against same still-existing database and root, compares full objects/bindings/KO states/readiness and old schema errors | Immutable Blob adapter uses disk synthetic transport, not Azure network |
| Startup has no new authority writes | Recovery invents review or rewrites publication/object history | Physical ctid/xmin and complete payload comparisons for object/binding/event/canonical/registry tables | Existing baseline reconcile changes exactly one published workflow.documents row: revision +1 and updated_at only; explicit assertion permits this observed preexisting effect |
| Restart/two workers/recovery preserve authority | Stale state reactivates or loses binding | Existing native KO lifecycle, D5 two-worker and recovery tests selected at exact target | PG17 shared host; owner separately must complete CI PG16 |

Baseline run outputs: baseline4/{head,base,ko4}.json and baseline4.log. It is a baseline qualification, not target acceptance. Owned database context manager drops each isolated metis_718_* database on success/failure; root server left running. Native seed produces a real boom node successor 1.0 to 1.0.1 through review_object after hash-bound high-risk fixture setup. Baseline old-image full views equal. Native risk fixture setup is not a claim about model risk inference.

Final execution (loopback permission required):
```
METIS_TEST_POSTGRES_DSN=postgresql://postgres@127.0.0.1:55440/postgres PYTHONPATH=EXACT_HEAD_CHECKOUT /workspace/.venvs/metis-ds/bin/python /workspace/ko5-native-evidence/rollback_probe.py --head EXACT_HEAD_CHECKOUT --base /workspace/Metis-ko5-base --ko4 /workspace/ko5-native-evidence/old-ko4 --output /workspace/ko5-native-evidence/final
```

No production, external comments, merge, or deployment. No edits to owner's worktree.
