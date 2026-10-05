"""Isolate producer errors; never repair evidence or grant publication rights.

Validated selections and failures are observations in the existing working
revision. The source register still accounts for every unselected range.
"""
from copy import deepcopy

from src.semantic_passage_v1 import (
    SemanticPassageError, semantic_units_from_proposal, attach_relation_proposals,
)
from src.source_evidence_resolution_v1 import resolve_proposal_evidence
from src.source_accountability_v1 import validate_assessments

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
        units = semantic_units_from_proposal(**validator_input, proposal=value, include_coverage=False)
        attach_relation_proposals(units, raw_relations=value["relations"],
            evidence_fragments=validator_input["evidence_fragments"], object_version="1.0")

    rejected, objects, selections = [], {}, {}
    def reject(kind, index, error, spans=()):
        rejected.append({"kind": kind, "index": index, "reason_code": error.code,
                         "finding": deepcopy(error.finding), "spans": deepcopy(list(spans))})

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
            reject("object", index, error, selections.get(index, []))

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
            reject("object", original, error, selections[original])
            del objects[original]
        else:
            break

    relations = []
    bad = set(range(len(proposal["objects"]))) - set(objects)
    for index, raw in enumerate(proposal.get("relations", [])):
        try:
            relation = resolve(raw)
            ends = [relation.get(key) for key in ("source_spans", "target_spans")]
            owners = {i for i, spans in selections.items() if spans in ends}
            if len(owners) < 2:
                raise SemanticPassageError("relation_endpoint_missing")
            relations.append((index, relation, owners))
        except (SemanticPassageError, AttributeError) as error:
            if not isinstance(error, SemanticPassageError):
                error = SemanticPassageError("knowledge_relation_invalid")
            # Unknown endpoints cannot establish independence. Quarantine this
            # call, while an already validated earlier call remains available.
            bad.update(objects)
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
        reject("object", index, SemanticPassageError("semantic_dependency_rejected"), selections[index])
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
            reject("object", index, SemanticPassageError("semantic_dependency_rejected"), selections[index])
        result["objects"] = [obj for i, obj in objects.items() if i not in bad]
        result["relations"] = [r for _, r, owners in relations if not owners & bad and r in result["relations"]]

    for index, raw in enumerate(proposal.get("source_assessments", [])):
        try:
            row = resolve(raw)
            validate_assessments([*result["source_assessments"], row], blocks, result["objects"])
            result["source_assessments"].append(row)
        except (SemanticPassageError, ValueError) as error:
            if not isinstance(error, SemanticPassageError):
                error = SemanticPassageError(str(error))
            reject("source_assessment", index, error)
    if not result["objects"] and not result["source_assessments"]:
        result["abstain_reason"] = "no_validated_proposals"
    # Joint validation is mandatory, including conflicts between independently
    # valid objects. Failure cannot activate an inconsistent subset.
    validate(result)
    return result, {"version": VERSION, "status": "partial" if rejected else "validated",
                    "rejections": rejected, "accepted_object_count": len(result["objects"])}


def incomplete(envelope, *, objects=None):
    evidence = (envelope.get("semantic_replay") or {}).get("provider_evidence") or {}
    if not evidence.get("formation_incomplete"):
        return False
    if objects is None:
        return True
    from src.review_disposition_v1 import definitive_review_disposition
    final = [s for obj in objects if definitive_review_disposition(obj)["final"]
             for s in ((obj.get("metadata") or {}).get("semantic_passage") or {}).get("spans", [])]
    pending = evidence.get("pending_rejections") or []
    # Named human disposition can resolve a located rejection without deleting
    # the original model error. Unknown scope cannot be resolved by assumption.
    return not pending or any(not r.get("spans") or not all(any(
        s["block_id"] == ref["block_id"] and s["start"] <= ref["start"] and s["end"] >= ref["end"]
        for s in final) for ref in r["spans"]) for r in pending)


def pending_rejections(evidence, proposal):
    """Historical rejection is resolved only by a validated covering selection.

    Unknown failure locations remain open; a new successor may re-evaluate the
    entire source. A successful HTTP call alone never clears a formation error.
    """
    selected = [s for o in proposal.get("objects", []) for s in o["spans"]]
    selected += [r["span"] for r in proposal.get("source_assessments", [])]
    pending = []
    for call in [evidence, *evidence.get("supplementary_calls", [])]:
        if call.get("error_code"):
            pending.append({"kind": "call", "reason_code": call.get("failure_reason") or call["error_code"],
                            "spans": call.get("target_spans", [])})
        for rejection in (call.get("formation") or {}).get("rejections", []):
            spans = rejection.get("spans", [])
            if rejection.get("requires_review") or not spans or not all(any(s["block_id"] == ref["block_id"]
                    and s["start"] <= ref["start"] and s["end"] >= ref["end"]
                    for s in selected) for ref in spans):
                pending.append(deepcopy(rejection))
    # A call-level error may be recovered only when all its explicit source
    # targets are covered. Unknown-location errors still require successor work.
    return [r for r in pending if r.get("requires_review") or not r.get("spans") or not all(any(
        s["block_id"] == ref["block_id"] and s["start"] <= ref["start"] and s["end"] >= ref["end"]
        for s in selected) for ref in r["spans"])]


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
