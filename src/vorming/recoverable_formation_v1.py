"""Isolate producer errors; never repair evidence or grant publication rights.

Validated selections and failures are observations in the existing working
revision. The source register still accounts for every unselected range.
"""
from copy import deepcopy

from src.vorming.semantic_passage_v1 import (
    SemanticPassageError, semantic_units_from_proposal, attach_relation_proposals,
)
from src.vorming.source_evidence_resolution_v1 import resolve_proposal_evidence
from src.vorming.source_accountability_v1 import validate_assessments
from src.vorming.source_containers_v1 import _covers
from src.review.knowledge_path_v1 import spans_are_exact

VERSION = "recoverable-formation-v1"


def prepare(proposal, *, blocks, evidence_blocks, validator_input):
    """Return a completely revalidated subproposal plus rejected observations.

Malformed top-level envelopes are not salvageable. Candidates are isolated at
the producer boundary, before transformation/admission. Relations propagate
quarantine to both endpoints, transitively, rather than disappearing silently.
"""
    if (not isinstance(proposal, dict)
            or set(proposal) - {"objects", "relations", "abstain_reason", "source_assessments"}
            or not isinstance(proposal.get("objects"), list)
            or not isinstance(proposal.get("relations", []), list)
            or not isinstance(proposal.get("source_assessments", []), list)
            or len(proposal["objects"]) > 4096
            or len(proposal.get("relations", [])) > 8192
            or len(proposal.get("source_assessments", [])) > 8192
            or proposal.get("abstain_reason") and proposal["objects"]):
        raise SemanticPassageError("semantic_proposal_invalid")

    def resolve(value):
        return resolve_proposal_evidence(value, blocks=blocks,
            evidence_blocks=evidence_blocks, field_contract_v3=True)

    def validate(value):
        from src.vorming.knowledge_materialisation_v1 import materialise_knowledge_candidates
        decisions = semantic_units_from_proposal(**validator_input, proposal=value, include_coverage=False)
        units = materialise_knowledge_candidates(
            decisions,
            document_id=validator_input["document_id"],
            fragments=validator_input["fragments"],
        )
        attach_relation_proposals(units, raw_relations=value["relations"],
            evidence_fragments=validator_input["evidence_fragments"], object_version="1.0")

    rejected, objects, selections = [], {}, {}
    def reject(kind, index, error, spans=(), *, proposed_object_type=None, source_assessment_role=None, evidence_span=None):
        row = {"kind": kind, "index": index, "reason_code": error.code,
               "finding": deepcopy(error.finding), "spans": deepcopy(list(spans))}
        if proposed_object_type not in (None, ""):
            row["proposed_object_type"] = proposed_object_type
        if source_assessment_role not in (None, ""):
            row["source_assessment_role"] = source_assessment_role
        if isinstance(evidence_span, dict):
            # Diagnostic location only. pending_rejections() reads spans, and an
            # empty span list stays an unknown failure location.
            row["evidence_span"] = deepcopy(evidence_span)
        rejected.append(row)

    # Resolve source selections independently of field evidence. This keeps
    # failed-field locations accountable without pretending the field is valid.
    for index, obj in enumerate(proposal["objects"]):
        try:
            selections[index] = resolve(obj.get("spans", [])) if isinstance(obj, dict) else []
            one = {"objects": [obj], "relations": [], "source_assessments": [], "abstain_reason": None}
            bound = resolve(one)["objects"][0]
            if "context_evidence" not in bound:
                raise SemanticPassageError("source_bound_context_required")
            objects[index] = bound
        except SemanticPassageError as error:
            raw_type = obj.get("proposed_object_type") if isinstance(obj, dict) else None
            reject("object", index, error, selections.get(index, []),
                   proposed_object_type=raw_type)

    # Validate the joint selection once, removing only a precisely identified
    # invalid candidate and revalidating. Do not reconstruct a long document
    # separately for every object (which would consume the processing budget).
    while objects:
        try:
            validate({"objects": list(objects.values()), "relations": [],
                      "source_assessments": [], "abstain_reason": None})
        except SemanticPassageError as error:
            index = error.finding.get("candidate_index")
            if type(index) is not int or not 0 <= index < len(objects):
                raise
            original = list(objects)[index]
            raw = proposal["objects"][original]
            reject("object", original, error, selections[original],
                   proposed_object_type=raw.get("proposed_object_type") if isinstance(raw, dict) else None)
            del objects[original]
        else:
            break

    def indexed_endpoints(raw):
        """B5-h: the two distinct proposal objects a relation names by index, or None."""
        if not isinstance(raw, dict) or not {"source_object", "target_object"} <= set(raw):
            return None
        ends = (raw["source_object"], raw["target_object"])
        if (any(type(i) is not int or not 0 <= i < len(proposal["objects"]) for i in ends)
                or ends[0] == ends[1] or not all(isinstance(proposal["objects"][i], dict) for i in ends)):
            return None
        return ends

    def span_relation(raw):
        # Index endpoints become the named objects' own selections, so the
        # unchanged resolver, validator and relation attachment see exactly the
        # spans those objects selected. Unusable indexes stay unresolvable.
        ends = indexed_endpoints(raw)
        if not isinstance(raw, dict) or not {"source_object", "target_object"} & set(raw):
            return raw
        rest = {k: v for k, v in raw.items() if k not in ("source_object", "target_object")}
        if ends is None:
            return {**rest, "source_spans": [], "target_spans": []}
        return {**rest, "source_spans": deepcopy(proposal["objects"][ends[0]].get("spans")),
                "target_spans": deepcopy(proposal["objects"][ends[1]].get("spans"))}

    def endpoint_owners(raw):
        """Objects named by both relation endpoints, or None when either is unknown."""
        ends = indexed_endpoints(raw)
        if ends is not None:
            return set(ends)
        try:
            ends = [resolve(raw[key]) for key in ("source_spans", "target_spans")]
        except (SemanticPassageError, AttributeError, KeyError, TypeError):
            return None
        # Each endpoint names exactly one proposed object, and they differ.
        owners = [[i for i, spans in selections.items() if spans == end] for end in ends]
        if any(len(found) != 1 for found in owners) or owners[0] == owners[1]:
            return None
        return {owners[0][0], owners[1][0]}

    relations = []
    bad = set(range(len(proposal["objects"]))) - set(objects)
    for index, raw in enumerate(proposal.get("relations", [])):
        try:
            relation = resolve(span_relation(raw))
            ends = [relation.get(key) for key in ("source_spans", "target_spans")]
            indexed = indexed_endpoints(raw)
            owners = set(indexed) if indexed else {i for i, spans in selections.items() if spans in ends}
            if len(owners) < 2:
                raise SemanticPassageError("relation_endpoint_missing")
            relations.append((index, relation, owners))
        except (SemanticPassageError, AttributeError) as error:
            if not isinstance(error, SemanticPassageError):
                error = SemanticPassageError("knowledge_relation_invalid")
            # B5-b (#909): when both endpoints still name exactly one proposed
            # object each, only those endpoints (and, below, their dependants)
            # are quarantined. Unknown endpoints cannot establish independence:
            # quarantine this call, while an earlier validated call remains.
            endpoints = endpoint_owners(raw)
            bad.update(objects if endpoints is None else endpoints)
            reject("relation", index, error)

    while True:
        changed = False
        for index, relation, owners in relations:
            if owners & bad and not owners <= bad:
                bad.update(owners)
                changed = True
        if not changed:
            break
    for index in sorted(set(objects) & bad):
        raw = proposal["objects"][index]
        reject("object", index, SemanticPassageError("semantic_dependency_rejected"), selections[index],
               proposed_object_type=raw.get("proposed_object_type") if isinstance(raw, dict) else None)
    objects = {i: obj for i, obj in objects.items() if i not in bad}
    result = {"objects": list(objects.values()), "relations": [],
              "source_assessments": [], "abstain_reason": None}
    for index, relation, owners in relations:
        if owners & bad:
            continue
        try:
            validate({**result, "relations": [*result["relations"], relation]})
            result["relations"].append(relation)
        except SemanticPassageError as error:
            # A relation whose meaning/structure is invalid must not leave its
            # endpoint candidates apparently independent and publishable.
            reject("relation", index, error)
            bad.update(owners)
    if bad & set(objects):
        # Re-run dependency closure after semantic relation validation.
        changed = True
        while changed:
            before = set(bad)
            for _, _, owners in relations:
                if owners & bad:
                    bad.update(owners)
            changed = before != bad
        for index in sorted(set(objects) & bad):
            raw = proposal["objects"][index]
            reject("object", index, SemanticPassageError("semantic_dependency_rejected"), selections[index],
                   proposed_object_type=raw.get("proposed_object_type") if isinstance(raw, dict) else None)
        result["objects"] = [obj for i, obj in objects.items() if i not in bad]
        result["relations"] = [r for _, r, owners in relations if not owners & bad and r in result["relations"]]

    for index, raw in enumerate(proposal.get("source_assessments", [])):
        row = None
        try:
            row = resolve(raw)
            validate_assessments([*result["source_assessments"], row], blocks, result["objects"])
            result["source_assessments"].append(row)
        except (SemanticPassageError, ValueError) as error:
            if not isinstance(error, SemanticPassageError):
                error = SemanticPassageError(str(error))
            candidate = row if isinstance(row, dict) else raw if isinstance(raw, dict) else {}
            span = candidate.get("span") if isinstance(candidate.get("span"), dict) else None
            evidence_span = span if span and isinstance(span.get("block_id"), str) and type(span.get("start")) is int and type(span.get("end")) is int else None
            reject("source_assessment", index, error,
                   source_assessment_role=candidate.get("role"), evidence_span=evidence_span)
    if not result["objects"] and not result["source_assessments"]:
        result["abstain_reason"] = "no_validated_proposals"
    # Joint validation is mandatory, including conflicts between independently
    # valid objects. Failure cannot activate an inconsistent subset.
    validate(result)
    return result, {"version": VERSION, "status": "partial" if rejected else "validated",
                    "rejections": rejected, "accepted_object_count": len(result["objects"])}


def incomplete(envelope, *, objects=None, bindings=None, fragments=None):
    """Derive closure from the current source and review bundle, without writes."""
    return bool(unresolved_rejections(envelope, objects=objects, bindings=bindings, fragments=fragments))


def unresolved_rejections(envelope, *, objects=None, bindings=None, fragments=None):
    """The same exact closure decision for readiness and the problem projection."""
    replay = envelope.get("semantic_replay") or {}
    evidence = replay.get("provider_evidence") or {}
    pins=envelope.get('_document_inputs')
    if pins is not None and (bool(pins.get('replay')) != (pins.get('formation_variant')=='semantic')
            or (pins.get('formation_variant')=='semantic' and not replay)):
        return [{"kind":"formation","reason_code":"formation_evidence_unverified","spans":[]}]
    if not evidence.get("formation_incomplete"):
        return []
    pending = evidence.get("pending_rejections") or [{
        "kind": "formation", "reason_code": "source_formation_incomplete", "spans": []}]
    unverified = [{"kind": "formation", "reason_code": "formation_evidence_unverified", "spans": []}]
    if objects is None:
        return deepcopy(unverified)
    from src.vorming.semantic_replay_v1 import exact_replay_lookup, stable_json_hash, LOOKUP_HIT
    identity = replay.get("identity") or {}
    components = identity.get("components") or {}
    if (not fragments or not envelope.get("source_id") or not envelope.get("version")
            or any(not envelope.get(field) or components.get(key) != envelope[field]
                   for key, field in (("snapshot_id", "snapshot_id"),
                                      ("source_sha256", "sha256"), ("document_id", "document_id")))
            or identity.get("hash") != stable_json_hash(components)
            or exact_replay_lookup(replay, expected_identity=identity).status != LOOKUP_HIT):
        return deepcopy(unverified)
    from src.vorming.pre_review_semantic_v1 import _candidate_fragments, _evidence_fragments
    from src.vorming.semantic_passage_v1 import semantic_source_blocks
    # Source-only remainders have no proposal stamp. Pin their literal inputs
    # with the same producer fingerprint; this computes blocks, never passages.
    if stable_json_hash({
            "source_blocks": semantic_source_blocks(_candidate_fragments(fragments)),
            "evidence_blocks": semantic_source_blocks(_evidence_fragments(fragments)),
    }) != components.get("source_blocks_hash"):
        return deepcopy(unverified)
    from src.vorming.source_accountability_v1 import is_source_record
    from src.review.review_disposition_v1 import definitive_review_disposition
    from src.vorming.source_containers_v1 import source_accountability
    from src.review.source_context_review_v1 import verify_literal_source, role_of
    from src.review.review_duty_v1 import review_stage, exact_current_approver_ids
    from src.vorming.passage_register_v1 import passage_register_of
    from src.integrity_kernel import exact_review_snapshot_hash
    from src.review.four_eyes_v1 import is_forbidden_reviewer
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    review_path = review_path_for_klasse(envelope["class"])
    objects, bindings = list(objects), tuple(bindings or ())
    projection = source_accountability(objects, review_path=review_path,
                                       bindings=bindings, fragments=fragments)
    final = []
    for obj in objects:
        source = obj.get("source") or {}
        semantic = ((obj.get("metadata") or {}).get("semantic_passage") or {})
        source_blocks_hash = semantic.get("source_blocks_hash")
        if source_blocks_hash is None and is_source_record(obj):
            source_blocks_hash = components.get("source_blocks_hash")
        disposition = definitive_review_disposition(obj)
        if (not disposition["final"] or disposition["outcome"] == "superseded"
                or any(source.get(key) != envelope[field] for key, field in (
                    ("source_id", "source_id"), ("source_checksum", "sha256"), ("version", "version")))
                or source_blocks_hash != components.get("source_blocks_hash")
                or not spans_are_exact(semantic.get("spans"))
                or projection.get(obj.get("object_id"), {}).get("closure") != "accounted"
                or not verify_literal_source(obj, fragments, envelope["sha256"])):
            continue
        if disposition["outcome"] == "approved" and (
                not exact_current_approver_ids(obj, bindings)
                or review_stage(obj, review_path=review_path, bindings=bindings, fragments=fragments) is not None):
            continue
        if disposition["outcome"] != "approved":
            governance = obj.get("governance") or {}
            reviewer = str(governance.get("validated_by") or "").strip()
            if (not reviewer or is_forbidden_reviewer(reviewer)
                    or not governance.get("validation_date")
                    or (not role_of(obj)
                        and governance.get("review_snapshot_hash") != exact_review_snapshot_hash(obj))):
                continue
        if disposition["outcome"] not in {"approved", "rejected"} and passage_register_of(obj).get("source") != "review":
            # Automatic context/support classification is not human closure,
            # even when the source-accountability projection is accounted.
            continue
        final.extend(semantic["spans"])
    # Named human disposition can resolve a located rejection without deleting
    # the original model error. Unknown scope cannot be resolved by assumption.
    return [deepcopy(r) for r in pending if not spans_are_exact(r.get("spans")) or not all(
        _covers(ref, final) for ref in r["spans"])]


def _whitespace_only(spans, by_id):
    """Only verified, nonempty exact ranges of literal whitespace are inert."""
    if not spans_are_exact(spans):
        return False
    return all(span["block_id"] in by_id
        and 0 <= span["start"] < span["end"] <= len(by_id[span["block_id"]])
        and not by_id[span["block_id"]][span["start"]:span["end"]].strip() for span in spans)


def pending_rejections(evidence, proposal, *, blocks=None):
    """Historical rejection is resolved only by a validated covering selection.

    The caller must supply the joint source-validated proposal and its evidence
    from one pinned preparation/replay. Block offsets alone do not bind a source.
    Unknown failure locations remain open; a new successor may re-evaluate the
    entire source. A successful HTTP call alone never clears a formation error.
    """
    selected = [s for o in proposal.get("objects", []) if spans_are_exact(o.get("spans")) for s in o["spans"]]
    selected += [r["span"] for r in proposal.get("source_assessments", []) if spans_are_exact([r.get("span")])]
    pending = []
    calls = [evidence, *evidence.get("supplementary_calls", [])]
    for index, call in enumerate(calls):
        # A bounded transport/budget failure can be answered by a later fully
        # validated task, including an explicit abstention. Its unknown source
        # still blocks source closure; it is no longer an unexecuted task.
        answered = False
        if evidence.get("task_policy") == "bounded-formation-v1" and call.get("target_spans"):
            later_spans = [s for later in calls[index + 1:]
                if later.get("task_id") and not later.get("error_code")
                and (later.get("formation") or {}).get("status") == "validated"
                and not (later.get("formation") or {}).get("rejections")
                if spans_are_exact(later.get("target_spans"))
                for s in later["target_spans"]]
            answered = spans_are_exact(call["target_spans"]) and all(_covers(ref, later_spans) for ref in call["target_spans"])
        if call.get("error_code") and not answered:
            pending.append({"kind": "call", "reason_code": call.get("failure_reason") or call["error_code"],
                            "spans": call.get("target_spans", [])})
        pending.extend(deepcopy((call.get("formation") or {}).get("rejections", [])))
    # A call-level error may be recovered only when all its explicit source
    # targets are covered. Unknown-location errors still require successor work.
    by_id = {block["block_id"]: block["text"] for block in blocks or []}
    return [r for r in pending if not _whitespace_only(r.get("spans"), by_id)
        and (r.get("requires_review") or not spans_are_exact(r.get("spans")) or not all(
            _covers(ref, selected) for ref in r["spans"]))]


def restrict_supplement(proposal, *, primary, targets):
    """Isolate out-of-target/conflicting reselections without overwriting work."""
    result, rejections, removed = deepcopy(proposal), [], []
    kept = []
    for index, obj in enumerate(proposal["objects"]):
        same = next((o for o in primary["objects"] if o["spans"] == obj["spans"]), None)
        if same == obj:
            # An exact duplicate is already represented, not new source work.
            continue
        inside = all(any(t["span"]["block_id"] == s["block_id"]
            and t["span"]["start"] <= s["start"] < s["end"] <= t["span"]["end"]
            for t in targets) for s in obj["spans"])
        if same is not None or not inside:
            removed.append(obj["spans"])
            rejections.append({"kind": "object", "index": index, "spans": obj["spans"],
                "proposed_object_type": obj.get("proposed_object_type"),
                "requires_review": same is not None,
                "reason_code": "semantic_supplement_conflict" if same is not None else "semantic_supplement_outside_target"})
        else:
            kept.append(obj)
    # Propagate dependencies of excluded supplemental selections.
    changed = True
    while changed:
        changed = False
        for relation in result["relations"]:
            ends = [relation["source_spans"], relation["target_spans"]]
            if any(s in removed for s in ends):
                for obj in kept[:]:
                    if obj["spans"] in ends:
                        kept.remove(obj)
                        removed.append(obj["spans"])
                        rejections.append({"kind": "object", "spans": obj["spans"],
                                           "proposed_object_type": obj.get("proposed_object_type"),
                                           "reason_code": "semantic_dependency_rejected"})
                        changed = True
    result["objects"] = kept
    result["relations"] = [r for r in result["relations"]
        if r["source_spans"] not in removed and r["target_spans"] not in removed]
    assessments = []
    for row in result["source_assessments"]:
        ref = row["span"]
        if any(t["span"]["block_id"] == ref["block_id"]
               and t["span"]["start"] <= ref["start"] < ref["end"] <= t["span"]["end"] for t in targets):
            assessments.append(row)
        else:
            rejections.append({"kind": "source_assessment", "spans": [ref],
                               "source_assessment_role": row.get("role"),
                               "reason_code": "semantic_supplement_outside_target"})
    result["source_assessments"] = assessments
    result["abstain_reason"] = None if kept or assessments else "no_validated_proposals"
    return result, rejections


def preserve_unchanged(objects, previous):
    """Keep exact candidate versions when only bundle-level origin hashes moved.

    Any change to content, fields, context, relations, governance or source
    prevents reuse. This does not transfer approvals to a changed candidate.
    """
    def comparable(obj):
        result = deepcopy(obj)
        provenance = result.get("provenance") or {}
        for field in ("semantic_spec_hash", "content_hash", "canonical_object_hash"):
            provenance.pop(field, None)
        ((result.get("metadata") or {}).get("semantic_passage") or {}).pop("proposal_hash", None)
        return result
    by_id = {o["object_id"]: o for o in previous}
    return [deepcopy(by_id[obj["object_id"]]) if obj["object_id"] in by_id
            and comparable(obj) == comparable(by_id[obj["object_id"]]) else obj for obj in objects]
