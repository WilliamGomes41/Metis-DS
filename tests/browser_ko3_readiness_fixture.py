"""Synthetic KO-3 browser state on real PostgreSQL and immutable-source adapter.

# release-control-evidence: scope/belofte opslag slop releasebewijs

Only deterministic model and Blob network transport are substituted. Seeding
arranges the explicit conflict fixture before browser input; diagnostic routes
read persisted state and never execute review/publication commands.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from src.g2_source_store import AzureBlobSourceStore
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.publication.publication_refusal_store_v1 import postgres_store
from src.review.knowledge_object_state_v1 import snapshot_ko_states
from src.retrieval.retrieval_projection_v2 import build_projection
from tests.context_test_support import bind_detected_context
from tests.production_support import production_application
from tests.semantic_fixture_support import bind_fixture_selections, install_fixture_history
from tests.test_a10_source_cache_repair import DiskBlobTransport

PASSWORD = 'ko3-browser-test-only'
FIRST = 'Oedeem is een ophoping van vocht.'
SECOND = 'Een observatie is een systematische waarneming van gedrag.'
UNSELECTED = 'Leg de gemaakte afspraak letterlijk vast.'
EXPECTED = {
    'main': ['review_work_incomplete', 'source_passage_review_incomplete'],
    'source': ['source_passage_review_incomplete'],
    'second': ['required_policy_review_missing', 'four_eyes_required', 'review_work_incomplete'],
    'conflict': ['review_disposition_inconsistent'],
}

configuration = json.loads(Path(os.environ['METIS_KO3_BROWSER_CONFIG']).read_text())
root = Path(configuration['root'])
source = AzureBlobSourceStore(blob_service_client=DiskBlobTransport(root / 'immutable'))
app = production_application(root, PostgresCanonicalConfig(dsn=configuration['dsn']),
    processing_binder=bind_fixture_selections, immutable_source_store=source)
console = app.state.operations_kernel
manifest_path = root / 'browser-manifest.json'


def _seed():
    people = {name: console.create_account(username=f'ko3.{name}', password=PASSWORD,
        roles=roles, display_name=display) for name, roles, display in [
            ('author', ('researcher',), 'Anne Inleveraar'),
            ('reviewer', ('reviewer',), 'Bert Reviewer'),
            ('second', ('reviewer',), 'Dana Tweede reviewer'),
            ('publisher', ('publisher',), 'Carla Uitgever'),
        ]}
    documents = {}
    for slug, title in [('second', 'KO-3 Onafhankelijke review'),
                        ('source', 'KO-3 Bronafhandeling'),
                        ('conflict', 'KO-3 Uitkomstconflict'),
                        ('main', 'KO-3 Gereedheid van kennisobjecten')]:
        selections = [(FIRST, 'definition')] if slug == 'source' else None
        bind_fixture_selections(console, selections)
        second_text = UNSELECTED if slug == 'source' else SECOND
        heading = '' if slug == 'main' else '<h1>Begrippen</h1>'
        html = f'<html><body>{heading}<p>{FIRST}</p><p>{second_text}</p></body></html>'
        policy = {}
        if slug == 'second':
            policy['review_policy'] = {'contract': 'explicit-review-v1', 'revision': 1,
                'primary': people['reviewer']['account_id'],
                'assignments': [{'reviewer_id': people['second']['account_id'],
                                 'participation': 'required'}]}
        sid = console.ingest(actor_id=people['author']['account_id'], filename=f'{slug}.html',
            content_type='text/html', data=html.encode(), ingest_kind='new', title=title,
            version='1.0', date='2026-11-06', live_url='', class_='richtlijn', family=f'ko3-{slug}',
            named_reviewers=[people['reviewer']['account_id'], people['second']['account_id']],
            **policy)['snapshot_id']
        bind_detected_context(console, sid, people['reviewer']['account_id'])
        candidates = [o for o in console.snapshot_objects(sid) if '-sem-' in o['object_id']]
        pending = None
        for obj in candidates:
            if slug == 'main' and obj['content']['clean_text'] == SECOND:
                pending = obj['object_id']
                continue
            console.review_object(actor_id=people['reviewer']['account_id'], snapshot_id=sid,
                object_id=obj['object_id'], decision='approve', confirmed_object_type='definition',
                relation_review_ack=True, suitability='ja', eindoordeel='goedkeuren')
        conflict_id = None
        if slug == 'conflict':
            history = console._load_objects(sid)
            current = console.snapshot_objects(sid)[-1]
            chosen = next(o for o in history if o['object_id'] == current['object_id']
                          and o['object_version'] == current['object_version'])
            chosen['metadata']['passage_register']['status'] = 'used_as_context'
            install_fixture_history(console, sid, history)
            conflict_id = chosen['object_id']
        considered = console.consider_publish(actor_id=people['publisher']['account_id'], snapshot_id=sid)
        assert considered['blockers'] == EXPECTED[slug], (slug, considered)
        documents[slug] = {'snapshot_id': sid, 'title': title, 'pending_object_id': pending,
            'conflict_object_id': conflict_id, 'expected_blockers': EXPECTED[slug],
            'source_sha256': console._envelope(sid)['sha256']}
    value = {'documents': documents, 'password': PASSWORD,
             'people': {name: {'username': person['username'], 'account_id': person['account_id']}
                        for name, person in people.items()}}
    manifest_path.write_text(json.dumps(value))
    return value


manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else _seed()


def _digest(table, *, snapshot_id=None):
    with console.workflow_document_store._connect() as connection:
        condition = ' WHERE r.snapshot_id=%s' if snapshot_id else ''
        rows = connection.execute(f'SELECT to_jsonb(r) AS value FROM {table} r' + condition,
                                  (snapshot_id,) if snapshot_id else ()).fetchall()
    values = sorted(json.dumps(row['value'], sort_keys=True, default=str) for row in rows)
    return hashlib.sha256('\n'.join(values).encode()).hexdigest()


@app.get('/browser-manifest')
def browser_manifest():
    return manifest


@app.get('/browser-proof/{slug}')
def browser_proof(slug: str):
    doc = manifest['documents'][slug]
    sid = doc['snapshot_id']
    considered = console.consider_publish(actor_id=manifest['people']['publisher']['account_id'],
                                          snapshot_id=sid)
    current = console.snapshot_objects(sid)
    states = snapshot_ko_states(console, console._envelope(sid))
    records = postgres_store(console).records_for(sid)
    projection = console._validate_publication_state()
    selected = set(considered.get('publishable_object_ids', []))
    _, prospective_errors = build_projection([{'knowledge_object': obj,
        'publication': {'release_id': 'fixture-preview', 'release_version': 'fixture-preview',
                        'published_at': '2026-11-06T00:00:00Z'}}
        for obj in current if obj['object_id'] in selected])
    return {'blockers': considered['blockers'],
        'curation_blockers': considered['curation_blockers'],
        'publication_ready': considered['publication_ready'],
        'publishable_object_count': considered['publishable_object_count'],
        'review_duties': considered.get('review_duties', []),
        'source_pending': considered.get('unresolved_source_passage_ids', []),
        'object_readiness': considered.get('object_readiness', []),
        'states': {obj['object_id']: state for obj, state in zip(current, states, strict=True)},
        'refusal_count': len(records),
        'workflow_digest': {table: _digest(table, snapshot_id=sid) for table in
            ['workflow.documents', 'workflow.document_objects', 'workflow.publish_authorizations',
             'workflow.review_events']},
        'canonical_digest': {table: _digest(table) for table in
            ['canonical_object_versions', 'canonical_object_sources', 'publication_releases',
             'publication_release_items', 'publication_registry', 'audit_events']},
        'projection': [{'object_id': row['metadata']['object_id'],
                        'object_version': row['metadata']['object_version'],
                        'type': row['metadata']['object_type'],
                        'source_bound_context': row['metadata'].get('source_bound_context'),
                        'source_locator': row['metadata']['source_locator']}
                       for row in projection],
        'prospective_projection_errors': prospective_errors,
        'publisher_badge': console.waiting_task_counts(manifest['people']['publisher']['account_id'])['publish'],
        'source_sha256': console._envelope(sid)['sha256']}
