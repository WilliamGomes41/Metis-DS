"""A prewrite repair handoff retains the caller's public generation contract.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: kwaliteit slop releasebewijs
"""
import re

from src.operations_console_app import ERROR_COPY
from tests.production_support import restart_production
from tests.test_deterministic_review_repair_v1 import _review_payload, _system
from tests.test_review_command_bounded_http_v1 import physical_state


def test_native_repair_handoff_keeps_original_generation_and_stale_guards(
    tmp_path, production_console, production_app,
):
    console, client, _author, _reviewer, sid, objects = _system(
        tmp_path, production_app=production_app, production_console=production_console)
    focal = objects[0]
    page = client.get('/review', params={'document': sid, 'object': focal['object_id']})
    assert page.status_code == 200
    match = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text)
    assert match and match.group(1).startswith('review-generation-v1:')
    original_generation = match.group(1)
    review = {**_review_payload(console, sid, focal), 'snapshot_revision': original_generation}
    own_fragments = {ref['raw_object_id'] for ref in focal['provenance']['source_fragments']}
    units = [row['unit_id'] for row in console.source_units(snapshot_id=sid, object_id=focal['object_id'])
             if row['fragment_id'] in own_fragments]
    assert units

    def durable(owner):
        return physical_state(owner, sid), owner.workflow_review_store.read_events()

    before = durable(console)
    specification = client.post('/review', data=review, follow_redirects=False)
    assert specification.status_code == 400
    assert 'structured_repair_required' in specification.text
    assert durable(console) == before
    fields = {**review, 'repair_kind': 'source_units'}
    assert fields['snapshot_revision'] == original_generation
    resolve = {**fields, 'source_unit_ids': units, 'comment': 'Gebruik de volledige bronzin.'}
    saved = client.post('/review/resolve', data=resolve, follow_redirects=False)
    assert saved.status_code == 303
    current = console._current_object(sid, focal['object_id'])
    assert current['object_version'] != focal['object_version']
    assert current['governance']['validation_status'] == 'needs_review'
    winner = durable(console)
    assert winner != before
    assert durable(restart_production(console)) == winner

    # Both public entry points keep their existing stale-response contracts.
    stale_review = client.post('/review', data=review, follow_redirects=False)
    assert stale_review.status_code == 409
    assert 'data-error-code="snapshot_object_write_conflict"' in stale_review.text
    assert durable(console) == winner
    stale_repair = client.post('/review/resolve', data=resolve, follow_redirects=False)
    assert stale_repair.status_code in (400, 409)
    assert ERROR_COPY['snapshot_object_write_conflict'] in stale_repair.text
    assert durable(console) == winner
