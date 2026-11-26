"""Actual PG/ASGI correction fixture; no test endpoints in product code."""
import os

from src.vorming import annotation_document_check_v1 as document_check
from src.vorming import annotation_section_coverage_v1 as coverage
from src.vorming import confirmed_document_structure_v1 as structure
from src.vorming import human_annotation_v1 as annotation
from tests.browser_postgres_support import browser_application
from tests.test_human_annotation_build_postgres import saved_source
from tests.test_human_annotation_review_postgres import execute_build, candidate, approve
from tests.test_reviewer_recommendation_semantics_1067 import prepared_recommendation

app = browser_application('human-review')
console = app.state.operations_kernel
recommendation_sid, recommendation, _, _ = prepared_recommendation(console, explicitly_proposed=True)
os.environ['METIS_ANNOTATION_DOCUMENT_CHECK'] = '1'
os.environ['METIS_ANNOTATION_CONFIRMED_STRUCTURE'] = '1'
_, actor, sid, original = saved_source(lambda **kwargs: console, console.root, context_function='supported_by')
scope = {'actor_id': actor, 'snapshot_id': sid}
initial = annotation.overview(console, **scope)
structure.confirm(console, **scope, extraction_hash=initial['extraction_hash'], entries=[])
document_check.transition(console, **scope, phase='checking',
                          expected_generation=initial['generation'], expected_round=0)
section_view = annotation.overview(console, **scope, include_coverage=True)[coverage.KEY]
coverage.write(console, **scope, basis=section_view['basis'], scope='full')
section, = section_view['sections']
coverage.write(console, **scope, basis=section_view['basis'],
               section=section['block_id'], fingerprint=section['fingerprint'])
execute_build(console, actor, sid)
reviewer = console._envelope(sid)['named_reviewers'][0]
oid = candidate(console, sid)['object_id']
approve(console, sid, oid, reviewer)
version = candidate(console, sid)['object_version']


@app.get('/browser-manifest')
def manifest():
    return {'document': sid, 'annotation': original['annotation_id'], 'object': oid,
            'version': version, 'username': 'reviewer', 'password': 'human-build-secret',
            'recommendation_document': recommendation_sid, 'recommendation_object': recommendation['object_id']}
