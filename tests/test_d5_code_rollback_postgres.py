"""D5 code rollback on the same PG authority, stale disk copies and Blob bytes.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from tests.complete_workflow_support import complete_postgres  # noqa: F401
from tests.test_d5_pg_recovery_and_source_v1 import _scenario
from tests.test_pg_console_without_disk_mirrors import CONSOLES, MIRROR_NAMES, ROOT, _normalise
from tests.test_vsa_publish_readiness_ui_v1 import HTML_FIXTURE
from tests.test_workflow_chain_recovery_v1 import _install_schema
from src.review.review_ledger import unregister_backend

ROLLBACK = '629d63c5f2ba8781f7b2c1307e8011c6476b63e2'


@pytest.mark.parametrize('kind', CONSOLES)
def test_code_rollback_rebuilds_copies_and_preserves_pg_and_product_api(complete_postgres, tmp_path, monkeypatch, kind):
    root = tmp_path / 'runtime-root'
    checkout = tmp_path / 'rollback-checkout'
    checkout.mkdir()
    archive = subprocess.run(['git', 'archive', ROLLBACK], cwd=ROOT, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(checkout, filter='data')
    try:
        context, guard = _scenario(complete_postgres, root, monkeypatch, kind)
        console, accounts = context['console'], context['accounts']
        with guard.installed(monkeypatch):
            receipt = console.ingest(actor_id=accounts['researcher']['account_id'],
                filename='rollback-successor.html', data=HTML_FIXTURE.read_bytes() + b'<!-- rollback -->',
                content_type='text/html', ingest_kind='new_version',
                replaces_snapshot_id=context['successor']['snapshot_id'], title='Rollback successor',
                version='5.0', date='2026-09-16', live_url='https://example.test/d5',
                class_='richtlijn', family='d4', named_reviewers=[accounts['reviewer']['account_id']])
        before = context['adapter'].export_state()
        payload = tmp_path / 'input.json'
        payload.write_text(json.dumps(dict(root=str(root), kind=kind, accounts=accounts,
            snapshot_id=receipt['snapshot_id'],
            blobs={key: base64.b64encode(value).decode() for key, value in context['source'].blobs.items()})))
        outcomes = []
        for name, code in (('current', ROOT), ('rollback', checkout)):
            if name == 'rollback':
                _install_schema(complete_postgres.dsn)  # Fixture-owned empty target only.
                context['adapter'].restore_state(before)
                runtime = root / 'runtime'
                (runtime / 'objects').mkdir(exist_ok=True)
                (runtime / 'release_manifests').mkdir(exist_ok=True)
                for file in MIRROR_NAMES:
                    (runtime / file).write_text('{"stale":true}\n')
                for row in before['workflow_tables']['documents']:
                    (runtime / 'objects' / (row['snapshot_id'] + '.jsonl')).write_text('{"stale":true}\n')
                for row in before['tables']['publication_releases']:
                    (runtime / 'release_manifests' / (row['release_id'] + '.json')).write_text('{"stale":true}\n')
            data = json.loads(payload.read_text())
            data['legacy'] = name == 'rollback'
            payload.write_text(json.dumps(data))
            output = tmp_path / f'{name}.json'
            env = {**os.environ, 'PYTHONPATH': str(code)}
            result = subprocess.run([sys.executable, str(ROOT / 'tests/d5_rollback_support.py'), str(payload), str(output)],
                                    cwd=code, env=env, capture_output=True, text=True, timeout=90)
            assert result.returncode == 0, result.stderr[-5000:]
            outcome = _normalise(json.loads(output.read_text()), root)
            for row in outcome['state']['workflow_tables']['document_objects']:
                # WP6 updates retained rows; the pinned full-set writer deletes
                # and reinserts them, resetting this physical write counter.
                # Object versions/hashes, all audit evidence and every other
                # durable field remain in the exact comparison below.
                assert type(row['revision']) is int and row['revision'] >= 1
                row.pop('revision')
            outcomes.append(outcome)
        assert outcomes[0] == outcomes[1]
        assert not guard.rows
    finally:
        unregister_backend(root / 'runtime/review_ledger.jsonl')
