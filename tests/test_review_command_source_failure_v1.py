"""Missing-source parity: safe disposition stays available; approval fails closed.

# release-control-evidence: scope/belofte opslag stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy

import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming.source_accountability_v1 import is_source_record
from tests.production_support import restart_production
from tests.test_review_formation_problems import FIRST, SECOND, execute, received


def test_missing_source_preserves_safe_disposition_and_refuses_content_approval(
    tmp_path, production_console, monkeypatch,
):
    console, sid, author, reviewer, *_ = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'missing-source-review-parity')
    objects = console.snapshot_objects(sid)
    source = next(obj for obj in objects
                  if is_source_record(obj) and obj['content']['clean_text'] == SECOND)
    candidate = next(obj for obj in objects if obj.get('proposed_object_type') == 'recommendation'
                     and obj['content']['clean_text'] == FIRST)
    assert console.immutable_source_store is None
    console._source_cache_path(console._envelope(sid)).unlink()

    # The original source-disposition command has no open-original condition.
    result = console.review_object(actor_id=reviewer, snapshot_id=sid,
        object_id=source['object_id'], decision='reject',
        comment='Explicit disposition of this exact retained source record.')
    assert next(obj for obj in result if obj['object_id'] == source['object_id'])[
        'governance']['validation_status'] == 'rejected'
    assert next(obj for obj in console.snapshot_objects(sid) if obj['object_id'] == candidate['object_id'])[
        'governance']['validation_status'] == 'needs_review'

    def durable(owner):
        documents, reviews = owner.workflow_document_store, owner.workflow_review_store
        with documents._connect() as con:
            counters = dict(con.execute(
                'SELECT revision,object_generation FROM workflow.documents WHERE snapshot_id=%s',
                (sid,),
            ).fetchone())
        return deepcopy((documents.get_envelope(sid), documents.list_document_objects(sid),
                         reviews.read_bindings([sid]), reviews.read_events(), counters))

    before = durable(console)
    with pytest.raises(ConsoleError) as refused:
        console.review_object(actor_id=reviewer, snapshot_id=sid,
            object_id=candidate['object_id'], decision='approve',
            confirmed_object_type='recommendation', recommendation_direction='against',
            recommendation_strength_level='not_stated', relation_review_ack=True)
    assert refused.value.code == 'source_lineage_unavailable'
    assert durable(console) == before
    assert durable(restart_production(console)) == before
