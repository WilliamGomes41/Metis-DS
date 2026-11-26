"""#1067 part C, besluit William 2026-11-14, end to end on native PostgreSQL.

A reviewer confirms a relation from A to B and approves A. B is corrected in the annotation card and rebuilt through
the production build. Then A's confirmation has lapsed, the relation is proposed again for B's new version, A is a new
version back in review that admission accepts, and the reviewer can confirm the relation again and approve A.

A human annotation build makes no relation proposals of its own; Metis' semantic producer does. The test therefore
wraps the materialiser so it proposes A -> B, deterministically, in the build and in its replay. Everything else runs
through the production build, review, correction and rebuild commands; the database refuses direct writes.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

from src.knowledge_relations_v1 import build_knowledge_relation, knowledge_relation_errors
from src.review.knowledge_relation_review_v1 import relation_choice_value
from src.review.review_cockpit_v1 import confirmable_proposed_type
from src.review.revision_workflow import current_revisions
from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_v1 as annotation
from src.vorming.admission_gate_v1 import admission_of
from src.vorming.knowledge_relation_proposal_v1 import (PROPOSABLE_RELATION_TYPES, RELATION_EVIDENCE_VERSION,
                                                          relation_endpoint_compatible)
from tests.ko_review_fixture_support import affirmative_assessment
from tests.test_human_annotation_review_postgres import correction_request
from tests.test_second_review_reject_1064 import four_eyes


def _current(console, sid, oid):
    rows = current_revisions(console.snapshot_objects(sid, include_blocked=True), snapshot_id=sid)
    return next(o for o in rows if o['object_id'] == oid)


def _kind(obj):
    return str(obj.get('confirmed_object_type') or confirmable_proposed_type(obj) or '')


def _approve_with_relation(console, sid, oid, actor, choices):
    from src.vorming.human_annotation_projection_v1 import has_literal_support
    obj = _current(console, sid, oid)
    console.review_object(actor_id=actor, snapshot_id=sid, object_id=oid, decision='approve',
        confirmed_object_type=_kind(obj), assessment=affirmative_assessment(),
        evidence_not_applicable=not has_literal_support(obj, console.review_source_fragments(sid)),
        relation_choices=choices, relation_review_ack=True, expected_revision=console.objects_revision(sid))


def _propose_a_to_b(monkeypatch):
    """Metis' producer proposes a relation from the second claim (A) to the first (B) on every build."""
    from src.vorming import human_annotation_materialisation_v1 as materialisation
    original = materialisation.build_objects

    def build_objects(seal, entries, *, fragments):
        objects = original(seal, entries, fragments=fragments)
        a = next((o for o in objects if o['content']['clean_text'].startswith('De beoordeling')), None)
        b = next((o for o in objects if o['content']['clean_text'].startswith('De kwetsbare huid')), None)
        if a and b:
            kind = next(name for name in sorted(PROPOSABLE_RELATION_TYPES)
                        if relation_endpoint_compatible(name, source_type=_kind(a), target_type=_kind(b)))
            relation = build_knowledge_relation(source_object_id=a['object_id'],
                source_object_version=str(a['object_version']), relation_type=kind,
                target_object_id=b['object_id'], target_object_version=str(b['object_version']))
            # As Metis' producer does: a proposal always carries source-bound evidence.
            def span(obj):
                core = next(r for r in obj['metadata']['human_annotation']['ranges'] if r['role'] == 'core')
                return {'block_id': core['block_id'], 'start': core['start'], 'end': core['end'],
                        'source_fragment_ids': [core['block_id']]}
            a.setdefault('metadata', {})['knowledge_relation_evidence'] = {
                'version': RELATION_EVIDENCE_VERSION, 'relations': [{
                    'relation_id': relation['relation_id'], 'relation_type': kind,
                    'target_object_id': b['object_id'], 'target_object_version': str(b['object_version']),
                    'source_spans': [span(a)], 'target_spans': [span(b)], 'evidence_spans': [span(a)]}]}
            a['proposed_knowledge_relations'] = [relation]
            a['relations'] = [{'relation_type': kind, 'target_object_id': b['object_id'],
                               'target_object_version': str(b['object_version']), 'confirmed': False}]
            from src.integrity_kernel import stamp_canonical_hashes
            stamp_canonical_hashes(a)
        return objects
    monkeypatch.setattr(materialisation, 'build_objects', build_objects)


def test_a_relation_to_a_corrected_target_is_confirmed_again_end_to_end(production_console, tmp_path, monkeypatch):
    _propose_a_to_b(monkeypatch)
    console, _actor, sid, original, first, _second, b_id, a_id = four_eyes(production_console, tmp_path)
    a, b = _current(console, sid, a_id), _current(console, sid, b_id)
    [proposal] = a['proposed_knowledge_relations']
    kind = proposal['relation_type']
    assert proposal['target_object_version'] == str(b['object_version'])

    # 1. The reviewer confirms the relation and approves A.
    _approve_with_relation(console, sid, a_id, first, [relation_choice_value(proposal)])
    approved = _current(console, sid, a_id)
    assert [(r['relation_type'], r['target_object_version']) for r in approved['confirmed_knowledge_relations']] == [
        (kind, str(b['object_version']))]
    assert approved['governance']['validation_status'] == 'approved'

    # 2. B is corrected in the annotation card and rebuilt through the production build.
    request = correction_request(console, sid, original)
    next(r for r in request['selection']['ranges'] if r['role'] == 'evidence')['evidence_function'] = 'explains'
    saved = annotation.save(console, actor_id=first, **request)
    from tests.test_human_annotation_build_postgres import closing
    request = closing(build.overview(console, actor_id=first, snapshot_id=sid))
    assert request['expected_generation'] == saved['generation']
    result = build.finalize(console, actor_id=first, **{**request, 'command_id': 'relation-target-correction'})
    from src.vorming.worker_handover_v1 import native_attempt
    console.execute_source_selection(actor_id=first, snapshot_id=sid,
                                     attempt=native_attempt(console, sid, result['attempt_id']))
    b_new = _current(console, sid, b_id)
    assert str(b_new['object_version']) != str(b['object_version'])

    # 3. A's confirmation lapsed; the relation is proposed again for B's new version; A is reviewed again.
    a_new = _current(console, sid, a_id)
    assert str(a_new['object_version']) != str(approved['object_version']), 'A is a new version'
    assert a_new['metadata']['revision_lineage']['previous_object_version'] == str(approved['object_version'])
    assert a_new['governance']['validation_status'] == 'needs_review'
    assert not a_new.get('confirmed_knowledge_relations')
    [again] = a_new['proposed_knowledge_relations']
    assert (again['relation_type'], again['target_object_version']) == (kind, str(b_new['object_version']))
    assert knowledge_relation_errors(a_new) == []
    # Codex P2: the relation review of the approved version stays on that version; nobody reviewed this one yet.
    assert 'knowledge_relation_review' in approved['metadata']
    assert 'knowledge_relation_review' not in a_new['metadata']
    assert admission_of(a_new)['gate_result'] == 'allowed', admission_of(a_new)

    # 4. The reviewer confirms the relation again and approves A.
    _approve_with_relation(console, sid, a_id, first, [relation_choice_value(again)])
    final = _current(console, sid, a_id)
    assert final['governance']['validation_status'] == 'approved'
    assert [(r['relation_type'], r['target_object_version']) for r in final['confirmed_knowledge_relations']] == [
        (kind, str(b_new['object_version']))]
    receipt = final['metadata']['knowledge_relation_review']
    assert receipt['source_object_version_after'] == str(final['object_version'])
    assert deepcopy(final) == _current(console, sid, a_id)
