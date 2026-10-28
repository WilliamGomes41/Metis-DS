# Review source reconstruction — #886

Change class: B
Promise: Continued fragments reconstruct with the same source representation without repeatedly copying or rescanning a growing prefix.
Proof: Full-output baseline comparison, input/alias isolation, boundary mutation, bounded-work checks and matched PostgreSQL route measurements.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing owner and change

The existing `reconstruct_source_fragments` feeds `_reconstructed_blocks`,
`prepare`, materialisation, and review readers. The original inputs remain
unchanged. A private, operation-local accumulator holds text pieces, lengths,
source IDs and mappings only after an existing joined block becomes long and
unambiguously non-boundary. It materializes the block once when closed. Short
or ambiguous cases continue through the existing predicates and join. A long
original heading is compared incrementally so an exact later heading remains a
boundary. No source contract version, identity, source hash, authorization,
publication, storage, lifecycle or cache lifetime changes.

Context: extracted fragments and their source locators belong to the existing
source owner; a reconstructed block and its offsets exist only for the current
calculation; prepared views remain bound to their existing input hash and
contract. Review decisions and permissions remain current-domain decisions.
No durable state or transaction boundary is introduced. Code revert is the
rollback; no data migration is needed.

## Reproduction and proof boundaries

On main `49e50be279925b7e87d4ffa551609b998cac5869`, the existing source
benchmark with 150/600 continued fragments and three repetitions returned
median 0.507/7.311 s, exceeding the predeclared 6x budget. With the changed
source file SHA-256 `0b5a65455228109b6b054db5ecba30f448aa3d87f8a9cfcc4e5029651fdecd70`,
it returned 0.041/0.160 s and passed. Those synthetic samples are in
`evidence/review-reconstruction-886/source-{baseline,after}.json`.

The same cProfile workload (100/300 fragments, one repetition) showed 398
calls to `_join` and 2.336 cumulative seconds in `deepcopy` on the original;
the changed version made 16 `_join` calls and used 0.042 cumulative seconds in
`deepcopy`. Profile overhead and local machine load limit timing comparisons;
the deterministic work-volume test also bounds processed text and copied span
work separately, including a large initial text.

`tests/test_source_reconstruction_parity_886.py` compares complete results on
62 fixed synthetic cases with the unoptimized output, checks independently
readable text/offset examples, input isolation, long heading boundaries, and
work-volume growth. The generated baseline is a characterization oracle, not
independent proof that every old decision is correct. An additional 160 seeded
long cases were differentially checked against the main version, including
mutable alias relationships and long heading matches. A one-character offset
error in an isolated temporary copy caused the full-output comparison to fail
on the intended long fixture; no mutation is retained.

The reproducible route fixture and five-sample results per route are in
`evidence/review-reconstruction-886/route_matrix.py` and its `baseline/` and
`after/` directories. It uses disposable PostgreSQL, an authenticated ASGI
client, synthetic complete/incomplete formation, 300 closed candidates,
multiple documents and 150 continued fragments. It uses the existing fixture's
stubbed lifecycle-status projection and synthetic formation/provider behavior;
it is not a production or completely unmocked end-to-end benchmark. For the
continued fixture, document medians were 0.424/0.066 s, overview 0.665/0.258 s,
passage 0.416/0.073 s. The 300-candidate closed and two-document controls did
not regress in this repeated run. Five samples do not support a p95 claim.

The actual production document, current runtime and deployment are unmeasured.
WP3 and WP4 retain their own acceptance criteria; this result alone does not
prove the total production delay is solved.

## Rollback-test compatibility discovered during verification

The first complete-suite attempt stopped after 2,283 passes because the D5
rollback helper imported `src.review.review_ledger` in its intentionally pinned
pre-room checkout, which still has `src.review_ledger`. The same test failed
with the same missing module on unmodified main `49e50be`. The helper now uses
the scenario's explicit `legacy` flag to select the two known old module paths;
it does not catch import errors or weaken rollback assertions. Both durable and
Azure-simulated rollback scenarios passed on disposable PostgreSQL after this
test-only compatibility repair. The interrupted suite is not completion proof.
