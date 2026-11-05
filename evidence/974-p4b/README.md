# #974 P4b evidence: the repair page reads its document and source once

Trunk is `4d7fb42` (the P4a head, PR #982). Head is `c16fbd4` on branch `ccr-fc816d1f-mljiu0-p4b`.
Both ran on 2026-11-05 with Python 3.13.18, FastAPI 0.128.2, Starlette 0.50.0 and a disposable
PostgreSQL 16.15 from `tests/conftest.py`. The fixture is synthetic; no production data was used.

Class B, `Rewrite risk: none`. No schema, authorization, lifecycle or integrity check changes.

## Mechanism

`GET` routes run inside `document_read_operation()`, the existing request-local read snapshot
(`src/console_read_operations_v1.py`). The snapshot keeps the envelope, objects and prepared review
source for one operation, and nothing crosses requests.

A revise decision on `POST /review` raises `StructuredRepairRequired`. Its exception handler renders
the repair page, and so does the error path of `POST /review/resolve`. Both run outside any
snapshot, so each reader on the page went to PostgreSQL again. On trunk, one render read the
envelope 9 times, the current objects 3 times and the prepared review source twice
(`tests/test_974_repair_render_reads_once.py`, red at `450871e`).

Inside a snapshot, two readers still deep-copied every current object to return one row:
`_current_object` (called twice per render) and `open_source_passage` (through
`source_fragment_catalog` and `_require_open_original`).

The three changes:

1. `4722d4d`: `render_repair` opens `document_read_operation()` itself. Every caller gets one
   snapshot for the render.
2. `1fceff0`: `_current_object` borrows `_read_current_objects`, the existing reader that
   `snapshot_objects` copies from, and copies only the matching row.
3. `c16fbd4`: `open_source_passage` does the same for the row whose passage it opens.

The source path is unchanged. `_read_source_fragments` returns the prepared source that P1 already
freezes, and `_read_source_blocks` already reuses its stored index (`source_reconstruction` 0 ms on
both sides).

## Files

- `probe_p4b.py`: the probe. It ingests one HTML guideline with 923 paragraphs (the production
  document's evidence-fragment count; 925 objects after formation). It sends each repair entry twice
  through the production ASGI app and measures the second request.
- `run_p4b.sh`: runs the probe at trunk and head, alternating trunk and head, one fresh process and
  ingest per run.
- `compare_p4b.py`: reduces the receipts to `perf.json`.
- `receipts/`: raw receipts, 5 per side.

Rerun: `PYTHON=<venv python> evidence/974-p4b/run_p4b.sh <trunk checkout> <head checkout> <out> 5`,
then `python evidence/974-p4b/compare_p4b.py <out> > perf.json`.

## Results (`perf.json`)

5 interleaved runs per side, median (min to max). `render` is the time inside `render_repair`.
Queries and JSON bytes come from the app's own psycopg instrumentation
(`src/console_performance_v1.py`). They were identical in every run of a side.

`POST /review` (revise, the path in the production stack dumps):

| | trunk | head |
|---|---|---|
| render ms | 3,052 (2,944 to 3,390) | 1,241 (1,035 to 1,364) |
| request ms | 3,894 (3,637 to 4,345) | 2,089 (1,899 to 2,198) |
| SQL statements in render | 36 | 10 |
| JSON bytes decoded in render | 71,828,744 | 18,988,421 |
| `read_review_source` in render | 2 | 1 |
| full object copies (`payload_copy`) | 3 | 0 |

`GET /source-selection?task=repair` (already inside a snapshot on trunk):

| | trunk | head |
|---|---|---|
| render ms | 1,513 (1,357 to 1,687) | 1,010 (961 to 1,338) |
| SQL statements in render | 11 | 11 |
| JSON bytes decoded in render | 18,988,421 | 18,988,421 |
| full object copies (`payload_copy`) | 3 | 0 |

Store-level reads in one render on head, both routes (asserted by the test):
`get_envelope` 1, `list_document_objects` 1 (the object histories, for the snapshot revision),
`current_document_objects` 1, `read_review_source` 1.

### What the numbers measure

- **Where trunk's time went (POST render).** Median phase times: `objects_read` 1,792 ms (973 ms of
  it full copies), the second prepared-source read, and `document_load` 353 ms for 9 envelope
  reads. On head: `objects_read` 472 ms, `document_load` 75 ms, one source read.
- **Why head is not faster still.** One render needs one prepared-source read: ~350 ms to fetch and
  decode 19 MB of JSON and to hydrate and validate the views. `objects_read` (~310 to 470 ms)
  still fetches the histories and the current objects, and `snapshot_objects_and_revision` still
  makes one deep copy of all current rows for the page's own `objects`. The rest is building the
  1,846 source-unit options. A profiled run (not reported as timing) showed `deepcopy` and the
  prepared-source read as the largest remaining items.
- **The rest of the POST request is outside the render** and unchanged. It is about 850 ms: the
  revise preflight's store transaction (~310 ms) and its own prepared-source read (~400 ms). It makes
  24 of the 34 statements.
- **Work happened, and nothing errored.** Every measured response was 200 and contained the repair
  form with 1,846 source-unit options on both sides. The JSON-byte totals show that the source and
  objects were read in full once on head.
- **Noise.** Each probe process ingests its own document, and other sessions shared the 4-core host
  (load average 1.3 to 2.4). The trunk and head ranges do not overlap on either route.
- **Scale.** The production dump showed more than 30 s for a 923-fragment PDF. This HTML fixture
  shows the repeated reads, not that absolute time. PDF-shaped rows (numeric `bbox`, pages) are
  larger per fragment (see `evidence/974-p1/README.md`), so each repeated envelope, object or
  source read costs more there. The ratio that carries over is the reduction in reads and bytes
  per render: 36 to 10 statements and 3.8 times fewer JSON bytes.

## HTML is byte-identical

- **Same database.** `test_repair_page_html_is_unchanged_by_the_read_snapshot` renders the revise page
  twice on the same document, once normally and once with `document_read_operation` replaced by a
  no-op, so every read goes to PostgreSQL as on trunk. The two responses are byte-identical.
- **Trunk vs head.** Each run ingests its own document, so ids differ. The probe renames every id
  canonically in order of appearance (`normalized` in `probe_p4b.py`) and hashes the page. All 10
  trunk and head pages per route have the same hash (`page_identical`: true for both routes).

## Tests and checks

- `tests/test_974_repair_render_reads_once.py`: red at `450871e` (POST render: envelope 9,
  current objects 3, review source 2). Green at `4722d4d` and at the head. It also pins:
  - `_current_object` stays a detached copy inside a snapshot. With the copy removed, that test fails.
  - Stale: after a repair is saved, the next render shows the new passage and the new snapshot
    revision. With a render snapshot kept across requests, that test fails.
  - Concurrent: two simultaneous revise renders return identical pages, and each makes its own
    reads (exactly twice the single-render counts).
- Repair, event-loop, disposition, bounded-command, closed-review, open-original and console tests
  touching the changed modules: 814 passed, 12 skipped. All 12 skips are the real-Docling
  acceptance tests (`tests/test_docling_real_pdf.py`). No PostgreSQL test was skipped.
