"""Keep a separately located exception on the human-annotated recommendation.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from src.vorming import human_annotation_v1 as annotation
from src.vorming import human_annotation_build_v1 as build
from src.vorming.source_bound_fields_v3 import FIELDS
from tests.production_support import application_for
from tests.test_human_annotation_postgres import anchor, command
from tests.test_human_annotation_review_postgres import candidate, execute_build


def test_smetten_exception_survives_human_annotation_build_and_review(tmp_path, production_console):
    source = Path(__file__).parent / 'fixtures/smetten-documenttoets.html'
    recommendation = 'Controleer dagelijks de huid. Leg de waarneming vast.'
    exception = 'Sla de dagelijkse huidcontrole over als de patiënt de controle weigert.'
    console = production_console(root=tmp_path)
    researcher = console.create_account(username='annotator', password='fixture-only', roles=('researcher',))
    reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))
    actor = researcher['account_id']
    sid = console.receive_source(actor_id=actor, filename=source.name, data=source.read_bytes(),
        content_type='text/html', ingest_kind='new', title='Synthetische Smetten-proef',
        version='1', date='2026-11-18', live_url='', class_='richtlijn', family='test',
        named_reviewers=[reviewer['account_id']])['snapshot_id']
    view = annotation.prepare(console, actor_id=actor, snapshot_id=sid,
                              expected_revision=console.objects_revision(sid))
    core = anchor(view, recommendation)
    condition = anchor(view, 'Pas deze aanbeveling toe', role='condition')
    exception_range = anchor(view, exception, role='exception')
    assert exception_range['block_id'] != core['block_id']
    exception_span = {key: exception_range[key] for key in ('block_id', 'start', 'end')}

    fields = {key: {'span': None, 'missing_reason': 'not_applicable'} for key in FIELDS}
    for field, text in [('predicate_span', 'Controleer'), ('recommended_action', 'Controleer dagelijks de huid'),
                        ('action_object_or_goal', 'de huid')]:
        start = recommendation.index(text)
        fields[field] = {'span': {'block_id': core['block_id'], 'start': start, 'end': start + len(text)},
                         'quote': text, 'missing_reason': None}
    fields.update(type_evidence_spans={'core': True}, recommendation_evidence_span={'core': True})
    request = command(view, ranges=[core, condition], status='ready')
    request['selection'].update(evidence_not_applicable=True, field_evidence=fields)
    saved = annotation.save(console, actor_id=actor, **request)

    overview = build.overview(console, actor_id=actor, snapshot_id=sid)
    assert overview['inspection']['unaccounted_ranges'] == [{**exception_span, 'quote': exception}]
    assert not overview['can_finalize']

    request.update(command_id=str(uuid4()), expected_revision=saved['revision'],
                   expected_generation=saved['generation'])
    request['selection']['ranges'].append(exception_range)
    annotation.save(console, actor_id=actor, **request)
    overview = build.overview(console, actor_id=actor, snapshot_id=sid)
    assert overview['can_finalize'], overview['inspection']
    execute_build(console, actor, sid)

    obj = candidate(console, sid)
    assert obj['content']['clean_text'] == recommendation
    context = obj['metadata']['source_bound_context']['entries']
    entry, = [item for item in context if item['role'] == 'exception']
    assert entry['span'] == exception_span and entry['text'] == exception
    assert entry['source_mapping']

    with TestClient(application_for(console)) as client:
        login = client.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'},
                            follow_redirects=False)
        assert login.status_code == 303
        review = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    assert review.status_code == 200
    # The literal can also occur in the expandable source. Require it in the
    # existing object summary under the specific exception label.
    assert f'<th scope="row">Uitzondering</th><td><p>{exception}' in review.text
