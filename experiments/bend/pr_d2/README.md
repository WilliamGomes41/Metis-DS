# PR-D2: retired standalone second-review CLI (#775)

Change class: C. Rewrite risk: none. No active review semantics, domain state,
schema, publication authority, or runtime implementation is replaced.

## 1. Specify the change

Remove the blocked standalone JSONL second-review module and its three
historical tests. Preserve the existing console command, four-eyes checks,
review evidence and historical T11 reader map. External operator usage of
`python -m` cannot be established from repository searches; the removal is
explicitly requested by the owner, with no replacement CLI alias.

## 2. State the bounded laws

`PendingSecond.bend` models **actionability** for a pending default four-eyes
duty with exactly one exact-current approver. All other prerequisites are
assumed satisfied. It has two routes (retired standalone, existing console)
and a boolean recording whether the actor differs from the current approver.

`LAWS.bend` states:

- The retired standalone route is never actionable.
- The same reviewer cannot act on this pending second-review duty.
- The console route remains actionable for an independent reviewer.

These laws do not assert that every independent actor is authorized. They do
not cover configured/managed policies, completed-review idempotency, account
roles, source resolution, exact snapshot/hash verification, transactions,
publication, or arbitrary Python behavior. The existing runtime owns those.

## 3. Implement and prove

The implementation change deletes the legacy Python entrypoint. The Bend
file is a test-only reference model, not a second runtime authority.
`PROOF.bend` proves the three laws by reduction and route case analysis.
This tiny model has no useful parallel workload; it adds no concurrency.

```sh
bend guide
cd experiments/bend/pr_d2
bend PROOF.bend
bend PROOF.bend --verdict
```

The last command needs Lean v4.34.0. On Linux x86_64, use the pinned
`install-lean.sh` and add `$HOME/.local/share/metis-lean-4.34.0/bin` to PATH.
Its SHA-256 is the upstream GitHub release asset digest, checked on 2026-10-20.
This downloads about 580 MB; it is proof tooling only and is not automatically
installed in the production or offline security-runner containers.

## 4. Check the connection to Python

`tests/test_pr_d2_second_review_retirement.py` verifies that importing/running
the removed module fails without writing output, and that no active caller
remains. For all four model inputs it compares executable Bend output with
module absence or the **existing** `reviewer_route_for` projection, using the
same exact-current, pending four-eyes fixture as D5.3a.

Two temporary incorrect Bend implementations must fail the laws: restoring
standalone actionability, and allowing the same reviewer on the console route.
The laws themselves are unchanged. This is executable conformance evidence
for the finite abstraction, not a verified translation of the Python program.
BendTT rechecks proofs; Bend's translation into its kernel is not itself proven.

## 5. Check the actual console and the whole repository

From the repository root, with Bend and Lean on PATH:

```sh
METIS_BEND_VERDICT=1 python -m pytest -q tests/test_pr_d2_second_review_retirement.py
python -m pytest -q 'tests/characterization/test_review_room.py::test_review_room_golden[second_same_reviewer]' tests/test_d5_3a_binding_aware_review_duty.py
python -m pytest -q
```

The dedicated Bend workflow runs the proof, semantic negative controls,
conformance tests and existing console tests. It runs for relevant source,
script, workflow, packaging and test changes. Normal Metis CI remains in place.
The optional Bend tests may skip outside that dedicated workflow; the workflow
requires the tool explicitly and sets `METIS_BEND_VERDICT=1`.

## 6. Review

Review the deletion, unchanged runtime rules and evidence together. A passing
Bend proof does not replace the console/Python tests or establish production
correctness. The PR is not merged automatically; no deployment is included.

## Executed evidence (2026-10-20)

- Standard Bend proof: passed. Both semantic mutations were rejected.
- [Independent BendTT and console job](https://github.com/WilliamGomes41/Metis-DS/actions/runs/39387754742): passed; Lean 4.34.0, Bend 2.0.37, 19 tests passed with no skips. This job also rechecked the proof with `--verdict`.
- Local focused regression run: 92 passed, 1 skipped. Architecture invariants: 6 passed. Repository, release-control, dependency-boundary, JSON/YAML and shell syntax checks passed.
- Local full suite: **5 failed, 5048 passed, 586 skipped, 6 xfailed**, with 3 subtests passed. All five failing tests were also reproduced on unchanged main `08afdb0`; one requires the unavailable `psql` executable, and four are existing transport/SSRF test failures. They were not weakened or fixed in this deletion PR. A successful full suite is not claimed.
- The historical T11 reader map is byte-for-byte unchanged. The only `src/` change is deleting the legacy module.
- The retirement guard was also run against unchanged main: it correctly failed because the old CLI was still importable.

The local Lean executable cannot locate its application in this restricted
execution environment; the independent kernel result above was obtained on
the GitHub runner. The normal Python/PostgreSQL CI is separate and its result
must be assessed before merge. The proof/implementation/test files checked by
that successful Bend job are unchanged by this evidence/documentation update.
