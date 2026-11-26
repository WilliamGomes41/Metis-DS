"""Browser fixture for source selection against a real PDF extraction."""
from tests.browser_postgres_support import browser_application
from tests.test_annotation_strength_label_pdf import LABEL, prepare_recommendation_pdf
from src.vorming import human_annotation_v1 as annotation

app = browser_application('strength-label')
console = app.state.operations_kernel
actor, snapshot, _, request = prepare_recommendation_pdf(console, 'following')
request['selection']['status'] = 'draft'
annotation.save(console, actor_id=actor, **request)


@app.get('/browser-manifest')
def manifest():
    return {'snapshot': snapshot, 'annotation': request['annotation_id'],
            'label': LABEL, 'username': 'sterkte', 'password': 'fixture-only'}
