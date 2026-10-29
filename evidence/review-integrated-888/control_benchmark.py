"""Opt-in native PG/ASGI comparison; see README.md for the evidence boundaries.

REVIEW_PROOF_OUTPUT=/tmp/proof.json python -m pytest -q -p tests.conftest \
    evidence/review-integrated-888/benchmark.py
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from time import perf_counter

from fastapi.testclient import TestClient
import pytest

from tests.semantic_fixture_support import bind_fixture_selections


CASES = {
    'small': (20, False, 1),
    'continued150': (150, True, 1),
    'continued600': (600, True, 1),
    'occupied_batch': (300, False, 1),
    'complex': (20, False, 1),
    'multiple': (20, False, 3),
}


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def durable(console, ids):
    store = console.workflow_document_store
    return deepcopy({
        'envelopes': [store.get_envelope(sid) for sid in ids],
        'objects': [store.list_document_objects(sid) for sid in ids],
        'bindings': console.workflow_review_store.read_bindings(ids),
        'events': console.workflow_review_store.read_events(),
        'commands': console.workflow_review_store.read_command_events(),
    })


@pytest.mark.parametrize('case', os.environ.get('REVIEW_PROOF_CASES', ','.join(CASES)).split(','))
def test_native_review_matrix(case, tmp_path, production_console, production_app, monkeypatch):
    import src.vorming.source_reconstruction_v1 as reconstruction
    from src.request_diagnostics_v1 import RequestDiagnostics
    from src.vorming.source_preparation_context_v1 import stored_extraction
    from src.vorming.semantic_passage_v1 import semantic_source_blocks
    import src.console_performance_v1 as performance
    import src.review.review_workboard_v1 as workboard

    assert Path(reconstruction.__file__).resolve().is_relative_to(Path.cwd().resolve()), \
        'pytest imported code from a different checkout; this measurement is invalid'

    repeats = int(os.environ.get('REVIEW_PROOF_REPEATS', '7'))
    assert repeats >= 1
    size, continued, documents = CASES[case]
    console = production_console(root=tmp_path, processing_binder=lambda _: None)
    author = console.create_account(username='author', password='fixture-only', roles=('researcher',))
    reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))
    outsider = console.create_account(username='outsider', password='fixture-only', roles=('reviewer',))
    monkeypatch.setattr(workboard, '_observed_at', lambda: '2026-10-28T09:00:00+00:00')
    # Suppress transport logging, retain original diagnostics and metric accounting.
    monkeypatch.setattr(performance._LOGGER, 'info', lambda *args, **kwargs: None)
    texts = [f'begrip {i:04d} is een beschrijving van een afzonderlijke waarneming' +
             ('' if continued else '.') for i in range(size)]
    source = ('<html><body><h1>Bronindeling</h1>' +
              ''.join(f'<p>{text}</p>' for text in texts) + '</body></html>').encode()
    if case == 'complex':
        source = ('<html><body><h1>Bronindeling</h1><h2>Waarneming</h2>' +
            ''.join(f'<p>{text}</p>' for text in texts[:10]) +
            '<h2>Meetgegevens</h2><table><tr><th>Meetpunt</th><th>Waarde</th></tr>'
            '<tr><td>Rust</td><td>20</td></tr></table>' +
            ''.join(f'<p>{text}</p>' for text in texts[10:]) + '</body></html>').encode()
    # A single complete selection in continuing text, one per paragraph otherwise.
    selections = [(' '.join(texts), 'definition')] if continued else [(s, 'definition') for s in texts]
    bind_fixture_selections(console, selections)
    ids, manifests = [], []
    for number in range(documents):
        sid = console.ingest(actor_id=author['account_id'], filename=f'source-{number}.html',
            content_type='text/html', data=source, ingest_kind='new', title=f'Proof document {number}',
            version='1.0', date='2026-10-28', live_url='', class_='richtlijn', family='fixture',
            named_reviewers=[reviewer['account_id']])['snapshot_id']
        ids.append(sid)
        envelope = console.workflow_document_store.get_envelope(sid)
        fragments = stored_extraction(envelope)
        blocks = semantic_source_blocks(fragments)
        rows = console.snapshot_objects(sid)
        candidates = [o for o in rows if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')]
        assert candidates
        assert not console.processing_status(sid)['formation_incomplete']
        manifests.append({'source_sha256': sha256(source).hexdigest(), 'source_bytes': len(source),
            'fragments': len(fragments), 'blocks': len(blocks), 'objects': len(rows),
            'candidates': len(candidates), 'bindings': len(console.workflow_review_store.read_bindings([sid])),
            'source_contract': envelope['prepared_source_extraction']['version'],
            'continued': continued})
    sid = ids[0]
    obj = next(o for o in console.snapshot_objects(sid)
               if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    routes = {
        'overview': {}, 'individual': {'document': sid, 'task': 'individual'},
        'inventory': {'document': sid, 'task': 'inventory'},
        'batch': {'document': sid, 'task': 'batch'},
        'passage': {'document': sid, 'object': obj['object_id']},
    }
    # Only aggregate values are retained: no cookies, actor IDs or request IDs.
    evidence = []
    def emit(_self, payload):
        if payload.get('event') == 'request_finished' and payload.get('route') == '/review':
            evidence.append({key: payload[key] for key in ('elapsed_ms', 'status', 'outcome', 'phases',
                'phase_tree', 'counters', 'db', 'unattributed_lower_bound_ms', 'phase_tree_truncated', 'error')
                if key in payload})
    monkeypatch.setattr(RequestDiagnostics, 'emit', emit)
    result = {'case': case, 'commit': git('rev-parse', 'HEAD'),
        'production_diff': git('diff', 'HEAD', '--', 'src'),
        'harness_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'reconstruction_sha256': sha256(Path(reconstruction.__file__).read_bytes()).hexdigest(),
        'python': platform.python_version(), 'postgres': '16', 'runtime': 'local authenticated ASGI + native PG',
        'deployment': None, 'provider': 'explicit deterministic fixture selections, real candidate creator',
        'configuration': {'web_concurrency': 1, 'stores': 'native disposable PostgreSQL',
            'source': 'local immutable HTML fixture', 'semantic_mode': 'semantic-source-bound-v1'},
        'lifecycle_projection': 'original production composition; no replacement',
        'documents': manifests, 'actor': 'named reviewer', 'repeats': repeats,
        'samples': [], 'concurrent_samples': []}
    app = production_app(console)
    with TestClient(app, base_url='https://testserver') as client:
        assert client.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'},
                           follow_redirects=False).status_code == 303
        for incomplete in (False, True):
            if incomplete:
                # Synthetic retained finding, explicitly not a genuine failed provider run.
                envelope = console.workflow_document_store.get_envelope(sid)
                replay = envelope['semantic_replay']['provider_evidence']
                replay['formation_incomplete'] = True
                replay['pending_rejections'] = [{'kind': 'formation',
                    'reason_code': 'synthetic_open', 'spans': []}]
                console.workflow_document_store.write_bundle(envelope=envelope)
                assert console.processing_status(sid)['formation_incomplete']
            before = durable(console, ids)
            for name, params in routes.items():
                for iteration in range(repeats + 1):
                    start = perf_counter()
                    page = client.get('/review', params=params)
                    elapsed = (perf_counter() - start) * 1000
                    assert page.status_code == 200
                    warning = 'data-formation-incomplete' in page.text
                    if name != 'overview':
                        assert warning == incomplete
                    batch_count = len(re.findall(r'name="object_ids" value="([^"]+)"', page.text))
                    if case == 'occupied_batch' and name == 'batch' and not incomplete:
                        assert batch_count == 20, 'benchmark must exercise the occupied 20-item batch page'
                    assert evidence
                    result['samples'].append({'route': name, 'incomplete': incomplete,
                        'temperature': 'first_for_route' if iteration == 0 else 'warm',
                        'wall_ms': elapsed, 'html_bytes': len(page.content),
                        'formation_warning': warning, 'batch_members': batch_count, **evidence.pop()})
            # Two requests share one session, but each retains its real read transaction.
            with ThreadPoolExecutor(max_workers=2) as pool:
                start = perf_counter()
                pages = list(pool.map(lambda _: client.get('/review', params=routes['passage']), range(2)))
                elapsed = (perf_counter() - start) * 1000
            assert all(p.status_code == 200 for p in pages)
            result['concurrent_samples'].append({'incomplete': incomplete, 'requests': 2,
                'wall_ms': elapsed, 'statuses': [p.status_code for p in pages],
                'html_bytes': [len(p.content) for p in pages], 'diagnostics': list(evidence)})
            evidence.clear()
            assert durable(console, ids) == before, 'Review GET mutated durable source/review state'
        # A reviewer not assigned to any document cannot see its passage.
        assert client.post('/login', data={'username': 'outsider', 'password': 'fixture-only'},
                           follow_redirects=False).status_code == 303
        denied = client.get('/review', params=routes['passage'], follow_redirects=False)
        assert denied.status_code in (303, 403, 404)
        result['unauthorized_status'] = denied.status_code
    output = Path(os.environ['REVIEW_PROOF_OUTPUT'])
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(output.read_text()) if output.exists() else []
    previous.append(result)
    output.write_text(json.dumps(previous, indent=2) + '\n')
