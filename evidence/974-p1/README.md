# #974 P1 evidence: Vorming reads its source once

Trunk is `64c0f2d` (main `1f9deea` plus only the failing test). Head is `05ca116`.
Both ran on 2026-11-04 with Python 3.13 and a disposable PostgreSQL 16 from `tests/conftest.py`.
Every request went through the production ASGI app (`tests/production_support.py`).
`metis_diagnostic` events were read from the `metis.console.diagnostics` logger.

## Files

- `probe_p1.py` is the probe. It saves one receipt per lane or perf run.
- `run_p1.sh` runs it at trunk and head. Perf runs alternate trunk and head.
- `compare_p1.py` turns the receipts into `lanes.json` and `perf.json`.
- `microbench_hits.py` measures the cost of one build and of one cache hit.
- `receipts/` holds the raw receipts.

## Perf

Fixture: 2,000 HTML paragraphs and 200 materialised candidates.
Each run uses a fresh process and ingest. The probe opens `GET /source-selection?document=<sid>` twice and measures the second open.
There were 5 interleaved runs per side.

| | trunk median (min to max) | head median (min to max) |
|---|---|---|
| `source_reconstruction` inclusive ms | 1,569 (1,530 to 1,785) | 1,313 (1,070 to 1,413) |
| `elapsed_ms` | 3,379 (3,164 to 3,691) | 3,115 (2,714 to 3,702) |
| `source_input_compared` | 400 | 0 |
| `source_reconstruction_built` | 2 | 2 |
| `source_reconstruction` calls | 401 | 401 |

**The plan's perf rule fails on this fixture.** The rule asks for at most 1,000 ms and at most 10 percent of trunk. Head is 1,313 ms, which is 84 percent of trunk.

The limit is the two full reconstructions the plan allows (`source_reconstruction_built <= 2`). `microbench_hits.py` measured each one at 470 to 830 ms. Head removes the per-hit comparison completely: 400 comparisons become 0, and a hit now takes 0.003 to 0.006 ms.

On this HTML fixture the comparison was cheap on trunk: about 0.8 ms per hit, or about 0.3 s per request. The plan's baseline of 26 to 29 ms per read came from `prototype_source_reads.py`. That prototype averaged 20 calls and counted the first-call build in that average, so it did not measure the per-hit cost.

Rows shaped like a PDF extraction (numeric `bbox` and page fields) cost 10.6 to 13.9 ms per hit on trunk. That matches production's 27 ms per call more closely, and head brings it down to 0.006 ms.

So the production saving should be close to the full comparison cost (about 25 s for 945 calls). The two builds still cost about 1 to 1.3 s per 2,000 fragments, and P1 does not change them.

## Live lanes (`lanes.json`)

All 10 lanes are PASS. A control run compared trunk with trunk using the same comparison rules and also gave PASS on every lane, so the rules do not just record noise.

1. Regression. The 2,000-paragraph page is the same, with 100 problems. Head reports `source_reconstruction_built` 2 and `source_input_compared` 0.
2. Rejections. The document has formation rejections. The page and the sorted action hrefs are the same, with 2 problems. `/formation-problems` redirects to this page with 303 on both trunk and head.
3. Running. The status is 200, the progress line is present, and the 5 s refresh text is present.
4. Overview. No `source_reconstruction` phase runs.
5. Not named. The status is 400 with `reviewer_not_named_on_snapshot`, the same as trunk.
6. Decision tree (`decision-boom`). The page is the same and the status is 200.
7. Legacy document without a stored extraction. The page is the same and no error is recorded.
8. `task=disposition`. The page is the same.
9. Twice. Both opens report the same counters.
10. Concurrent. Two clients both get 200 with identical literal problem ids.

Problem ids hash the snapshot id, so they differ between two ingests, and the problem order differs with them. For that reason the trunk and head pages are compared with every id masked, as a sorted multiset of tag fragments, together with the sorted hrefs and the problem count. Literal problem ids are compared only within one process, in lane 10 and in `tests/test_formation_source_read_once.py`.
