"""Explicit same-fixture comparison of the pre-project and current landing.

WORKPLACE_COMPARISON_OUTPUT=/tmp/comparison.json python -m pytest -q \
  -p tests.conftest evidence/863/read_write_comparison.py

Historical presentation source runs above the SAME current PG/backend fixture.
This isolates renderer access changes; it is not a historical deployment benchmark.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import types

from src.console_performance_v1 import performance_scope
from src import review_workboard_v1 as current
from tests.personal_review_fixture_support import bind, prepare, snapshot

BASE = 'efed882c8f2bef850ea2aff47d744214b83131c8'
ROOT = Path(__file__).resolve().parents[2]


def historical_module(name, path):
    source = subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT, text=True)
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        exec(compile(source, f'{BASE}:{path}', 'exec'), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def test_same_fixture_landing_reads_and_writes(tmp_path, production_console, monkeypatch):
    console = production_console(root=tmp_path, processing_binder=bind)
    actors, docs = prepare(console)
    before = deepcopy(snapshot(console, docs))
    old_ui = historical_module('historical_ui_863', 'src/operations_console_app.py')
    old_board = historical_module('historical_board_863', 'src/review_workboard_v1.py')
    old_board.console_ui = old_ui
    reads = [('summaries', console, 'review_workboard_summaries'),
             ('enrich', console, '_enrich_review_workboard_summaries'),
             ('objects_batch', console.workflow_document_store, 'list_current_objects_batch'),
             ('bindings', console.workflow_review_store, 'read_bindings'),
             ('source_fragments', console, 'review_source_fragments'),
             ('events', console.workflow_review_store, 'read_events_for_snapshots'),
             ('accounts', console, 'list_accounts'),
             ('deep_objects', console, 'snapshot_objects')]
    writes = [('command_commit', console, '_commit_prepared_store'),
              ('object_bundle', console.workflow_document_store, 'write_bundle'),
              ('bindings_write', console.workflow_review_store, 'replace_snapshot_bindings')]
    results = {}
    try:
        for label, renderer in [('baseline', old_board._workboard_page), ('current', current._workboard_page)]:
            calls = Counter()
            def counted(key, original):
                def call(*args, **kwargs):
                    calls[key] += 1
                    return original(*args, **kwargs)
                return call
            with monkeypatch.context() as patch:
                for key, owner, method in [*reads, *writes]:
                    patch.setattr(owner, method, counted(key, getattr(owner, method)))
                with performance_scope() as measured, console.document_read_operation():
                    html = renderer(console, account=actors['a'])
            assert all(doc['snapshot_id'] in html for doc in docs.values())
            assert all(calls[key] == 0 for key, _, _ in writes), calls
            assert snapshot(console, docs) == before
            results[label] = {'calls': dict(sorted(calls.items())),
                'db': {k: v for k, v in asdict(measured).items() if k in {'connections', 'queries', 'json_bytes'}}}
        assert results['current']['calls'].get('deep_objects', 0) == 0
        for key, _, _ in reads:
            assert results['current']['calls'].get(key, 0) <= results['baseline']['calls'].get(key, 0), (key, results)
        assert results['current']['db']['queries'] <= results['baseline']['db']['queries'], results
        report = {'baseline': BASE, 'evaluated_revision': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'fixture': 'personal_review_fixture_support.prepare: five documents, actor A',
            'comparison_boundary': 'historical Python presentation above identical current native backend',
            'measurements': results, 'durable_state_unchanged': True}
        Path(os.environ['WORKPLACE_COMPARISON_OUTPUT']).write_text(json.dumps(report, indent=2) + '\n')
    finally:
        sys.modules.pop('historical_ui_863', None)
        sys.modules.pop('historical_board_863', None)
