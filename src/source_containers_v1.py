"""Typed revision containers and exact source usage, derived from one durable bundle.

No approval or serving authority lives here. Legacy source records keep their
old human-disposition policy. New records may account for narrowly recognized
document information and validated, current target context.
"""
import re

from src.source_accountability_v1 import evidence_of, is_source_record, CONTAINERS_VERSION
from src.source_bound_fields_v2 import context_matches_target, CONTEXT_KEY
from src.review_disposition_v1 import definitive_review_disposition

VERSION = "source-containers-v1"
SOURCE_VERSION = CONTAINERS_VERSION


def metadata_reason(text):
    """Closed whole-range rules; never exclude by chapter location alone."""
    text = text.strip()
    if re.fullmatch(r"Versie\s*:\s*\d+(?:\.\d+)*", text, re.I):
        return "document_metadata"
    if re.fullmatch(r"Datum\s*:\s*(?:\d{1,2}\s+)?(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+\d{4}", text, re.I):
        return "document_metadata"
    if re.fullmatch(r"[^\n]{1,160}\.{8,}\s*\d{1,4}", text):
        return "navigation"
    # A page footer requires the complete document label, edition indication,
    # month/year and terminal page. A word such as 'richtlijn' is insufficient.
    if re.fullmatch(r"(?:Concept)?richtlijn\s+[^\n]{1,100}\s+[–-]\s+commentaarronde\s+[a-z]+\s+20\d{2}\s+\d{1,3}", text, re.I):
        return "page_furniture"
    return None


def _covers(ref, spans):
    cursor = ref["start"]
    for s in sorted((s for s in spans if s["block_id"] == ref["block_id"]), key=lambda s:s["start"]):
        if s["start"] > cursor:
            break
        cursor = max(cursor, s["end"])
    return cursor >= ref["end"]


def source_accountability(objects, *, review_path="richtlijn", bindings=None, fragments=None):
    """One read-only source role/closure/action projection for a current bundle.

    Existing evidence owns state. Missing review inputs never prove target
    approval. Structure QA and content ReviewDuty remain separate authorities.
    """
    from src.admission_gate_v1 import admission_of, is_boom_object
    from src.knowledge_path_v1 import content_reviewable, source_lineage_resolves, spans_are_exact
    from src.operations_console_v1 import review_lane
    from src.review_duty_v1 import review_duty_for, review_stage, exact_current_approver_ids
    from src.source_context_review_v1 import context_issues, role_of, links_of

    objects = list(objects)
    bindings = tuple(bindings or ())
    fragments = list(fragments) if fragments is not None else None
    conflicts = context_issues(objects)
    targets = []

    def target_state(target):
        oid = str(target.get("object_id") or "")
        if oid in conflicts:
            return "invalid"
        if (target.get("governance") or {}).get("validation_status") in {"rejected", "superseded", "revise"}:
            return "retired"
        if not content_reviewable(target):
            return "invalid"
        if fragments is not None and not source_lineage_resolves(target, fragments=fragments):
            return "invalid"
        admission = admission_of(target)
        source = target.get("source") or {}
        if (admission.get("source_hash") and admission["source_hash"] != source.get("source_checksum")
                or admission.get("document_version") and admission["document_version"] != source.get("version")):
            return "invalid"
        if (fragments is not None and exact_current_approver_ids(target, bindings)
                and review_stage(target, review_path=review_path, bindings=bindings, fragments=fragments) is None):
            return "approved"
        return "pending"

    for target in objects:
        if is_source_record(target) or is_boom_object(target):
            continue
        raw = (target.get("metadata") or {}).get(CONTEXT_KEY)
        if not isinstance(raw, dict):
            continue
        try:
            valid = context_matches_target(target)
        except (KeyError, TypeError, ValueError):
            valid = False
        state = target_state(target) if valid else "invalid"
        entries = raw.get("entries")
        for row in entries if isinstance(entries, list) else []:
            if (isinstance(row, dict) and spans_are_exact([row.get("span")])
                    and not row.get("unresolved_reason")):
                targets.append((target, row["span"], state))

    result = {}
    for obj in objects:
        oid = str(obj.get("object_id") or "")
        if not oid:
            continue
        source_record = is_source_record(obj)
        disposition = definitive_review_disposition(obj)
        row = {"role": "unresolved", "closure": "open", "human_action": "source_disposition",
               "reason": disposition["outcome"], "target_ids": [], "kind": "unresolved",
               "accounted": False, "required": obj.get("object_type") != "document"}
        def finish(role, closure, action, reason, kind=None):
            row.update(role=role, closure=closure, human_action=action, reason=reason,
                       kind=kind or role, accounted=closure == "accounted")
            result[oid] = row

        if obj.get("object_type") == "document":
            row["required"] = False
            finish("structure", "accounted", "none", "document")
            continue
        evidence = evidence_of(obj) if source_record else {}
        if oid in conflicts or (source_record and (not evidence or not spans_are_exact(evidence.get("spans")))):
            finish("invalid_evidence", "repair_required", "technical_repair",
                   (conflicts.get(oid) or ["source_accountability_invalid"])[0])
            continue
        if not source_record:
            # Preserve the existing boom/legacy passage closure contract. T10
            # does not reinterpret decision-tree construction or review duties.
            if review_lane(obj) == "fast":
                row["required"] = False
                finish("structure", "accounted", "none", "structure")
            elif disposition["final"]:
                finish("knowledge_source" if content_reviewable(obj) else "explicitly_accounted",
                       "accounted", "none", disposition["outcome"], "reviewed")
            elif content_reviewable(obj):
                if fragments is not None and not source_lineage_resolves(obj, fragments=fragments):
                    finish("invalid_evidence", "repair_required", "technical_repair", "source_lineage_incomplete")
                else:
                    finish("knowledge_source", "waiting_on_target", "none", "knowledge_review")
            elif review_duty_for(obj, review_path=review_path, bindings=bindings, fragments=fragments):
                finish("knowledge_source", "waiting_on_target", "none", "knowledge_review")
            elif (admission_of(obj).get("gate_result") == "blocked"
                  and (review_path != "boom" or (obj.get("metadata") or {}).get("decision_unit_construction"))):
                finish("unresolved", "repair_required", "technical_repair", "admission_blocked")
            else:
                finish("unresolved", "open", "source_disposition", disposition["outcome"])
            continue

        if evidence["version"] != SOURCE_VERSION:
            if disposition["final"]:
                finish("explicitly_accounted", "accounted", "none", disposition["outcome"], "reviewed")
            else:
                finish("unresolved", "open", "source_disposition", "legacy_source_policy")
            continue

        role = role_of(obj)
        if role.get("role") in {"label", "context"}:
            linked_targets = [target for target in objects
                              if any(link.get("source_object_id") == oid for link in links_of(target))]
            row["target_ids"] = sorted(target["object_id"] for target in linked_targets)
            states = [target_state(target) for target in linked_targets]
            if not states or "invalid" in states:
                finish("invalid_evidence", "repair_required", "technical_repair", "source_context_stale")
            elif "retired" in states:
                finish("unresolved", "open", "source_disposition", "source_context_target_retired")
            else:
                finish("linked_context", "accounted" if all(s == "approved" for s in states) else "waiting_on_target",
                       "none", "confirmed_source_context")
            continue
        if disposition["final"]:
            finish("explicitly_accounted", "accounted", "none", disposition["outcome"], "reviewed")
            continue

        spans = evidence["spans"]
        linked = [(target, span, state) for target, span, state in targets
                  if obj.get("source", {}).get("source_checksum")
                  and target.get("source", {}).get("source_checksum") == obj.get("source", {}).get("source_checksum")
                  and any(span["block_id"] == s["block_id"]
                          and max(span["start"], s["start"]) < min(span["end"], s["end"]) for s in spans)]
        row["target_ids"] = sorted({target["object_id"] for target, _, _ in linked})
        manual = role or (obj.get("metadata", {}).get("passage_register") or {}).get("source") == "review"
        machine_reason = metadata_reason(evidence["text"]) if not manual else None
        if machine_reason:
            finish("navigation" if machine_reason == "navigation" else "document_information",
                   "accounted", "none", machine_reason, "document_information")
        elif not manual and any(state == "invalid" for _, _, state in linked):
            finish("invalid_evidence", "repair_required", "technical_repair", "source_context_stale")
        elif not manual and all(_covers(s, [span for _, span, state in linked
                                          if state in {"pending", "approved"}]) for s in spans):
            closed = all(_covers(s, [span for _, span, state in linked if state == "approved"]) for s in spans)
            finish("linked_context", "accounted" if closed else "waiting_on_target", "none", evidence["reason"])
        else:
            finish("unresolved", "open", "source_disposition", evidence["reason"])
    return result


def source_closure(projection):
    """Compatibility summary of a source-domain decision, with no new policy."""
    required = [oid for oid, row in projection.items() if row["required"]]
    unresolved = [oid for oid in required if projection[oid]["closure"] != "accounted"]
    return {
        "source_passage_review_complete": not unresolved,
        "review_required_source_passage_ids": required,
        "review_required_source_passage_count": len(required),
        "unresolved_source_passage_ids": unresolved,
        "unresolved_source_passage_count": len(unresolved),
    }


def source_usage(objects, *, review_path="richtlijn", bindings=None, fragments=None, projection=None):
    """Existing source-only view over the central accountability projection."""
    objects = list(objects)
    if projection is None:
        projection = source_accountability(objects, review_path=review_path, bindings=bindings, fragments=fragments)
    return {obj["object_id"]: {key: projection[obj["object_id"]][key]
            for key in ("kind", "reason", "target_ids", "accounted", "role", "closure", "human_action")}
            for obj in objects if is_source_record(obj) and obj.get("object_id") in projection}


def partition(objects, *, review_path="richtlijn", bindings=None, fragments=None, projection=None):
    """Separate access contracts over the same atomic storage bundle."""
    objects = list(objects)
    usage = source_usage(objects, review_path=review_path, bindings=bindings, fragments=fragments, projection=projection)
    knowledge, source, structure = [], [], []
    for obj in objects:
        if is_source_record(obj):
            source.append({"record": obj, "usage": usage[obj["object_id"]]})
        elif obj.get("object_type") in {"document", "heading"}:
            structure.append(obj)
        else:
            knowledge.append(obj)
    return {"version": VERSION, "knowledge": knowledge, "source": source, "structure": structure}
