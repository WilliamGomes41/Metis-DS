"""Keep a separately located exception on the human-annotated recommendation.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from src.review.ko_receipt_ui_v1 import knowledge_connections_html
from src.vorming import human_annotation_v1 as annotation
from src.vorming import human_annotation_build_v1 as build
from src.vorming.source_bound_fields_v3 import FIELDS
from tests.production_support import application_for
from tests.test_human_annotation_postgres import anchor, command
from tests.test_human_annotation_review_postgres import candidate, execute_build


def test_smetten_exception_survives_human_annotation_build_and_review(tmp_path, production_console):
    source = Path(__file__).parent / 'fixtures/smetten-documenttoets.html'
    original = 'Controleer dagelijks de huid. Leg de waarneming vast.'
    recommendation = 'Controleer bij iedere patiënt dagelijks de huid. Leg de waarneming vast.'
    population = 'iedere patiënt'
    situation = 'Bij zorg thuis.'
    additional_context = 'Met huid wordt hier de intacte huid bedoeld.'
    data = (source.read_text().replace(original, recommendation)
            .replace('</body>', f'<p>{situation}</p><p>{additional_context}</p></body>')).encode()
    exception = 'Sla de dagelijkse huidcontrole over als de patiënt de controle weigert.'
    console = production_console(root=tmp_path)
    researcher = console.create_account(username='annotator', password='fixture-only', roles=('researcher',))
    reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))
    actor = researcher['account_id']
    sid = console.receive_source(actor_id=actor, filename=source.name, data=data,
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
    for field, text in [('predicate_span', 'Controleer'), ('recommended_action', 'Controleer bij iedere patiënt dagelijks de huid'),
                        ('action_object_or_goal', 'de huid')]:
        start = recommendation.index(text)
        fields[field] = {'span': {'block_id': core['block_id'], 'start': start, 'end': start + len(text)},
                         'quote': text, 'missing_reason': None}
    fields['target_group_span'] = {'span': None, 'missing_reason': 'not_stated'}
    fields.update(type_evidence_spans={'core': True}, recommendation_evidence_span={'core': True})
    start = recommendation.index(population)
    population_range = anchor(view, population, role='population', start=start, end=start + len(population))
    assert population_range['block_id'] == core['block_id']
    assert core['start'] < population_range['start'] < population_range['end'] < core['end']
    request = command(view, ranges=[core, population_range, condition,
        anchor(view, situation, role='scope'), anchor(view, additional_context, role='context')], status='ready')
    request['selection'].update(evidence_not_applicable=True, field_evidence=fields)
    saved = annotation.save(console, actor_id=actor, **request)

    overview = build.overview(console, actor_id=actor, snapshot_id=sid)
    pending = annotation.overview(console, actor_id=actor, snapshot_id=sid, include_source_work=True)
    assert any({**exception_span, 'quote': exception}.items() <= gap.items()
               for gap in pending['source_work']['ranges'])
    assert not overview['can_finalize']

    request.update(command_id=str(uuid4()), expected_revision=saved['revision'],
                   expected_generation=saved['generation'])
    request['selection']['ranges'].append(exception_range)
    annotation.save(console, actor_id=actor, **request)
    from tests.test_human_annotation_build_postgres import open_document_check
    open_document_check(console, actor, sid)
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

    card = review.text.split('class="ko-meaning-table"', 1)[1].split('</table>', 1)[0]
    assert '<th colspan="2">Toepassing</th>' in card
    receipt = knowledge_connections_html(obj, [obj])
    for label, text in [('Doelgroep', population), ('Situatie', situation),
                        ('Voorwaarde', 'Pas deze aanbeveling toe als de huid zichtbaar is.'), ('Aanvullende context', additional_context)]:
        assert f'<th scope="row">{label}</th><td><p>{text}' in card
        assert f'<dt>{label}</dt><dd>{text}' in receipt
        assert receipt.count(text) == 1
    assert 'Niet expliciet vermeld' not in card + receipt
