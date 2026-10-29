"""Command dependency capture follows current edges and retains selected history.

# release-control-evidence: scope/belofte opslag stale concurrent
# release-control-evidence: kwaliteit metrics slop releasebewijs
"""
from copy import deepcopy
from types import SimpleNamespace

from src.review.review_command_v1 import capture_histories
from src.vorming.heading_parent_list_v1 import parent_proposal_may_bind
from tests.test_review_command_storage_v1 import seed


def test_native_capture_ignores_removed_incoming_relation_but_retains_current_dependency(
    complete_postgres,
):
    documents, _reviews, sid, _reviewer = seed(complete_postgres)
    envelope = documents.get_envelope(sid)
    rows = documents.list_document_objects(sid)
    former = next(row for row in rows if row['object_id'] == 'delta-b')
    former['confirmed_relations'] = [{'relation_type': 'supported_by', 'target_object_id': 'delta-a'}]
    current = deepcopy(former)
    current['object_version'] = '1.1'
    current['confirmed_relations'] = []
    documents.write_bundle(envelope=envelope, objects=[*rows, current])

    owner = SimpleNamespace(workflow_document_store=documents)
    captured = capture_histories(owner, sid, 'delta-a', {'decision': 'approve'})
    assert {row['object_id'] for row in captured} == {'delta-a'}
    assert [row['object_version'] for row in captured] == ['1.0', '1.1']

    # Filtering historical edges must not omit the same edge when current.
    linked = deepcopy(current)
    linked['object_version'] = '1.2'
    linked['confirmed_relations'] = deepcopy(former['confirmed_relations'])
    rows = documents.list_document_objects(sid)
    documents.write_bundle(envelope=envelope, objects=[*rows, linked])
    captured = capture_histories(owner, sid, 'delta-a', {'decision': 'approve'})
    assert {row['object_id'] for row in captured} == {'delta-a', 'delta-b'}
    assert [row['object_version'] for row in captured if row['object_id'] == 'delta-b'] == [
        '1.0', '1.1', '1.2']


def test_explicit_parent_capture_preserves_full_heading_toc_validation(complete_postgres):
    documents, _reviews, sid, _reviewer = seed(complete_postgres)
    headings = [dict(object_id=oid, object_version='1.0', object_type='heading',
                     extract_index=index, content={'clean_text': text})
                for index, (oid, text) in enumerate([
                    ('toc', 'Inhoudsopgave'), ('parent', '1 Thema'),
                    ('child', '1.1 Onderwerp')])]
    former_heading = dict(object_id='former', object_version='1.0', object_type='heading')
    former_current = {**former_heading, 'object_version': '1.1', 'object_type': 'claim'}
    proposed = dict(object_id='proposed', object_version='1.0', object_type='claim',
                    proposed_object_type='heading', extract_index=3,
                    content={'clean_text': '1.2 Nog een onderwerp'})
    documents.write_bundle(envelope=documents.get_envelope(sid),
        objects=[*headings, former_heading, former_current, proposed])
    assert not parent_proposal_may_bind(headings[2], headings[1], headings)
    # Without TOC context the exact same validator erroneously permits this edge.
    assert parent_proposal_may_bind(headings[2], headings[1], headings[1:])
    owner = SimpleNamespace(workflow_document_store=documents)
    captured = capture_histories(owner, sid, 'child', {
        'decision': 'later', 'documentpositie_action': 'andere_kop', 'parent_choice': 'parent'})
    assert not parent_proposal_may_bind(headings[2], headings[1], captured)
    assert {row['object_id'] for row in captured} == {'toc', 'parent', 'child', 'proposed'}
