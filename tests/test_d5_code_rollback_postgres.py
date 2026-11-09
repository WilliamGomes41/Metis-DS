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
            raw = json.loads(output.read_text())
            prior_events = {row['event_id']: row for row in before['workflow_tables']['review_events']}
            actual_events = {row['event_id']: row for row in raw['state']['workflow_tables']['review_events']}
            assert prior_events.keys() <= actual_events.keys()
            for event_id, event in prior_events.items():
                assert actual_events[event_id] == event
            new_approvals = [row for event_id, row in actual_events.items()
                             if event_id not in prior_events and row['event_type'] == 'clinical_review_approve']
            assert new_approvals
            decision_evidence = {
                'assessment': {'version': 'review-assessment-v1', 'applicable': 'yes',
                               'complete': 'yes', 'placed_correctly': 'yes'},
                'supporting_evidence': {'version': 'ko-supporting-evidence-v1', 'applicability': 'not_applicable'},
            }
            for event in new_approvals:
                assert event['snapshot_id'] == receipt['snapshot_id']
                for details in (event['details'], event['event_payload']['details']):
                    if name == 'current':
                        assert all(details[key] == value for key, value in decision_evidence.items())
                    else:
                        assert not decision_evidence.keys() & details.keys()
            # KO-5 stops the obsolete envelope tick; the pinned image still
            # writes it for this one approval. Validate both behaviors before
            # comparing all remaining durable/product state exactly.
            prior_envelope = next(row['envelope_payload'] for row in before['workflow_tables']['documents']
                                  if row['snapshot_id'] == receipt['snapshot_id'])
            actual_envelope = next(row['envelope_payload'] for row in raw['state']['workflow_tables']['documents']
                                   if row['snapshot_id'] == receipt['snapshot_id'])
            assert prior_envelope.get('review_passes', {}) == {}
            if name == 'current':
                assert ('review_passes' in actual_envelope) == ('review_passes' in prior_envelope)
                assert actual_envelope.get('review_passes') == prior_envelope.get('review_passes')
            else:
                from datetime import datetime
                assert len(new_approvals) == 1
                expected_actor = accounts['reviewer']['account_id']
                assert new_approvals[0]['details']['reviewer_id'] == expected_actor
                passes = actual_envelope['review_passes']
                assert set(passes) == {expected_actor}
                tick = passes[expected_actor]
                assert set(tick) == {'at', 'passed', 'object_id'}
                assert tick['passed'] is True
                assert tick['object_id'] == new_approvals[0]['object_id']
                assert isinstance(tick['at'], str) and tick['at']
                assert datetime.fromisoformat(tick['at'].replace('Z', '+00:00')).tzinfo is not None
            outcome = _normalise(raw, root)
            compared_envelope = next(row['envelope_payload'] for row in outcome['state']['workflow_tables']['documents']
                                     if row['snapshot_id'] == receipt['snapshot_id'])
            if name == 'rollback':
                if 'review_passes' in prior_envelope:
                    compared_envelope['review_passes'] = prior_envelope['review_passes']
                else:
                    compared_envelope.pop('review_passes')
            if name == 'current':
                new_approval_ids = {row['event_id'] for row in new_approvals}
                for event in outcome['state']['workflow_tables']['review_events']:
                    if event['event_id'] in new_approval_ids:
                        for details in (event['details'], event['event_payload']['details']):
                            for key in decision_evidence:
                                details.pop(key)
            # This is a rollback proof for legacy, unpinned documents. Format 8
            # adds formation/source backup records that the pinned binary
            # cannot export. Compare the common durable/product state exactly;
            # never interpret this legacy scenario as a rollback of proof-v3.
            state = outcome['state']
            if name == 'current':
                assert state.pop('workflow_recovery_version') == 14
                # This old-binary comparison covers pre-deletion work only.
                # Never discard nonempty deletion history to manufacture parity.
                assert state['workflow_tables'].pop('test_document_deletions') == []
                assert state['workflow_tables'].pop('deleted_test_snapshots') == []
                assert all(not row['envelope_payload'].get('prose_transitions')
                           for row in raw['state']['workflow_tables']['documents'])
                # v12 now exports the complete existing decision payload. The
                # pinned v7 binary cannot export this column. Validate it
                # independently before comparing their common projection.
                from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
                previous_payloads = {r['authorization_id']: r['authorization_payload']
                                     for r in before['workflow_tables']['publish_authorizations']}
                for row in raw['state']['workflow_tables']['publish_authorizations']:
                    binding_payload = row['authorization_payload']
                    assert PostgresWorkflowReviewStore._binding_projection(binding_payload) == PostgresWorkflowReviewStore._binding_projection(row)
                    if row['authorization_id'] in previous_payloads:
                        assert binding_payload == previous_payloads[row['authorization_id']]
                    else:
                        assert all(binding_payload[key] == value for key, value in decision_evidence.items())
                for row in state['workflow_tables']['publish_authorizations']:
                    row.pop('authorization_payload')
                formation = state.pop('formation_recovery')
                assert formation['version'] == 5
                for table in ('annotation_sets','annotation_versions','annotation_heads','annotation_commands',
                              'annotation_seals','annotation_build_commands'):
                    assert formation['tables'][table] == []  # Legacy work is never silently taken over.
                assert not formation['tables']['formation_evidence_roots']
                assert all(d['formation_evidence_id'] is None for d in formation['documents'])
            else:
                assert state.pop('workflow_recovery_version') == 7
                assert 'formation_recovery' not in state
            for row in outcome['state']['workflow_tables']['document_objects']:
                # WP6 updates retained rows; the pinned full-set writer deletes
                # and reinserts them, resetting this physical write counter.
                # Object versions/hashes, existing audit evidence and every other
                # durable field remain in the exact comparison below.
                assert type(row['revision']) is int and row['revision'] >= 1
                row.pop('revision')
            outcomes.append(outcome)
        assert outcomes[0] == outcomes[1]
        assert not guard.rows
    finally:
        unregister_backend(root / 'runtime/review_ledger.jsonl')
