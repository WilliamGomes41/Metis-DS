"""Native source ingress preserves the actual unlinked admission neighbours.

# release-control-evidence: scope/belofte opslag stale recovery kwaliteit slop releasebewijs
"""
from copy import deepcopy

from src.vorming import admission_gate_v1 as gate
from tests.test_source_context_review_v1 import _system


def test_scoped_source_readmission_matches_full_bundle_with_unlinked_condition(
    tmp_path, production_console, monkeypatch,
):
    condition = 'Bij een ernstige nierfunctiestoornis is extra controle nodig.'
    html = ('<html><body><h1>Zorg</h1><h2>1 Ondersteuning</h2><p>DOEN</p><p>' + condition +
        '</p><p>Een observatie is een systematische waarneming van gedrag.</p></body></html>').encode()
    state, _, _, source, target, command = _system(tmp_path, production_console=production_console, source_html=html)
    sid = command['snapshot_id']
    whole = deepcopy(state.snapshot_objects(sid))
    original, observed = gate.apply_admission_gate, []

    def parity(proposed, **kwargs):
        by_id = {obj['object_id']: obj for obj in proposed}
        expected_bundle = [by_id.get(obj['object_id'], obj) for obj in whole]
        ordered = sorted(proposed, key=lambda obj: (obj.get('structure') or {}).get('sequence', 0))
        index = next(i for i, obj in enumerate(ordered) if obj['object_id'] == target['object_id'])
        assert gate._paragraph_neighbor_text(ordered, index, -1) == condition
        expected = original(expected_bundle, **kwargs)
        actual = original(proposed, **kwargs)
        expected_target = next(obj for obj in expected if obj['object_id'] == target['object_id'])
        actual_target = next(obj for obj in actual if obj['object_id'] == target['object_id'])
        assert actual_target['metadata']['admission'] == expected_target['metadata']['admission']
        observed.append(True)
        return actual
    monkeypatch.setattr(gate, 'apply_admission_gate', parity)
    result = state.confirm_source_context(**command)
    assert result['role'] == 'label' and observed
