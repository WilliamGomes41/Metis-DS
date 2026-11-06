"""#974 actual PostgreSQL/ASGI fixture for the disposition-safe review form."""
from src.review.proportionate_review_v1 import normal_risk_batch_queue
from tests.browser_postgres_support import browser_application
from tests.semantic_fixture_support import bind_fixture_selections

PASSWORD = 'review-disposition-test-only'
app = browser_application('review-disposition', processing_binder=bind_fixture_selections)
state = app.state.operations_kernel
researcher = state.create_account(username='disp.anne', password=PASSWORD, roles=('researcher',))
reviewer = state.create_account(username='disp.bert', password=PASSWORD, roles=('reviewer',))
sid = state.ingest(
    actor_id=researcher['account_id'], filename='begrippen.html', content_type='text/html',
    data=b'<html><body><h1>Begrippen</h1><h2>1 Begrippen</h2>'
         b'<p>De Dutch Job Group (dJG) is een meetinstrument voor werkbelasting.</p>'
         b'<p>Een observatie is een systematische waarneming van gedrag.</p>'
         b'<p>Een evaluatie is een beoordeling van de gemaakte afspraken.</p>'
         b'<p>Een interventie is een handeling gericht op een zorgdoel.</p></body></html>',
    ingest_kind='new', title='Begrippen', version='1.0', date='2026-09-08', live_url='',
    class_='richtlijn', family='begrippen', named_reviewers=[reviewer['account_id']],
)['snapshot_id']
ids = [obj['object_id'] for obj in normal_risk_batch_queue(
    state.snapshot_objects(sid), review_path='richtlijn',
    bindings=state.object_review_bindings(sid), fragments=state.review_source_fragments(sid))]


@app.get('/browser-manifest')
def manifest():
    return {'snapshot_id': sid, 'objects': ids, 'username': 'disp.bert', 'password': PASSWORD}


@app.get('/browser-review-events')
def review_events():
    with state.workflow_review_store._connect() as con:
        return {'count': con.execute('SELECT count(*) AS n FROM workflow.review_events').fetchone()['n']}
