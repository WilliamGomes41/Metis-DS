"""Cost of one diagnostic_json_bytes call inside a diagnosed request, three phases deep.

    PYTHONPATH=. python evidence/974-p2/microbench_attribution.py

Isolates the per-load overhead the JSON loader gains; the HTTP probe is too noisy for 2 %.
"""
import json
import timeit

from src.request_diagnostics_v1 import _CURRENT, RequestEvidence, diagnostic_json_bytes, diagnostic_phase

evidence = RequestEvidence("0" * 32, "/review", lambda payload: None)
token = _CURRENT.set(evidence)
try:
    with diagnostic_phase("review_render"), diagnostic_phase("source_views_read_records"), \
            diagnostic_phase("db_fetch"):
        runs = [timeit.timeit(lambda: diagnostic_json_bytes(120), number=200_000) / 200_000 for _ in range(7)]
        baseline = [timeit.timeit(lambda: None, number=200_000) / 200_000 for _ in range(7)]
finally:
    _CURRENT.reset(token)
per_call_ns = (sorted(runs)[3] - sorted(baseline)[3]) * 1e9
print(json.dumps({"per_call_ns_median_of_7": round(per_call_ns, 1),
                  "attributed": evidence.json_bytes,
                  "ms_per_100k_loads": round(per_call_ns * 100_000 / 1e6, 2)}))
