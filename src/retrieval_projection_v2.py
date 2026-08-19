#!/usr/bin/env python3
"""Build deterministic retrieval projections from *published* V&VN knowledge objects.

This module is deliberately downstream of the canonical publication registry.
It does not approve, publish, embed, or mutate canonical knowledge objects.

Input format is the JSONL envelope produced by canonical_store.export_published():
    {"knowledge_object": {...}, "publication": {...}}

Safety properties:
- only explicit publication envelopes are accepted;
- the canonical object itself must still be clinically approved;
- unresolved uncertainty is rejected;
- retrieval records preserve object/version/content hashes and release metadata;
- clinically relevant parent/condition context is copied into the derived view;
- projection hashes are deterministic and can be regenerated at any time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

SEARCHABLE_TYPES = {
    "definition",
    "condition",
    "score_rule",
    "decision",
    "action",
    "recommendation",
    "exception",
    "out_of_scope",
}

NON_SEARCHABLE_TYPES = {"document", "section", "supersession"}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def publication_errors(envelope: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    obj = envelope.get("knowledge_object")
    pub = envelope.get("publication")
    if not isinstance(obj, dict):
        return ["knowledge_object_missing"]
    if not isinstance(pub, dict):
        return ["publication_envelope_missing"]
    for field in ("release_id", "release_version", "published_at"):
        if not pub.get(field):
            errors.append(f"publication_{field}_missing")
    gov = obj.get("governance") or {}
    if gov.get("validation_status") != "approved":
        errors.append("object_not_clinically_approved")
    if (obj.get("uncertainty") or {}).get("has_uncertainty"):
        errors.append("unresolved_uncertainty")
    if not (obj.get("provenance") or {}).get("content_hash"):
        errors.append("content_hash_missing")
    if not obj.get("object_version"):
        errors.append("object_version_missing")
    if obj.get("object_type") not in SEARCHABLE_TYPES | NON_SEARCHABLE_TYPES:
        errors.append("unknown_object_type")
    return errors


def _logic_text(logic: dict[str, Any] | None) -> list[str]:
    if not logic:
        return []
    parts: list[str] = []
    for p in logic.get("predicates") or []:
        source_text = p.get("source_text")
        if source_text:
            parts.append(f"Voorwaarde: {source_text}")
        else:
            bits = [str(p.get("field") or "").strip(), str(p.get("operator") or "").strip()]
            if p.get("threshold") is not None:
                bits.append(str(p["threshold"]))
            if p.get("unit"):
                bits.append(str(p["unit"]))
            compact = " ".join(x for x in bits if x)
            if compact:
                parts.append(f"Voorwaarde: {compact}")
    if logic.get("score_points") is not None:
        parts.append(f"Score: {logic['score_points']} punt(en)")
    rt = logic.get("result_threshold")
    if rt:
        parts.append(
            "Uitkomstdrempel: "
            + " ".join(
                str(x) for x in (rt.get("operator"), rt.get("threshold"), rt.get("unit")) if x is not None
            )
        )
    if logic.get("result_action"):
        parts.append(f"Actie: {logic['result_action']}")
    return parts


def _context_summary(obj: dict[str, Any]) -> str:
    return (obj.get("content") or {}).get("clean_text", "").strip()


def build_projection(envelopes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (retrieval_records, blocked_records)."""
    blocked: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    for env in envelopes:
        errs = publication_errors(env)
        if errs:
            obj = env.get("knowledge_object") or {}
            blocked.append({
                "object_id": obj.get("object_id"),
                "object_version": obj.get("object_version"),
                "errors": errs,
            })
        else:
            valid.append(env)

    # Context can only be inherited from objects present in the same published export.
    object_index = {e["knowledge_object"]["object_id"]: e["knowledge_object"] for e in valid}
    records: list[dict[str, Any]] = []
    for env in valid:
        obj = env["knowledge_object"]
        if obj["object_type"] not in SEARCHABLE_TYPES:
            continue
        pub = env["publication"]
        content = obj.get("content") or {}
        structure = obj.get("structure") or {}
        source = obj.get("source") or {}

        context_ids: list[str] = []
        if obj.get("parent_object_id") and obj["parent_object_id"] in object_index:
            context_ids.append(obj["parent_object_id"])
        for rel in obj.get("relations") or []:
            target = rel.get("target_object_id")
            if target in object_index and target not in context_ids:
                context_ids.append(target)

        context_objects = [object_index[i] for i in context_ids]
        context_texts = [_context_summary(c) for c in context_objects if _context_summary(c)]

        text_parts: list[str] = []
        if source.get("title"):
            text_parts.append(f"Bron: {source['title']}")
        section_path = structure.get("section_path") or []
        if section_path:
            text_parts.append("Sectie: " + " > ".join(section_path))
        if structure.get("heading"):
            text_parts.append(f"Kop: {structure['heading']}")
        if content.get("context_text"):
            text_parts.append(f"Context: {content['context_text']}")
        if context_texts:
            text_parts.append("Gekoppelde context: " + " | ".join(context_texts))
        if content.get("clean_text"):
            text_parts.append(content["clean_text"].strip())
        text_parts.extend(_logic_text(obj.get("logic")))
        retrieval_text = "\n".join(p for p in text_parts if p).strip()

        metadata = {
            "object_id": obj["object_id"],
            "object_version": obj["object_version"],
            "document_id": obj["document_id"],
            "object_type": obj["object_type"],
            "content_hash": obj["provenance"]["content_hash"],
            "release_id": pub["release_id"],
            "release_version": pub["release_version"],
            "published_at": pub["published_at"],
            "source_title": source.get("title"),
            "source_url": source.get("source_url"),
            "source_page": source.get("source_page"),
            "source_version": source.get("version"),
            "topic": content.get("topic", []),
            "target_group": content.get("target_group", []),
            "care_setting": content.get("care_setting", []),
            "parent_object_id": obj.get("parent_object_id"),
            "context_object_ids": context_ids,
            "risk_level": (obj.get("risk") or {}).get("risk_level"),
        }
        # Preserve structured clinical logic separately from free-text retrieval text.
        # This is a derived read-only projection of the canonical object and allows
        # downstream consumers to verify operators/thresholds without reparsing text.
        structured_logic = obj.get("logic") or {}
        record_core = {
            "retrieval_id": f"{obj['object_id']}@{obj['object_version']}",
            "retrieval_text": retrieval_text,
            "structured_logic": structured_logic,
            "metadata": metadata,
        }
        record = dict(record_core)
        record["projection_hash"] = canonical_hash(record_core)
        records.append(record)

    records.sort(key=lambda r: r["retrieval_id"])
    return records, blocked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True, help="Published JSONL export from canonical_store.py")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    envelopes = read_jsonl(args.input) if args.input.exists() else []
    records, blocked = build_projection(envelopes)
    write_jsonl(records, args.out)
    report = {
        "status": "PASS" if not blocked else "BLOCKED",
        "input_published_envelopes": len(envelopes),
        "retrieval_records": len(records),
        "blocked_records": len(blocked),
        "blocked": blocked,
        "embedding_status": "disabled",
        "canonical_data_mutated": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
