"""Typed revision containers and exact source usage, derived from one durable bundle.

No approval or serving authority lives here. Legacy source records keep their
old human-disposition policy. New records may account for narrowly recognized
document information and validated, current target context.
"""
import re

from src.source_accountability_v1 import evidence_of, is_source_record, CONTAINERS_VERSION, VERSION_V3, roles_for
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


def source_usage(objects):
    """Account only for context still bound to a current, non-rejected target."""
    from src.source_context_review_v1 import context_issues
    conflicts = context_issues(objects)
    targets = []
    for obj in objects:
        if is_source_record(obj) or not context_matches_target(obj):
            continue
        if (obj.get("governance") or {}).get("validation_status") in {"rejected", "superseded", "revise"}:
            continue
        for row in obj["metadata"][CONTEXT_KEY]["entries"]:
            if isinstance(row, dict) and isinstance(row.get("span"), dict) and not row.get("unresolved_reason"):
                targets.append((obj, row["span"]))
    result = {}
    for obj in objects:
        evidence = evidence_of(obj)
        if not evidence:
            continue
        disposition = definitive_review_disposition(obj)
        if disposition["final"] and obj["object_id"] not in conflicts:
            result[obj["object_id"]] = {"kind": "reviewed", "reason": disposition["outcome"],
                                        "target_ids": [], "accounted": True}
            continue
        if evidence.get("version") == SOURCE_VERSION:
            spans = evidence["spans"]
            linked = [(target, span) for target, span in targets
                      if obj.get("source", {}).get("source_checksum")
                      and target.get("source", {}).get("source_checksum") == obj.get("source", {}).get("source_checksum")
                      and any(span["block_id"] == s["block_id"] and max(span["start"],s["start"]) < min(span["end"],s["end"]) for s in spans)]
            linked_spans = [span for _, span in linked]
            final_spans = [span for target, span in linked if definitive_review_disposition(target)["outcome"] == "approved"]
            # The existing reset command removes the role but retains its reviewed
            # passage register. It must also override an automatic source decision.
            metadata = obj.get("metadata") or {}
            manual = metadata.get("source_role_review") or (metadata.get("passage_register") or {}).get("source") == "review"
            machine_reason = metadata_reason(evidence["text"]) if not manual else None
            context = not manual and bool(spans) and all(_covers(s, linked_spans) for s in spans)
            result[obj["object_id"]] = {
                "kind": "document_information" if machine_reason else "linked_context" if context else "unresolved",
                "reason": machine_reason or evidence["reason"],
                "target_ids": sorted({target["object_id"] for target, _ in linked}),
                "accounted": bool(machine_reason) or (context and all(_covers(s, final_spans) for s in spans)),
            }
            continue
        if evidence.get("version") != VERSION_V3:
            continue
        spans = evidence["spans"]
        role = evidence.get("proposed_role")
        linked = [(target, span) for target, span in targets
                  if obj.get("source", {}).get("source_checksum")
                  and target.get("source", {}).get("source_checksum") == obj.get("source", {}).get("source_checksum")
                  and any(span["block_id"] == s["block_id"] and max(span["start"], s["start"]) < min(span["end"], s["end"]) for s in spans)]
        linked_spans = [span for _, span in linked]
        final_spans = [span for target, span in linked if definitive_review_disposition(target)["outcome"] == "approved"]
        metadata = obj.get("metadata") or {}
        manual = metadata.get("source_role_review") or (metadata.get("passage_register") or {}).get("source") == "review"
        machine_reason = metadata_reason(evidence["text"]) if not manual else None
        allowed = roles_for(VERSION_V3).get(role, ())
        context_bound = not manual and role == "context" and bool(spans) and all(_covers(s, linked_spans) for s in spans)
        if role in {"metadata", "structure"} and machine_reason in allowed:
            usage = {"kind": "document_information", "reason": machine_reason, "accounted": True}
        elif context_bound:
            usage = {
                "kind": "linked_context",
                "reason": evidence["reason"],
                "accounted": all(_covers(s, final_spans) for s in spans),
            }
        else:
            usage = {
                "kind": {
                    "background": "background",
                    "support": "proposed_support",
                    "answer_bearing": "answer_bearing",
                    "context": "unresolved",
                }.get(role, "unresolved"),
                "reason": evidence["reason"],
                "accounted": False,
            }
        result[obj["object_id"]] = {
            **usage,
            "target_ids": sorted({target["object_id"] for target, _ in linked}),
        }
    return result


def partition(objects):
    """Separate domain access contracts over the same atomic storage bundle."""
    objects = list(objects)
    usage = source_usage(objects)
    knowledge, source, structure = [], [], []
    for obj in objects:
        if is_source_record(obj):
            source.append({"record": obj, "usage": usage.get(obj["object_id"], {
                "kind": "unresolved", "reason": "legacy_source_policy", "accounted": False, "target_ids": []})})
        elif obj.get("object_type") in {"document", "heading"}:
            structure.append(obj)
        else:
            knowledge.append(obj)
    return {"version": VERSION, "knowledge": knowledge, "source": source, "structure": structure}
