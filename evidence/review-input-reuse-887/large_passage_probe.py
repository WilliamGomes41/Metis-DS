import json
import os
from pathlib import Path
from time import perf_counter
from copy import deepcopy

import pytest
from tests.test_review_render_source_reuse import review_client


@pytest.mark.parametrize('review_client', [300], indirect=True)
def test_incomplete_large_passage(review_client, monkeypatch):
    import src.vorming.knowledge_materialisation_v1 as materialisation
    import src.vorming.recoverable_formation_v1 as formation
    console, client, sid = review_client
    store = console.workflow_document_store
    envelope = store.get_envelope(sid)
    replay = envelope['semantic_replay']
    assert replay.get('identity') and replay.get('proposal_hash')
    evidence = replay.setdefault('provider_evidence', {})
    evidence['formation_incomplete'] = True
    evidence['pending_rejections'] = [{'kind': 'formation', 'reason_code': 'synthetic_open', 'spans': []}]
    store.write_bundle(envelope=envelope)
    before = deepcopy(store.get_envelope(sid))
    objects = console.snapshot_objects(sid)
    obj = next(o for o in objects if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    assert console.processing_status(sid)['formation_incomplete']
    comparisons = []
    observed_reasons = []
    original_rejections = formation.unresolved_rejections
    original = materialisation._SourceNumber.__eq__
    def count(self, other):
        comparisons.append(1)
        return original(self, other)
    instrument = os.environ.get('SCALE_COUNT', '1') == '1'
    if instrument:
        monkeypatch.setattr(materialisation._SourceNumber, '__eq__', count)
    def observe(*args, **kwargs):
        rows = original_rejections(*args, **kwargs)
        if kwargs.get('objects') is not None:
            observed_reasons.append([row.get('reason_code') for row in rows])
        return rows
    monkeypatch.setattr(formation, 'unresolved_rejections', observe)
    samples = []
    for _ in range(5):
        comparisons.clear()
        start = perf_counter()
        response = client.get('/review', params={'document': sid, 'object': obj['object_id']})
        assert response.status_code == 200 and 'data-formation-incomplete' in response.text
        samples.append({'seconds': perf_counter() - start, 'comparisons': len(comparisons) if instrument else None,
                        'bytes': len(response.content)})
    assert observed_reasons == [['synthetic_open']] * 5
    assert store.get_envelope(sid) == before
    Path(os.environ['SCALE_OUTPUT']).write_text(json.dumps({'candidate_count': len(objects),
        'comparison_instrumentation': instrument, 'samples': samples}, indent=2))
