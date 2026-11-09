"""Test-only native PostgreSQL fixture; no production bootstrap or delete action."""
import os
os.environ['CONSOLE_TEST_DOCUMENT_DELETION'] = 'on'

from tests.browser_postgres_support import browser_application
from tests.test_test_document_deletion_postgres import published, receive, form_source
from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore, TEST_PASSWORD
from src.vorming import human_annotation_v1 as annotation
from tests.test_human_annotation_postgres import anchor, command
from src.product_api_v1 import create_product_app
from tests.test_product_api_v1 import paths, registry, KEY

app = browser_application('publisher-test-delete',immutable_source_store=MemorySourceStore())
console = app.state.operations_kernel
_, accounts, sid, release, _ = published(lambda **kwargs:console,console.root)
draft = receive(console,accounts,prior=sid)
view = annotation.prepare(console,actor_id=accounts['researcher']['account_id'],snapshot_id=draft,
                          expected_revision=console.objects_revision(draft))
annotation.save(console,actor_id=accounts['researcher']['account_id'],
                **command(view,ranges=[anchor(view,'Bespreek het onderwerp')]))
other = receive(console,accounts,title='Ander document',version='1.0')
other_release = form_source(console,accounts,other)
rows = console.canonical_publication_store.active_publication_rows()
old_object = next(r['knowledge_object']['object_id'] for r in rows if r['publication']['release_id']==release['release_id'])
other_object = next(r['knowledge_object']['object_id'] for r in rows if r['publication']['release_id']==other_release['release_id'])
app.mount('/public',create_product_app('real',paths=paths(console.root/'api'),
    tenant_registry=registry(docs=('*',)),canonical_publication_store=console.canonical_publication_store,
    immutable_source_store=console.immutable_source_store))


@app.get('/browser-manifest')
def manifest():
    return {'document':sid,'username':accounts['publisher']['username'],'password':TEST_PASSWORD,
        'title': 'Continentie fixture','old_object':old_object,'other_object':other_object,'key':KEY}
