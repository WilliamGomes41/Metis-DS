# release-control-evidence: scope/belofte opslag toegang slop releasebewijs
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from src.g2_source_store import AzureBlobSourceStore
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.review.knowledge_object_state_v1 import snapshot_ko_states
from tests.context_test_support import bind_detected_context
from tests.production_support import production_application
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_a10_source_cache_repair import DiskBlobTransport

PASSWORD = 'ko4-browser-fixture-only'
YES = {'version': 'review-assessment-v1', 'applicable': 'yes',
       'complete': 'yes', 'placed_correctly': 'yes'}
CLAIM = 'Een observatie is een systematische waarneming van gedrag.'
SUPPORT = 'Een systematische waarneming maakt veranderingen in gedrag herkenbaar.'
LONG_DEFINITION = ('Zelfzorgondersteuning is de gezamenlijke afstemming tussen cliënt, naasten en zorgverlener over de dagelijkse verzorging. '
    'De cliënt beschrijft welke handelingen zelfstandig lukken en bij welke handelingen ondersteuning gewenst is. '
    'Leg voorkeuren, voorwaarden en uitzonderingen vast, bespreek veranderingen bij iedere evaluatie en controleer samen of de afgesproken ondersteuning blijft aansluiten. '
    'Als de cliënt geen ondersteuning wenst, wordt deze keuze besproken en herkenbaar vastgelegd zonder een eerder besluit stilzwijgend over te nemen.')
DEFINITION = 'Zelfzorg is de zorg die iemand zelf uitvoert.'
CORRECTION = 'Zelfzorg is de zorg die iemand zelf uitvoert, met passende ondersteuning als dat nodig is.'

configuration = json.loads(Path(os.environ['METIS_KO4_BROWSER_CONFIG']).read_text())
root = Path(configuration['root'])
source = AzureBlobSourceStore(blob_service_client=DiskBlobTransport(root / 'immutable'))
app = production_application(root, PostgresCanonicalConfig(dsn=configuration['dsn']),
    processing_binder=bind_fixture_selections, immutable_source_store=source)
console = app.state.operations_kernel
manifest_path = root / 'ko4-browser-manifest.json'


def _seed():
    people = {name: console.create_account(username='ko4.' + name, password=PASSWORD,
        roles=roles, display_name=display) for name, roles, display in [
            ('author', ('researcher',), 'Anne Inleveraar'),
            ('reviewer', ('reviewer',), 'Bert Reviewer'),
            ('second', ('reviewer',), 'Dana Tweede reviewer'),
        ]}
    documents = {}
    for slug, texts in [('link', [SUPPORT, CLAIM]),
                        ('not-applicable', [DEFINITION, CORRECTION]),
                        ('second', [DEFINITION]), ('long-text', [LONG_DEFINITION])]:
        selected = texts[:1] if slug == 'not-applicable' else texts
        bind_fixture_selections(console, [(text, 'definition') for text in selected])
        policy = {}
        if slug == 'second':
            policy['review_policy'] = {'contract': 'explicit-review-v1', 'revision': 1,
                'primary': people['reviewer']['account_id'],
                'assignments': [{'reviewer_id': people['second']['account_id'],
                                 'participation': 'required'}]}
        sid = console.ingest(actor_id=people['author']['account_id'], filename=slug + '.html',
            content_type='text/html', data=('<h1>Begrippen</h1>' + ''.join(
                '<p>' + text + '</p>' for text in texts)).encode(), ingest_kind='new',
            title={'link': 'Onderbouwing beoordelen', 'not-applicable': 'Zelfzorg beoordelen',
                   'second': 'Onafhankelijk tweede akkoord',
                   'long-text': 'Langdurige ondersteuning bij dagelijkse zelfzorg met afspraken over voorkeuren, voorwaarden en evaluatie'}[slug], version='1.0',
            date='2026-11-06', live_url='', class_='richtlijn', family='ko4-' + slug,
            named_reviewers=[people['reviewer']['account_id'], people['second']['account_id']],
            **policy)['snapshot_id']
        bind_detected_context(console, sid, people['reviewer']['account_id'])
        candidates = [o for o in console.snapshot_objects(sid) if '-sem-' in o['object_id']]
        by_text = {o['content']['clean_text']: o for o in candidates}
        focal = by_text[CLAIM if slug == 'link' else LONG_DEFINITION if slug == 'long-text' else DEFINITION]
        if slug == 'second':
            console.review_object(actor_id=people['reviewer']['account_id'], snapshot_id=sid,
                object_id=focal['object_id'], decision='approve', confirmed_object_type='definition',
                type_action='dit_klopt', suitability='ja', eindoordeel='goedkeuren',
                relation_review_ack=True, assessment=YES, evidence_not_applicable=True)
        documents[slug] = {'snapshot_id': sid, 'object_id': focal['object_id'],
            'support_object_id': by_text[SUPPORT]['object_id'] if slug == 'link' else None,
            'correction_text': CORRECTION if slug == 'not-applicable' else None}
    value = {'documents': documents,
        'people': {name: {'username': person['username'], 'account_id': person['account_id']}
                   for name, person in people.items()}}
    manifest_path.write_text(json.dumps(value))
    return value


manifest = {**(json.loads(manifest_path.read_text()) if manifest_path.exists() else _seed()),
            'password': PASSWORD}


def _digest(table, sid=None, physical=False):
    with console.workflow_document_store._connect() as connection:
        where = ' WHERE r.snapshot_id=%s' if sid else ''
        columns = "jsonb_build_object('payload',to_jsonb(r),'ctid',r.ctid::text,'xmin',r.xmin::text)" if physical else 'to_jsonb(r)'
        rows = connection.execute(f'SELECT {columns} AS value FROM {table} r' + where,
                                  (sid,) if sid else ()).fetchall()
    values = sorted(json.dumps(row['value'], sort_keys=True, default=str) for row in rows)
    return hashlib.sha256('\n'.join(values).encode()).hexdigest()


@app.get('/ko4-browser-manifest')
def browser_manifest():
    return manifest


@app.get('/ko4-browser-proof/{slug}')
def browser_proof(slug: str):
    sid = manifest['documents'][slug]['snapshot_id']
    objects = console.snapshot_objects(sid)
    envelope = console._envelope(sid)
    state_objects = console.snapshot_objects(sid, envelope=envelope)
    states = snapshot_ko_states(console, envelope)
    return {'snapshot_id': sid, 'objects': objects, 'histories': console._load_objects(sid),
        'states': {row['object_id']: state for row, state in zip(state_objects, states, strict=True)},
        'bindings': console.object_review_bindings(sid),
        'events': console.workflow_review_store.read_events_for_snapshots([sid]),
        'workflow_digest': {table: _digest(table, sid, physical=True) for table in
            ['workflow.documents', 'workflow.document_objects', 'workflow.publish_authorizations',
             'workflow.review_events']},
        'canonical_digest': {table: _digest(table) for table in
            ['canonical_object_versions', 'canonical_object_sources', 'publication_releases',
             'publication_release_items', 'publication_registry', 'audit_events']},
        'immutable_files': {str(path.relative_to(root / 'immutable')):
            hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (root / 'immutable').rglob('*') if path.is_file()}}
