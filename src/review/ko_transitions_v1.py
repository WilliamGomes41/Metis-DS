"""One read-only transition policy inside the existing atomic KO commands."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterable

from src.knowledge_relations_v1 import confirmed_knowledge_relations_of
from src.review.knowledge_object_state_v1 import (
    KO_STATES, GEPUBLICEERD, INGETROKKEN, VERVANGEN, AFGEWEZEN,
    GOEDGEKEURD, TWEEDE_REVIEW, derive_ko_state, is_knowledge_object,
    EVIDENCE_RELATION_TYPES,
)

EVIDENCE_VERSION = 'ko-supporting-evidence-v1'
EVENTS = ('approve', 'approve_second', 'reject', 'later', 'confirm_type',
          'correct', 'link_support', 'supersede_merge')
ALLOWED_FINAL_BY_SUITABILITY = {
    'ja': {'approve', 'revise', 'reject'},
    'mist_context': {'revise', 'reject'},
    'samenvoegen': {'revise', 'reject'},
    'alleen_onderbouwing': {'revise', 'approve', 'reject'},
    'geen_kenniseenheid': {'reject'},
}
APPROVAL_ONLY_FIELDS = (
    'confirmed_object_type', 'recommendation_strength', 'recommendation_direction',
    'recommendation_strength_level', 'documentpositie_action', 'parent_choice', 'type_action',
)


@dataclass(frozen=True)
class Transition:
    event: str
    target: str


_MUTABLE = frozenset(KO_STATES) - {GEPUBLICEERD, INGETROKKEN, VERVANGEN}
TRANSITIONS = {
    (state, event): Transition(event, 'derived_open_revision' if event in
        {'confirm_type', 'correct', 'link_support'} else
        GOEDGEKEURD if event in {'approve', 'approve_second'} else
        AFGEWEZEN if event == 'reject' else VERVANGEN if event == 'supersede_merge' else state)
    for state in _MUTABLE for event in EVENTS
    if (event != 'approve_second' or state == TWEEDE_REVIEW)
    and (event != 'approve' or state in {'Kandidaat', 'Bewijs open', 'In review', 'Samengesteld'})
    and (event not in {'reject', 'later'} or state not in {GOEDGEKEURD, AFGEWEZEN, TWEEDE_REVIEW})
}


def _refuse(code: str, message: str = ''):
    from src.operations_console_v1 import ConsoleError
    raise ConsoleError(code, message or None)


def require_assessment(value: Any) -> dict[str, Any]:
    from src.review.review_assessment_v1 import ReviewAssessment
    if isinstance(value, ReviewAssessment):
        parsed = value
    else:
        parsed = ReviewAssessment.from_evidence(value)
    if parsed is None:
        _refuse('review_assessment_required', 'Beantwoord de drie vragen voordat je goedkeurt.')
    if not parsed.all_yes:
        _refuse('review_assessment_requires_three_yes',
                'Voor goedkeuren moeten de drie antwoorden Ja zijn. Kies anders Correctie nodig.')
    return parsed.as_evidence()


def confirmed_support(obj: dict[str, Any], objects: Iterable[dict[str, Any]]) -> bool:
    peers = {str(row.get('object_id') or ''): row for row in objects}
    for relation in confirmed_knowledge_relations_of(obj):
        if relation.get('relation_type') not in EVIDENCE_RELATION_TYPES:
            continue
        peer = peers.get(str(relation.get('target_object_id') or ''))
        if (peer is not None and peer.get('object_id') != obj.get('object_id')
                and str(peer.get('object_version') or '') == str(relation.get('target_object_version') or '')
                and (peer.get('content') or {}).get('clean_text')
                and (peer.get('governance') or {}).get('validation_status') not in {'rejected', 'superseded'}):
            return True
    return False


def supporting_evidence(obj, objects, *, not_applicable=False):
    if type(not_applicable) is not bool:
        _refuse('supporting_evidence_choice_invalid')
    if not_applicable:
        return {'version': EVIDENCE_VERSION, 'applicability': 'not_applicable'}
    if not confirmed_support(obj, objects):
        _refuse('knowledge_evidence_required', 'Dit kennisobject heeft nog geen onderbouwing.')
    return {'version': EVIDENCE_VERSION, 'applicability': 'linked'}


def recorded_not_applicable(obj, bindings):
    from src.publication.publish_authorization_v1 import still_matches
    return any(row.get('decision') == 'approve' and still_matches(row, obj)
        and row.get('supporting_evidence') == {
            'version': EVIDENCE_VERSION, 'applicability': 'not_applicable'} for row in bindings)


def apply_ko_event(*, current, event, review_path, bindings=(), fragments=None,
                   prepared=None, objects=(), assessment=None, evidence_not_applicable=False):
    """Authorize captured facts; the enclosing command retains its writer/transaction."""
    if event not in EVENTS:
        _refuse('ko_event_unknown')
    if not is_knowledge_object(current, review_path):
        return {}
    state = derive_ko_state(current, review_path=review_path, bindings=bindings,
                            fragments=fragments)['state']
    transition = TRANSITIONS.get((state, event))
    if transition is None or (state == 'Kandidaat' and event == 'approve' and review_path != 'boom'):
        _refuse('ko_transition_refused', f'De handeling {event} is niet toegestaan bij {state}.')
    if event in {'approve', 'approve_second'}:
        return {'assessment': require_assessment(assessment),
                'supporting_evidence': supporting_evidence(prepared or current, objects,
                    not_applicable=evidence_not_applicable)}
    return {}


def require_allowed_review_disposition(submission):
    from src.review.review_cockpit_v1 import map_eindoordeel
    suitability = str(submission.get('suitability') or '').strip()
    if not suitability:
        return
    decision = map_eindoordeel(str(submission.get('eindoordeel') or ''),
                              str(submission.get('decision') or ''))
    if decision == 'later':
        return
    if decision not in ALLOWED_FINAL_BY_SUITABILITY.get(suitability, ()):
        from src.review.closed_review_loop_v1 import ReviewDispositionConflict
        raise ReviewDispositionConflict(suitability, decision)


def without_closed_follow_up(submission):
    allowed = ALLOWED_FINAL_BY_SUITABILITY.get(str(submission.get('suitability') or '').strip())
    if allowed is None:
        return dict(submission)
    kept = dict(submission)
    if 'approve' not in allowed:
        kept.update(dict.fromkeys(APPROVAL_ONLY_FIELDS))
        kept['relation_choices'] = None
        kept['relation_review_ack'] = False
    if 'revise' not in allowed:
        kept['source_discrepancy'] = None
    return kept


@dataclass(frozen=True)
class RepairCommand:
    actor_id: str
    snapshot_id: str
    object_id: str
    suitability: str


_ACTIVE_REPAIR: ContextVar[RepairCommand | None] = ContextVar('ko_validated_repair', default=None)


@contextmanager
def validated_repair(submission):
    token = _ACTIVE_REPAIR.set(RepairCommand(*(str(submission[key]) for key in
        ('actor_id', 'snapshot_id', 'object_id', 'suitability'))))
    try:
        yield
    finally:
        _ACTIVE_REPAIR.reset(token)


def active_repair(actor_id, snapshot_id, object_id):
    value = _ACTIVE_REPAIR.get()
    return value if value and (value.actor_id, value.snapshot_id, value.object_id) == (
        actor_id, snapshot_id, object_id) else None
