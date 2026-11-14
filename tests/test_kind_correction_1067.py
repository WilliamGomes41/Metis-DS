"""#1067 part C: a kind corrected in the annotation card reaches the rebuilt version (fail-closed)."""
from src.review.revision_workflow import _drop_confirmation_of_another_kind


def confirmed(kind, **extra):
    return {'confirmed_object_type': kind, **extra}


def test_another_kind_drops_the_old_confirmation_and_recommendation_semantics():
    proposed = confirmed('recommendation', confirmed_recommendation_semantics={'direction': 'for'},
                         confirmed_recommendation_strength='doen')
    _drop_confirmation_of_another_kind(proposed, {'proposed_object_type': 'definition'})
    assert proposed == {}


def test_the_same_kind_keeps_every_confirmation():
    proposed = confirmed('recommendation', confirmed_recommendation_semantics={'direction': 'for'})
    before = dict(proposed)
    _drop_confirmation_of_another_kind(proposed, {'proposed_object_type': 'recommendation'})
    assert proposed == before


def test_nothing_confirmed_or_no_new_kind_changes_nothing():
    proposed = {'proposed_object_type': 'explanation'}
    _drop_confirmation_of_another_kind(proposed, {'proposed_object_type': 'definition'})
    assert proposed == {'proposed_object_type': 'explanation'}
    proposed = confirmed('explanation')
    _drop_confirmation_of_another_kind(proposed, {})
    assert proposed == confirmed('explanation')


def test_a_confirmed_relation_the_corrected_kind_cannot_hold_is_dropped():
    from src.vorming.knowledge_relation_proposal_v1 import PROPOSABLE_RELATION_TYPES, relation_endpoint_compatible
    peers = {'peer': {'confirmed_object_type': 'recommendation'}}
    kept = [kind for kind in sorted(PROPOSABLE_RELATION_TYPES)
            if relation_endpoint_compatible(kind, source_type='definition', target_type='recommendation')]
    dropped = [kind for kind in sorted(PROPOSABLE_RELATION_TYPES)
               if relation_endpoint_compatible(kind, source_type='recommendation', target_type='recommendation')
               and not relation_endpoint_compatible(kind, source_type='definition', target_type='recommendation')]
    assert dropped, 'a relation that only fits the old kind must exist for this proof'
    relations = [{'relation_type': kind, 'target_object_id': 'peer'} for kind in dropped + kept]
    proposed = confirmed('recommendation', confirmed_knowledge_relations=relations)
    _drop_confirmation_of_another_kind(proposed, {'proposed_object_type': 'definition'}, peers=peers)
    assert [r['relation_type'] for r in proposed['confirmed_knowledge_relations']] == kept


def test_a_target_corrected_in_the_same_build_is_judged_by_its_new_kind():
    from src.vorming.knowledge_relation_proposal_v1 import PROPOSABLE_RELATION_TYPES, relation_endpoint_compatible
    # A relation that fits explanation → condition but not explanation → definition.
    candidates = [kind for kind in sorted(PROPOSABLE_RELATION_TYPES)
                  if relation_endpoint_compatible(kind, source_type='explanation', target_type='condition')
                  and not relation_endpoint_compatible(kind, source_type='explanation', target_type='definition')]
    assert candidates, 'a relation that only fits the old target kind must exist for this proof'
    relation = {'relation_type': candidates[0], 'target_object_id': 'peer'}
    peers = {'peer': {'confirmed_object_type': 'condition'}}
    proposed = confirmed('recommendation', confirmed_knowledge_relations=[relation])
    _drop_confirmation_of_another_kind(proposed, {'proposed_object_type': 'explanation'}, peers=peers,
                                       next_kinds={'peer': 'definition'})
    assert proposed['confirmed_knowledge_relations'] == []


def _built_pair(production_console, tmp_path):
    from src.review.revision_workflow import current_revisions
    from tests.test_second_review_reject_1064 import four_eyes
    console, actor, sid, _, _, _, first_id, second_id = four_eyes(production_console, tmp_path)
    rows = {o['object_id']: o for o in current_revisions(console.snapshot_objects(sid, include_blocked=True), snapshot_id=sid)}
    return sid, actor, rows[first_id], rows[second_id]


def _kind(obj):
    from src.review.review_cockpit_v1 import confirmable_proposed_type
    return str(obj.get('confirmed_object_type') or confirmable_proposed_type(obj) or obj.get('object_type') or '')


def _relation_kind(source, target, *, fits=True, other=None):
    from src.vorming.knowledge_relation_proposal_v1 import PROPOSABLE_RELATION_TYPES, relation_endpoint_compatible
    for name in sorted(PROPOSABLE_RELATION_TYPES):
        ok = relation_endpoint_compatible(name, source_type=_kind(source), target_type=_kind(target))
        if ok == fits and (other is None or relation_endpoint_compatible(name, source_type=_kind(source),
                                                                           target_type=other) is not fits):
            return name
    raise AssertionError('no relation type for this proof')


def _rebuilt(b, sid, actor, *, kind=None):
    """A correction of B: a new version, with another kind only when asked."""
    from copy import deepcopy
    from src.review.revision_workflow import revise_object
    corrected = deepcopy(b)
    corrected.setdefault('metadata', {})['test_correction_1067'] = True
    if kind:
        corrected['proposed_object_type'] = kind
        corrected.pop('confirmed_object_type', None)
    return revise_object(b, corrected, snapshot_id=sid, actor=actor, reason='test correction')


def test_a_relation_to_a_rebuilt_target_is_confirmed_again(production_console, tmp_path):
    """Besluit William 2026-11-14: confirmation lapses, the proposal and its evidence follow the new target version,
    and an unchanged source becomes a new version that is reviewed again."""
    from copy import deepcopy
    from src.knowledge_relations_v1 import build_knowledge_relation
    from src.review.revision_workflow import _retarget_relations_to_rebuilt
    sid, actor, a, b = _built_pair(production_console, tmp_path)
    kind = _relation_kind(a, b)
    relation = build_knowledge_relation(source_object_id=a['object_id'], source_object_version=str(a['object_version']),
                                        relation_type=kind, target_object_id=b['object_id'],
                                        target_object_version=str(b['object_version']))
    a = deepcopy(a)
    a.update(confirmed_knowledge_relations=[relation], proposed_knowledge_relations=[relation])
    a.setdefault('metadata', {})['knowledge_relation_evidence'] = {'relations': [{
        'relation_id': relation['relation_id'], 'relation_type': kind, 'target_object_id': b['object_id'],
        'target_object_version': str(b['object_version']), 'source_spans': [], 'target_spans': [], 'evidence_spans': []}]}
    b_new = _rebuilt(b, sid, actor)
    result, unchanged = [deepcopy(a), b_new], {a['object_id']: a}
    _retarget_relations_to_rebuilt(result, {a['object_id']: a, b['object_id']: b}, unchanged,
                                   snapshot_id=sid, actor=actor)
    source = result[0]
    assert source['confirmed_knowledge_relations'] == []
    [proposal] = source['proposed_knowledge_relations']
    assert proposal['target_object_version'] == str(b_new['object_version'])
    [evidence] = source['metadata']['knowledge_relation_evidence']['relations']
    assert (evidence['relation_id'], evidence['target_object_version']) == (proposal['relation_id'],
                                                                            str(b_new['object_version']))
    assert str(source['object_version']) != str(a['object_version']), 'the unchanged source is a new version'
    assert source['governance']['validation_status'] == 'needs_review'
    assert a['object_id'] not in unchanged
    again = deepcopy(result)
    _retarget_relations_to_rebuilt(again, {a['object_id']: a, b['object_id']: b}, {}, snapshot_id=sid, actor=actor)
    assert again == result


def test_an_approved_source_with_only_a_confirmed_relation_gets_it_proposed_again(production_console, tmp_path):
    """Codex P1: approval leaves only the confirmed relation (and its legacy mirror). It must not disappear."""
    from copy import deepcopy
    from src.knowledge_relations_v1 import build_knowledge_relation, knowledge_relation_errors
    from src.review.revision_workflow import _retarget_relations_to_rebuilt
    sid, actor, a, b = _built_pair(production_console, tmp_path)
    kind = _relation_kind(a, b)
    relation = build_knowledge_relation(source_object_id=a['object_id'], source_object_version=str(a['object_version']),
                                        relation_type=kind, target_object_id=b['object_id'],
                                        target_object_version=str(b['object_version']))
    a = deepcopy(a)
    a.pop('proposed_knowledge_relations', None)
    a.update(confirmed_knowledge_relations=[relation], relations=[], confirmed_relations=[{
        'relation_type': kind, 'target_object_id': b['object_id'],
        'target_object_version': str(b['object_version']), 'confirmed': True}])
    assert knowledge_relation_errors(a) == []
    b_new = _rebuilt(b, sid, actor)
    result = [deepcopy(a), b_new]
    _retarget_relations_to_rebuilt(result, {a['object_id']: a, b['object_id']: b}, {a['object_id']: a},
                                   snapshot_id=sid, actor=actor)
    source = result[0]
    assert source['confirmed_knowledge_relations'] == [] and source['confirmed_relations'] == []
    assert [(r['relation_type'], r['target_object_version']) for r in source['proposed_knowledge_relations']] == [
        (kind, str(b_new['object_version']))], 'the lapsed confirmation is offered again'
    assert knowledge_relation_errors(source) == []


def test_a_relation_the_rebuilt_target_kind_cannot_hold_lapses_with_its_evidence(production_console, tmp_path):
    """Codex P1: when the target's corrected kind breaks the endpoint contract, the relation is not re-proposed."""
    from copy import deepcopy
    from src.knowledge_relations_v1 import build_knowledge_relation
    from src.review.revision_workflow import _retarget_relations_to_rebuilt
    sid, actor, a, b = _built_pair(production_console, tmp_path)
    new_kind = 'definition' if _kind(b) != 'definition' else 'explanation'
    kind = _relation_kind(a, b, other=new_kind)
    relation = build_knowledge_relation(source_object_id=a['object_id'], source_object_version=str(a['object_version']),
                                        relation_type=kind, target_object_id=b['object_id'],
                                        target_object_version=str(b['object_version']))
    a = deepcopy(a)
    a.update(confirmed_knowledge_relations=[relation], proposed_knowledge_relations=[relation])
    a.setdefault('metadata', {})['knowledge_relation_evidence'] = {'relations': [{
        'relation_id': relation['relation_id'], 'relation_type': kind, 'target_object_id': b['object_id'],
        'target_object_version': str(b['object_version']), 'source_spans': [], 'target_spans': [], 'evidence_spans': []}]}
    b_new = _rebuilt(b, sid, actor, kind=new_kind)
    result = [deepcopy(a), b_new]
    _retarget_relations_to_rebuilt(result, {a['object_id']: a, b['object_id']: b}, {a['object_id']: a},
                                   snapshot_id=sid, actor=actor)
    source = result[0]
    assert source['confirmed_knowledge_relations'] == [] and source['proposed_knowledge_relations'] == []
    assert source['metadata']['knowledge_relation_evidence']['relations'] == []

def test_a_proposal_the_corrected_kind_cannot_carry_is_dropped():
    """Codex P2: an unconfirmed proposal is filtered like a confirmed relation, so admission accepts the object."""
    from src.vorming.knowledge_relation_proposal_v1 import PROPOSABLE_RELATION_TYPES, relation_endpoint_compatible
    peers = {'peer': {'confirmed_object_type': 'recommendation'}}
    dropped = [kind for kind in sorted(PROPOSABLE_RELATION_TYPES)
               if relation_endpoint_compatible(kind, source_type='recommendation', target_type='recommendation')
               and not relation_endpoint_compatible(kind, source_type='definition', target_type='recommendation')]
    proposed = confirmed('recommendation', proposed_knowledge_relations=[
        {'relation_type': dropped[0], 'target_object_id': 'peer'}])
    _drop_confirmation_of_another_kind(proposed, {'proposed_object_type': 'definition'}, peers=peers)
    assert proposed['proposed_knowledge_relations'] == []
