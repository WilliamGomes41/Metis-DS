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
