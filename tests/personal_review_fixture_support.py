"""Mixed source-bound work, real commands and exact current bindings for #860."""
from copy import deepcopy

from tests.semantic_fixture_support import bind_fixture_selections, install_fixture_history

PASSWORD = 'personal-review-test-only'
CONTEXT = 'De werkgroep adviseert de verpleegkundige interventie A te gebruiken.'
BATCH = 'Een waarneming is een beschrijving van de situatie.'
REJECTED = 'Deze oude uitleg wordt afgewezen.'
SUPERSEDED = 'Deze eerdere uitleg is vervangen.'
REPAIR = 'Deze uitleg wacht op technisch herstel.'
SOURCE = 'Versie: 1, documentinformatie blijft bronwerk.'


def bind(console):
    bind_fixture_selections(console, selections=[(CONTEXT, 'recommendation'), (BATCH, 'definition'),
        (REJECTED, 'explanation'), (SUPERSEDED, 'explanation'), (REPAIR, 'explanation')])


def prepare(console, *, mixed_copies=1):
    accounts = {name: console.create_account(username='personal.'+name, password=PASSWORD,
        roles=('researcher', 'reviewer') if name == 'a' else ('reviewer',)) for name in ('a', 'b', 'outsider')}
    a, b = [accounts[name]['account_id'] for name in ('a', 'b')]
    policy = {'contract': 'explicit-review-v1', 'revision': 1, 'primary': a,
              'assignments': [{'reviewer_id': b, 'participation': 'required'}]}
    docs = {}
    for name in (['Gemengd' + (str(i + 1) if i else '') for i in range(mixed_copies)]
                 + ['Wachten', 'Klaar', 'Bronwerk', 'Vergelijkbaar']):
        texts = [BATCH, SOURCE] if name in ('Bronwerk', 'Vergelijkbaar') else [CONTEXT, BATCH, SOURCE]
        if name.startswith('Gemengd'):
            texts += [REJECTED, SUPERSEDED, REPAIR]
        sid = console.ingest(actor_id=a, filename=name+'.html',
            data=('<html><body><h1>'+name+'</h1>'+''.join('<p>'+t+'</p>' for t in texts)+'</body></html>').encode(),
            content_type='text/html', ingest_kind='new', title=name, version='1.0', date='2026-10-27',
            live_url='', class_='richtlijn', family='personal', named_reviewers=[], review_policy=({**policy, 'assignments': [{'reviewer_id': b, 'participation': 'optional'}]}
                if name == 'Vergelijkbaar' else policy))['snapshot_id']
        ids = {row['content']['clean_text']: row['object_id'] for row in console.snapshot_objects(sid)}
        docs[name] = {'snapshot_id': sid, 'context': ids.get(CONTEXT), 'batch': ids.get(BATCH)}
        if name in ('Wachten', 'Klaar', 'Bronwerk'):
            for literal in ((BATCH,) if name in ('Bronwerk', 'Vergelijkbaar') else (CONTEXT, BATCH)):
                target = next(row for row in console.snapshot_objects(sid) if row['object_id'] == ids[literal])
                assert target['metadata']['admission']['gate_result'] == 'allowed', (literal, target['metadata']['admission'])
                console.review_object(actor_id=a, snapshot_id=sid, object_id=ids[literal], decision='approve',
                                      confirmed_object_type='recommendation' if literal == CONTEXT else 'definition',
                                      recommendation_direction='for', recommendation_strength_level='not_stated')
                if name in ('Klaar', 'Bronwerk'):
                    console.approve_second_review(actor_id=b, snapshot_id=sid, object_id=ids[literal])
        if name.startswith('Gemengd'):
            console.review_object(actor_id=a, snapshot_id=sid, object_id=ids[REJECTED], decision='reject',
                                  comment='Niet bruikbaar na inhoudelijke beoordeling.')
            # Represent supported historical/blocked rows; source and identity stay literal.
            rows = console.snapshot_objects(sid, include_blocked=True)
            for row in rows:
                if row['object_id'] == ids[SUPERSEDED]:
                    row['governance']['validation_status'] = 'superseded'
                if row['object_id'] == ids[REPAIR]:
                    row['metadata']['admission']['gate_result'] = 'blocked'
            install_fixture_history(console, sid, rows)
    return accounts, docs


def snapshot(console, docs):
    """GET-invariance evidence, independent from the landing's presentation."""
    ids = [doc['snapshot_id'] for doc in docs.values()]
    return {'envelopes': [deepcopy(console._envelope(sid)) for sid in ids],
            'objects': [console.snapshot_objects(sid, include_blocked=True) for sid in ids],
            'bindings': [console.object_review_bindings(sid) for sid in ids],
            'events': console.workflow_review_store.read_events_for_snapshots(ids)}
