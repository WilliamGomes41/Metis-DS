"""Frozen output of the pre-042 annotation writer (f33ea688^), using synthetic text.

# release-control-evidence: scope/belofte — historical heads open and retain their identity.
# release-control-evidence: slop — the existing save and seal paths enforce the decisions.
# release-control-evidence: releasebewijs — 035 to 042, restart, browser-facing API and build.
"""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from src.integrity_kernel import stable_hash
from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_preview_v1 as preview
from src.vorming import human_annotation_v1 as annotations
from tests.production_support import restart_production
from tests.test_human_annotation_postgres import command, source
from tests.test_t7_creator_cut import _fragment


ROOT = Path(__file__).resolve().parents[1]
OLD = json.loads((ROOT / 'tests/fixtures/annotation-history/pre-042.json').read_text())


@pytest.mark.parametrize('name', OLD)
def test_old_writer_output_opens_but_cannot_authorize_a_build(name):
    fragments = [_fragment('core', 'De huid is droog.'), _fragment('condition', 'Alleen bij jeuk.')]
    entry = deepcopy(OLD[name])
    result = preview.inspect_for_overview([entry], fragments=fragments)
    code = 'annotation_historical_read_only' if name in {'essential','withdrawal'} else 'annotation_historical_format'
    assert result['findings'] == [{'annotation_id': entry['annotation_id'], 'code': code}]
    assert result['unaccounted_ranges'] == []
    assert entry == OLD[name]
    with pytest.raises(ConsoleError):
        preview.inspect_document([entry], fragments=fragments)


@pytest.mark.parametrize('corruption', ['hash', 'witness', 'unexpected_field'])
def test_old_marker_never_masks_invalid_input(corruption):
    entry = deepcopy(OLD['essential'])
    if corruption == 'hash':
        entry['payload_hash'] = 'invalid'
    else:
        if corruption == 'witness':
            entry['payload']['ranges'][0]['quote_sha256'] = 'invalid'
        else:
            entry['payload']['unexpected'] = True
        entry['payload_hash'] = stable_hash(entry['payload'])
    fragments = [_fragment('core', 'De huid is droog.'), _fragment('condition', 'Alleen bij jeuk.')]
    with pytest.raises(ValueError, match='annotation_integrity_failed|annotation_selection_invalid'):
        preview.inspect_for_overview([entry], fragments=fragments)


@pytest.mark.parametrize('change', ['foreign_id', 'extra_field', 'duplicate', 'function'])
def test_invalid_historical_decision_is_rejected_even_with_matching_hash(change):
    entry = deepcopy(OLD['withdrawal'])
    links = entry['payload']['required_links']
    if change == 'foreign_id':
        links[0]['relationship_id'] = links[0]['relationship_id'].replace(entry['annotation_id'], str(uuid4()))
    elif change == 'extra_field':
        links[0]['unknown'] = True
    elif change == 'duplicate':
        links.append(deepcopy(links[0]))
    else:
        links[0]['evidence_function'] = 'explains'
    entry['payload_hash'] = stable_hash(entry['payload'])
    fragments = [_fragment('core', 'De huid is droog.'), _fragment('condition', 'Alleen bij jeuk.')]
    with pytest.raises(ConsoleError, match='annotation_integrity_failed|annotation_relationship_invalid|annotation_relationship_duplicate'):
        preview.inspect_for_overview([entry], fragments=fragments)


@pytest.mark.parametrize('name', ['empty_v2', 'withdrawn'])
def test_upgrade_reopens_mixed_overview_and_protects_saved_head(tmp_path, production_console, production_app, monkeypatch, name):
    console, actor, _, sid, view, _ = source(production_console, tmp_path)
    entry = OLD[name]
    request = command(view)
    request['annotation_id'] = entry['annotation_id']
    request['selection']['status'] = entry['payload']['status']

    def install_migration(name):
        with console.workflow_document_store._connect() as conn:
            conn.execute((ROOT / 'db/migrations' / name).read_text())

    install_migration('035_annotation_meaning_input.sql')
    with monkeypatch.context() as old_writer:
        old_writer.setattr(annotations, '_validate', lambda selection, blocks: deepcopy(entry['payload']))
        annotations.save(console, actor_id=actor, **request)
    install_migration('042_retire_essential_relationships.sql')
    console = restart_production(console)
    current = {**command(view), 'expected_generation': 1}
    annotations.save(console, actor_id=actor, **current)
    with TestClient(production_app(console), base_url='https://testserver') as client:
        assert client.post('/login', data={'username':'annotator','password':'annotation-secret'}, follow_redirects=False).status_code == 303
        page = client.get('/annotations', params={'document':sid, 'overview':'true'})
        assert page.status_code == 200
        assert 'Eerdere annotatieversie' in page.text
        assert 'Selectie controleren en opslaan' in page.text
        assert 'id="historisch-'+entry['annotation_id']+'"' in page.text
        assert 'action="/annotations/finalize"' not in page.text
        assert 'action="/annotations/source-role"' not in page.text
        assert current['annotation_id'] in page.text
        changed = dict(request, command_id=str(uuid4()), expected_revision=1, expected_generation=2)
        saved = client.post('/annotations/api', json=changed)
        assert saved.status_code == 409
        assert saved.json()['error'] == 'annotation_client_contract_stale'
    state = build.overview(console, actor_id=actor, snapshot_id=sid)
    with pytest.raises(ConsoleError, match='annotation_document_incomplete'):
        build.finalize(console, actor_id=actor, snapshot_id=sid, command_id=str(uuid4()),
                       overview_hash=state['overview_hash'], expected_generation=2, expected_revision=state['objects_revision'])
    with console.workflow_document_store._connect() as con:
        actual = con.execute('SELECT revision,payload,payload_hash FROM workflow.annotation_versions '
            'WHERE snapshot_id=%s AND annotation_id=%s', (sid,entry['annotation_id'])).fetchall()
        assert actual == [{k:entry[k] for k in ('revision','payload','payload_hash')}]
        assert con.execute('SELECT count(*) AS n FROM workflow.annotation_seals WHERE snapshot_id=%s', (sid,)).fetchone()['n'] == 0

    # A current, explicitly v2-capable correction becomes a normal successor.
    changed['selection'].update(object_type=None, disposition={'role':None,'reason':None})
    receipt = annotations.save(console, actor_id=actor, **changed)
    assert receipt['revision'] == 2 and receipt['status'] == entry['payload']['status']
    with pytest.raises(ConsoleError, match='annotation_write_conflict'):
        annotations.save(console, actor_id=actor, **dict(changed, command_id=str(uuid4())))
    assert annotations.save(console, actor_id=actor, **changed) == receipt
    next_state = build.overview(restart_production(console), actor_id=actor, snapshot_id=sid)
    assert 'annotation_historical_format' not in [f['code'] for f in next_state['inspection']['findings']]


def upgraded_ready_document(production_console, tmp_path, monkeypatch, essential):
    from tests.test_human_annotation_build_postgres import saved_source

    save = annotations.save
    validate = annotations._validate

    def old_save(console, **args):
        with console.workflow_document_store._connect() as con:
            con.execute((ROOT / 'db/migrations/035_annotation_meaning_input.sql').read_text())

        def old_validate(selection, blocks):
            payload = validate(selection, blocks)
            if 'field_evidence' in selection:
                payload['required_links'] = []
                for anchor in payload['ranges']:
                    anchor['required_for_meaning'] = essential is True and anchor['role'] == 'condition'
                    if essential == 'withdrawal' and anchor['role'] == 'condition':
                        payload['required_links'].append({
                            'relationship_id':annotations.relationship_id(args['annotation_id'], anchor),
                            'role':'condition', 'required_for_meaning':False, 'evidence_function':None,
                            'withdrawal_reason':'Controle <eerder> vastgelegd.'})
            return payload

        with monkeypatch.context() as patch:
            patch.setattr(annotations, '_validate', old_validate)
            return save(console, **args)

    with monkeypatch.context() as patch:
        patch.setattr(annotations, 'save', old_save)
        console, actor, sid, request = saved_source(production_console, tmp_path, context_function='supported_by')
    with console.workflow_document_store._connect() as con:
        con.execute((ROOT / 'db/migrations/042_retire_essential_relationships.sql').read_text())
    return restart_production(console), actor, sid, request


@pytest.mark.parametrize('essential', [False, True, 'withdrawal'])
def test_ready_annotation_across_042_uses_original_review_and_build_boundaries(
        tmp_path, production_console, production_app, monkeypatch, essential):
    from tests.test_human_annotation_review_postgres import candidate, execute_build
    console, actor, sid, request = upgraded_ready_document(production_console, tmp_path, monkeypatch, essential)
    with TestClient(production_app(console), base_url='https://testserver') as client:
        assert client.post('/login', data={'username':'builder','password':'human-build-secret'}, follow_redirects=False).status_code == 303
        page = client.get('/annotations', params={'document':sid, 'overview':'true'})
        assert page.status_code == 200
        assert ('Als essentieel aangemerkt: Alleen bij klachten.' in page.text) == (essential is True)
        if essential == 'withdrawal':
            assert 'Teruggenomen verband: Voorwaarde — Alleen bij klachten.' in page.text
            assert 'Controle &lt;eerder&gt; vastgelegd.' in page.text
        updated = dict(request, command_id=str(uuid4()), expected_revision=1, expected_generation=1)
        response = client.post('/annotations/api', json=updated)
        if essential:
            assert response.status_code == 409
            assert response.json()['error'] == 'annotation_historical_read_only'
            assert not build.overview(console, actor_id=actor, snapshot_id=sid)['can_finalize']
        else:
            assert response.json()['revision'] == 2
            execute_build(console, actor, sid)
            assert candidate(console, sid)['metadata']['human_annotation']['annotation_id'] == request['annotation_id']
    with console.workflow_document_store._connect() as con:
        versions = con.execute('SELECT payload,payload_hash FROM workflow.annotation_versions WHERE snapshot_id=%s '
                               'ORDER BY revision', (sid,)).fetchall()
    assert len(versions) == (1 if essential else 2)
    assert bool(versions[0]['payload']['required_links']) == (essential == 'withdrawal')
    assert all(stable_hash(v['payload']) == v['payload_hash'] for v in versions)
    if not essential:
        assert annotations.historical_finding(versions[1]['payload']) is None
