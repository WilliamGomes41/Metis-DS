"""Reproduce the synthetic 300-candidate authenticated Review GET measurement.

Run from repository root with dependencies and PostgreSQL 16 available:
REVIEW_BENCHMARK_OUTPUT=work/review-benchmark.json python -m pytest -q \
    -p tests.conftest evidence/review-document-read-performance/benchmark.py

The sectionless source makes the batch queue empty; its timing measures queue
classification overhead, not a fully populated batch screen. Real batch paging
and stale recovery are covered in test_review_document_read_performance.py.
"""
import json
import os
from pathlib import Path
from time import perf_counter
import pytest
from tests.test_review_render_source_reuse import review_client


@pytest.mark.parametrize('review_client', [300], indirect=True)
def test_document_benchmark(review_client):
    console, client, sid = review_client
    measurements = {}
    for task in ('individual', 'inventory', 'batch'):
        rows = []
        for _ in range(3):
            start = perf_counter()
            response = client.get('/review', params={'document': sid, 'task': task})
            elapsed = perf_counter() - start
            assert response.status_code == 200
            rows.append({'seconds': elapsed, 'html_bytes': len(response.content)})
        measurements[task] = rows
    Path(os.environ['REVIEW_BENCHMARK_OUTPUT']).write_text(json.dumps(measurements, indent=2))
