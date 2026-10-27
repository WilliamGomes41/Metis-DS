"""Source-bound mixed first/batch/second work for #861, using real commands."""
from tests.semantic_fixture_support import bind_fixture_selections

PASSWORD = 'content-review-test-only'
TEXTS = [('De werkgroep adviseert interventie A te gebruiken.', 'recommendation'),
         ('Een waarneming is een beschrijving van de situatie.', 'definition'),
         ('Een registratie is een vastlegging van een waarneming.', 'definition'),
         ('De werkgroep adviseert interventie B te gebruiken.', 'recommendation')]


def bind(console):
    bind_fixture_selections(console, selections=TEXTS)


def prepare(console, copies=1):
    accounts = {name: console.create_account(username='content.'+name, password=PASSWORD,
        roles=('researcher', 'reviewer') if name == 'a' else ('reviewer',)) for name in ('a', 'b', 'outsider')}
    a, b = [accounts[name]['account_id'] for name in ('a', 'b')]
    policy = {'contract': 'explicit-review-v1', 'revision': 1, 'primary': a,
              'assignments': [{'reviewer_id': b, 'participation': 'required'}]}
    docs = []
    for index in range(copies):
        sid = console.ingest(actor_id=a, filename=f'Inhoud{index}.html',
            data=('<html><body><h1>Inhoud</h1>'+''.join('<p>'+text+'</p>' for text, _ in TEXTS)+'</body></html>').encode(),
            content_type='text/html', ingest_kind='new', title=f'Inhoud {index}', version='1.0', date='2026-10-27',
            live_url='', class_='richtlijn', family='content-review', named_reviewers=[], review_policy={**policy, 'assignments': [{'reviewer_id': b, 'participation': 'optional'}]})['snapshot_id']
        ids = {row['content']['clean_text']: row['object_id'] for row in console.snapshot_objects(sid)}
        doc = dict(snapshot_id=sid, context=ids[TEXTS[0][0]], batch=[ids[t] for t, _ in TEXTS[1:3]], second=ids[TEXTS[3][0]])
        second_sid = console.ingest(actor_id=a, filename=f'Tweede{index}.html',
            data=('<html><body><h1>Tweede beoordeling</h1><p>'+TEXTS[3][0]+'</p></body></html>').encode(),
            content_type='text/html', ingest_kind='new', title=f'Tweede {index}', version='1.0', date='2026-10-27',
            live_url='', class_='richtlijn', family='content-second', named_reviewers=[], review_policy=policy)['snapshot_id']
        doc['second_snapshot'] = second_sid
        doc['second'] = next(r['object_id'] for r in console.snapshot_objects(second_sid) if r['content']['clean_text'] == TEXTS[3][0])
        console.review_object(actor_id=a, snapshot_id=second_sid, object_id=doc['second'], decision='approve',
            confirmed_object_type='recommendation', recommendation_direction='for', recommendation_strength_level='not_stated')
        docs.append(doc)
    return accounts, docs


def snapshot(console, docs):
    ids = [sid for doc in docs for sid in (doc['snapshot_id'], doc['second_snapshot'])]
    return {'objects': [console.snapshot_objects(sid, include_blocked=True) for sid in ids],
            'envelopes': [console._envelope(sid) for sid in ids],
            'bindings': [console.object_review_bindings(sid) for sid in ids],
            'events': console.workflow_review_store.read_events_for_snapshots(ids)}
