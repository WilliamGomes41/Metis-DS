"""Opt-in WP5 scale workload extended with all GET routes and redirect timing.

Run from the checkout being measured, with -p tests.conftest. Only synthetic
disposable PostgreSQL databases are prepared. No production inputs or runtime.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import runpy

import pytest


@pytest.mark.parametrize('size', [32, 128])
def test_native_integrated_review(size, tmp_path, production_console, production_app, monkeypatch):
    root = Path(__file__).resolve().parent
    harness = root / 'benchmark.py'
    namespace = runpy.run_path(str(harness))
    mode = os.environ.get('REVIEW_PROOF_CARD_MODE', 'legacy')
    assert mode in {'legacy', 'compact'}
    monkeypatch.setenv('CONSOLE_REVIEW_CARD_READS', mode)
    namespace['test_native_task_v1_review'](
        tmp_path, production_console, production_app, monkeypatch, False,
        size=size, history_depth=2, integrated=True)
    output = Path(os.environ['REVIEW_PROOF_OUTPUT'])
    rows = json.loads(output.read_text())
    rows[-1]['integrated_driver_sha256'] = sha256(Path(__file__).read_bytes()).hexdigest()
    output.write_text(json.dumps(rows, indent=2) + '\n')
