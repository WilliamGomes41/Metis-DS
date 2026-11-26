"""Exercise document control through the real editor, dispatcher and PostgreSQL."""
from tests.browser_postgres_support import browser_application
from tests.test_human_annotation_build_postgres import saved_source
from src.vorming import human_annotation_v1 as annotation

app = browser_application('annotation-document-check')
console = app.state.operations_kernel
_, author, snapshot_id, _ = saved_source(lambda **_: console, None, review_option='uploader_sole', for_build=False,
    heading='<h1>Algemeen</h1><p>Overige begeleidende tekst.</p><h2>Diagnostiek</h2>')
without_headings = console.receive_source(
    actor_id=author, filename='korte-bron.html', content_type='text/html',
    data=b'<html><body><p>Een bron met alleen lopende tekst.</p></body></html>',
    ingest_kind='new', title='Bron zonder koppen',
    version='1.0', date='2026-11-08', live_url='', class_='richtlijn', family='test', named_reviewers=[],
    source_status='unknown', review_choice={'contract': 'review-configuration-v2', 'option': 'uploader_sole',
        'four_eyes_required': False, 'reviewers': [], 'readers': []},
)['snapshot_id']
annotation.prepare(console, actor_id=author, snapshot_id=without_headings,
                   expected_revision=console.objects_revision(without_headings))


@app.get('/browser-manifest')
def manifest():
    return {'username': 'builder', 'password': 'human-build-secret',
            'snapshot_id': snapshot_id, 'without_headings': without_headings}
