"""Three explicit review answers over the proposal presented by the existing kernel."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.operations_console_v1 import ConsoleError
from src.review.review_cockpit_v1 import confirmable_proposed_type, found_under_path
from src.review.knowledge_relation_review_v1 import (
    plan_semantic_relation_review, relation_choice_value,
    semantic_confirmed_relations, semantic_proposed_relations,
)
from src.vorming.recommendation_semantics_v1 import (
    confirmed_recommendation_semantics_from_review,
    confirmed_recommendation_semantics_of, proposed_recommendation_semantics_of,
    validate_recommendation_semantics, PROPOSED_FIELD, CONFIRMED_FIELD,
)

ASSESSMENT_VERSION = 'review-assessment-v1'
ANSWER_FIELDS = ('applicable', 'complete', 'placed_correctly')


@dataclass(frozen=True)
class ReviewAssessment:
    applicable: str | None
    complete: str | None
    placed_correctly: str | None

    def __post_init__(self):
        if any(getattr(self, field) not in (None, 'yes', 'adjust') for field in ANSWER_FIELDS):
            raise ValueError('review_assessment_answer_invalid')

    @property
    def all_yes(self) -> bool:
        return all(getattr(self, field) == 'yes' for field in ANSWER_FIELDS)

    @classmethod
    def from_values(cls, applicable='', complete='', placed_correctly=''):
        return cls(*(None if value is None else str(value).strip() or None for value in
                     (applicable, complete, placed_correctly)))

    def as_evidence(self) -> dict[str, Any]:
        return {'version': ASSESSMENT_VERSION,
                **{field: getattr(self, field) for field in ANSWER_FIELDS}}

    @classmethod
    def from_evidence(cls, record):
        if not isinstance(record, dict) or record.get('version') != ASSESSMENT_VERSION:
            return None
        if not all(field in record for field in ANSWER_FIELDS):
            return None
        try:
            return cls(*(record[field] for field in ANSWER_FIELDS))
        except (ValueError, TypeError):
            return None


@dataclass(frozen=True)
class DisplayedReviewDescriptor:
    object_id: str
    object_version: str
    text: str
    object_type: str
    direction: str
    strength_choice: str
    parent_id: str
    found_under: str
    relation_choices: tuple[str, ...]
    relations: tuple[dict, ...]
    issues: tuple[str, ...]
    outcome_strength: str = ''
    outcome_no_action: bool = False
    legacy_recommendation_strength: str = ''

    @property
    def can_confirm(self) -> bool:
        return not self.issues


def _recommendation_values(focal, object_type):
    if object_type != 'recommendation':
        return '', '', [], ''
    if PROPOSED_FIELD not in focal and CONFIRMED_FIELD not in focal:
        from src.object_taxonomy_v1 import is_closed_recommendation_strength
        legacy = str(focal.get('confirmed_recommendation_strength')
                     or focal.get('proposed_recommendation_strength') or '')
        if is_closed_recommendation_strength(legacy):
            return '', '', [], legacy
        return '', '', ['recommendation_semantics_required'], ''
    semantics = (confirmed_recommendation_semantics_of(focal)
                 or proposed_recommendation_semantics_of(focal))
    errors = validate_recommendation_semantics(semantics) if semantics else ['recommendation_semantics_required']
    direction = str(semantics.get('direction') or '')
    strength = ('not_stated' if semantics.get('strength_status') == 'not_stated'
                else str(semantics.get('strength') or ''))
    if semantics.get('strength_status') == 'unmapped':
        errors.append('recommendation_strength_confirmation_required')
    if not errors:
        try:
            confirmed_recommendation_semantics_from_review(
                focal, direction=direction, strength_choice=strength)
        except ValueError as error:
            errors.append(str(error))
    return direction, strength, errors, ''


def _outcome_values(focal, object_type):
    if object_type != 'outcome':
        return '', False, []
    from src.object_taxonomy_v1 import is_closed_recommendation_strength
    from src.review.beslisboom_path_v1 import is_geen_actie_outcome
    strength = str(focal.get('confirmed_recommendation_strength')
                   or focal.get('proposed_recommendation_strength') or '')
    no_action = is_geen_actie_outcome(str((focal.get('content') or {}).get('clean_text') or ''))
    if strength:
        issues = [] if is_closed_recommendation_strength(strength) else ['unknown_recommendation_strength']
    else:
        issues = [] if no_action else ['outcome_strength_required']
    return strength, no_action, issues


def displayed_review_descriptor(
    focal: dict[str, Any], objects: Iterable[dict[str, Any]], review_path: str,
    *, bindings=(), fragments=None, stage=None,
) -> DisplayedReviewDescriptor:
    """Project precisely the type, semantics and relation basis a reviewer endorses."""
    rows = list(objects)
    object_type = str(focal.get('confirmed_object_type') or confirmable_proposed_type(focal)
                      or focal.get('object_type') or '')
    from src.object_taxonomy_v1 import is_closed_confirmed_type
    from src.review.beslisboom_path_v1 import CLOSED_BOOM_TYPES
    known_type = (object_type in CLOSED_BOOM_TYPES if review_path == 'boom'
                  else is_closed_confirmed_type(object_type))
    issues = [] if known_type else ['review_type_required']
    direction, strength, semantic_errors, legacy_strength = _recommendation_values(focal, object_type)
    issues.extend(semantic_errors)
    outcome_strength, outcome_no_action, outcome_errors = _outcome_values(focal, object_type)
    issues.extend(outcome_errors)
    proposed = semantic_proposed_relations(focal) if stage != 'second_review' else []
    basis = proposed or semantic_confirmed_relations(focal)
    choices = tuple(relation_choice_value(relation) for relation in basis)
    by_id = {str(row.get('object_id') or ''): row for row in rows}
    relations = []
    for relation in basis:
        target_id = str(relation.get('target_object_id') or '')
        target_version = str(relation.get('target_object_version') or '')
        target = by_id.get(target_id)
        resolution = ('missing' if target is None else 'current' if
                      str(target.get('object_version') or '') == target_version else 'version_mismatch')
        text = str((target.get('content') or {}).get('clean_text') or '') if target else ''
        if not text and resolution == 'current':
            resolution = 'missing'
        if resolution != 'current':
            issues.append('knowledge_relation_target_' + resolution)
        relations.append({
            'relation_type': str(relation.get('relation_type') or ''),
            'authority': 'proposed' if proposed else 'confirmed',
            'resolution': resolution,
            'target': {'object_id': target_id, 'object_version': target_version,
                       'id': target_id, 'version': target_version, 'text': text,
                       'origin': found_under_path(target) if target else ''},
        })
    if stage != 'second_review':
        try:
            plan_semantic_relation_review(focal, objects=rows,
                selected_choices=choices, source_type=object_type)
        except ValueError as error:
            issues.append(str(error))
    return DisplayedReviewDescriptor(
        str(focal.get('object_id') or ''), str(focal.get('object_version') or ''),
        str((focal.get('content') or {}).get('clean_text') or ''), object_type,
        direction, strength, str(focal.get('parent_object_id') or ''),
        found_under_path(focal), choices, tuple(relations), tuple(dict.fromkeys(issues)),
        outcome_strength=outcome_strength, outcome_no_action=outcome_no_action,
        legacy_recommendation_strength=legacy_strength)


def compact_approval_arguments(
    assessment: ReviewAssessment, descriptor: DisplayedReviewDescriptor,
) -> dict[str, Any]:
    """Translate explicit consent to the displayed proposal into existing kernel inputs."""
    if not assessment.all_yes:
        raise ConsoleError('review_assessment_approval_requires_yes')
    if not descriptor.can_confirm:
        raise ConsoleError(descriptor.issues[0])
    arguments = {
        'confirmed_object_type': descriptor.object_type,
        'type_action': 'dit_klopt', 'suitability': 'ja', 'eindoordeel': 'goedkeuren',
        'documentpositie_action': 'dit_klopt', 'parent_choice': descriptor.parent_id or None,
        'found_under': descriptor.found_under or None,
        'relation_choices': list(descriptor.relation_choices), 'relation_review_ack': True,
    }
    if descriptor.object_type == 'recommendation':
        if descriptor.legacy_recommendation_strength:
            arguments['recommendation_strength'] = descriptor.legacy_recommendation_strength
        else:
            arguments.update(recommendation_direction=descriptor.direction,
                             recommendation_strength_level=descriptor.strength_choice)
    if descriptor.object_type == 'outcome' and descriptor.outcome_strength:
        arguments['recommendation_strength'] = descriptor.outcome_strength
    return arguments
