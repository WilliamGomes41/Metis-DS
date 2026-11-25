"""Exercise document control through the real editor, dispatcher and PostgreSQL."""
import os

from tests.browser_postgres_support import browser_application
from tests.test_human_annotation_build_postgres import saved_source

os.environ['METIS_ANNOTATION_DOCUMENT_CHECK'] = '1'
os.environ['METIS_ANNOTATION_CONFIRMED_STRUCTURE'] = '1'
app = browser_application('annotation-document-check')
console = app.state.operations_kernel
_, _, snapshot_id, _ = saved_source(lambda **_: console, None, review_option='uploader_sole',
    heading='<h1>Algemeen</h1><p>Overige begeleidende tekst.</p><h2>Diagnostiek</h2>')


@app.get('/browser-manifest')
def manifest():
    return {'username': 'builder', 'password': 'human-build-secret', 'snapshot_id': snapshot_id}
