#!/usr/bin/env python3
"""Deterministic V&VN semantic transform for Protocol v2.

Canonical objects are generated only from a versioned semantic specification.
No LLM calls or probabilistic inference are permitted in this transform.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from src.integrity_kernel import stamp_canonical_hashes

TRANSFORM_VERSION = "semantic-v2.1.0"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(raw)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_block(spec: dict[str, Any], manifest: dict[str, Any], page: int | None) -> dict[str, Any]:
    src = manifest["canonical_source"]
    return {
        "source_id": src["source_id"],
        "title": src["title"],
        "publisher": "V&VN",
        "source_url": src["source_url"],
        "source_type": src["source_type"],
        "source_level": src["source_level"],
        "canonicality": src["canonicality"],
        "source_checksum": src.get("source_checksum"),
        "checksum_algorithm": src["checksum_algorithm"],
        "integrity_status": src["integrity_status"],
        "publication_date": None,
        "version": src.get("version"),
        "source_page": page,
    }


def governance(review_track: str, second_required: bool) -> dict[str, Any]:
    return {
        "validation_status": "needs_review",
        "publication_status": "unpublished",
        "review_track": review_track,
        "validated_by": None,
        "validation_date": None,
        "review_snapshot_hash": None,
        "second_review": {
            "required": second_required,
            "status": "pending" if second_required else "not_required",
            "reviewer": None,
            "review_date": None,
            "snapshot_hash": None,
        },
        "release_owner": None,
        "release_date": None,
        "superseded_by": None,
    }


def risk_block(risk_fields: list[str]) -> dict[str, Any]:
    fields = list(dict.fromkeys(risk_fields))
    high = bool(fields)
    return {
        "risk_level": "high" if high else "standard",
        "risk_fields": fields,
        "requires_second_review": high,
    }


def make_object(
    *, spec: dict[str, Any], manifest: dict[str, Any], spec_hash: str, raw_hash: str,
    object_id: str, object_type: str, text: str, sequence: int | None,
    parent: str | None = None, heading: str | None = None, logic: dict[str, Any] | None = None,
    relations: list[dict[str, str]] | None = None, risk_fields: list[str] | None = None,
    review_track: str = "clinical", page: int | None = None,
    decision_graph: dict[str, Any] | None = None, uncertainty_items: list[dict[str, str]] | None = None,
    source_fragments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    risks = risk_block(risk_fields or [])
    path = spec["section"].split(" > ") if page else []
    uncertainty_items = uncertainty_items or []
    obj = {
        "object_id": object_id,
        "document_id": spec["document_id"],
        "object_version": spec["object_version"],
        "parent_object_id": parent,
        "object_type": object_type,
        "source": source_block(spec, manifest, page),
        "structure": {"section_path": path, "heading": heading, "sequence": sequence},
        "content": {
            "raw_text": text,
            "clean_text": text,
            "context_text": spec["section"] if page else None,
            "target_group": ["verpleegkundige", "verzorgende", "verpleegkundig specialist"] if page else [],
            "care_setting": ["eerste lijn"] if page else [],
            "topic": ["osteoporose", "fractuurpreventie"],
        },
        "logic": logic,
        "relations": relations or [],
        "decision_graph": decision_graph,
        "risk": risks,
        "uncertainty": {"has_uncertainty": bool(uncertainty_items), "items": uncertainty_items},
        "governance": governance(review_track, risks["requires_second_review"]),
        "provenance": {
            "transformation_mode": "deterministic",
            "created_by": f"system:{TRANSFORM_VERSION}",
            "source_extract_hash": raw_hash,
            "semantic_spec_version": spec["spec_version"],
            "semantic_spec_hash": spec_hash,
            "transform_version": TRANSFORM_VERSION,
            "content_hash": "0" * 64,
            "canonical_object_hash": "0" * 64,
            "source_fragments": source_fragments or [],
            "previous_object_version": None,
            "revision_reason": None,
            "revision_patch_hash": None,
            "proposal_id": None,
        },
    }
    return stamp_canonical_hashes(obj)


def score_logic(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "predicates": [{
            "field": "score_factor",
            "operator": rule["operator"],
            "threshold": rule["threshold"],
            "unit": rule.get("unit"),
            "source_text": rule["condition"],
        }],
        "score_points": rule["score_points"],
        "result_threshold": None,
        "result_action": None,
    }


def transform(spec: dict[str, Any], manifest: dict[str, Any], spec_hash: str, raw_hash: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    doc = spec["document_id"]
    page = spec["page"]

    # New protocol-v2 document object. It is a technical-review object and cannot
    # be published while the canonical binary checksum is unavailable.
    source_uncertainty = []
    if manifest["canonical_source"].get("integrity_status") != "verified":
        source_uncertainty = [{
            "field": "source_checksum",
            "reason": "Canonical source binary is not locally available; publication must remain blocked until its SHA-256 is verified.",
        }]
    out.append(make_object(
        spec=spec, manifest=manifest, spec_hash=spec_hash, raw_hash=raw_hash,
        object_id=spec["document_object_id"], object_type="document", text=spec["title"],
        sequence=0, heading=spec["title"], review_track="technical", page=None,
        uncertainty_items=source_uncertainty, source_fragments=spec.get("document_source_fragments", []),
    ))

    seq = 0
    for scenario in spec["scenarios"]:
        seq += 1
        condition_id = f"{doc}-p{page:03d}-condition-{scenario['id']}"
        logic = {
            "predicates": scenario["predicates"],
            "score_points": None,
            "result_threshold": None,
            "result_action": None,
        }
        out.append(make_object(
            spec=spec, manifest=manifest, spec_hash=spec_hash, raw_hash=raw_hash,
            object_id=condition_id, object_type="condition", text=scenario["condition"], sequence=seq,
            logic=logic, risk_fields=scenario.get("risk_fields", []), page=page,
            source_fragments=scenario.get("source_fragments", []),
        ))
        for i, rec in enumerate(scenario["recommendations"], 1):
            seq += 1
            oid = f"{doc}-p{page:03d}-rec-{scenario['id']}-{i:02d}"
            rec_logic = None
            if rec.get("result_threshold") or rec.get("result_action"):
                rec_logic = {
                    "predicates": [],
                    "score_points": None,
                    "result_threshold": rec.get("result_threshold"),
                    "result_action": rec.get("result_action"),
                }
            out.append(make_object(
                spec=spec, manifest=manifest, spec_hash=spec_hash, raw_hash=raw_hash,
                object_id=oid, object_type="recommendation", text=rec["text"], sequence=seq,
                parent=condition_id, logic=rec_logic,
                relations=[{"relation_type": "conditioned_by", "target_object_id": condition_id}],
                risk_fields=rec.get("risk_fields", []), page=page,
                source_fragments=rec.get("source_fragments", []),
            ))

    # Preserve the existing expert-review ID while migrating table -> section.
    seq += 1
    section_id = f"{doc}-p{page:03d}-table-risk-score"
    out.append(make_object(
        spec=spec, manifest=manifest, spec_hash=spec_hash, raw_hash=raw_hash,
        object_id=section_id, object_type="section", text=spec["score_table"]["title"], sequence=seq,
        heading=spec["score_table"]["title"], page=page,
        source_fragments=spec["score_table"].get("source_fragments", []),
    ))

    for i, rule in enumerate(spec["score_table"]["rules"], 1):
        seq += 1
        oid = f"{doc}-p{page:03d}-score-{i:02d}"
        text = f"{rule['condition']} -> {rule['score_points']} punt" + ("en" if rule["score_points"] != 1 else "")
        out.append(make_object(
            spec=spec, manifest=manifest, spec_hash=spec_hash, raw_hash=raw_hash,
            object_id=oid, object_type="score_rule", text=text, sequence=seq, parent=section_id,
            logic=score_logic(rule),
            relations=[{"relation_type": "child_of", "target_object_id": section_id}],
            risk_fields=rule.get("risk_fields", []), page=page,
            source_fragments=rule.get("source_fragments", []),
        ))

    # Preserve existing expert-review ID while migrating background -> definition.
    seq += 1
    foot_id = f"{doc}-p{page:03d}-background-score-footnote"
    out.append(make_object(
        spec=spec, manifest=manifest, spec_hash=spec_hash, raw_hash=raw_hash,
        object_id=foot_id, object_type="definition", text=spec["score_table"]["footnote"], sequence=seq,
        parent=section_id, relations=[{"relation_type": "child_of", "target_object_id": section_id}], page=page,
        source_fragments=spec["score_table"].get("footnote_source_fragments", []),
    ))
    return out


def validate_integrity(objects: list[dict[str, Any]]) -> dict[str, bool]:
    ids = [o["object_id"] for o in objects]
    idset = set(ids)
    relation_targets = [r["target_object_id"] for o in objects for r in o["relations"]]
    parent_targets = [o["parent_object_id"] for o in objects if o["parent_object_id"]]
    return {
        "unique_ids": len(ids) == len(idset),
        "parent_targets_exist": all(x in idset for x in parent_targets),
        "relation_targets_exist": all(x in idset for x in relation_targets),
        "closed_object_types": all(o["object_type"] in {
            "document", "section", "definition", "condition", "score_rule", "decision",
            "action", "recommendation", "exception", "out_of_scope", "supersession"
        } for o in objects),
        "nothing_approved": all(o["governance"]["validation_status"] != "approved" for o in objects),
        "nothing_published": all(o["governance"]["publication_status"] == "unpublished" for o in objects),
        "risk_second_review_consistent": all(
            o["governance"]["second_review"]["required"] == o["risk"]["requires_second_review"]
            for o in objects
        ),
        "deterministic_only": all(o["provenance"]["transformation_mode"] == "deterministic" for o in objects),
        "no_ai_proposal_in_canonical": all(o["provenance"].get("proposal_id") is None for o in objects),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("--source-manifest", type=Path, required=True)
    ap.add_argument("--schema", type=Path, required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    spec = load_json(args.spec)
    manifest = load_json(args.source_manifest)
    schema = load_json(args.schema)
    spec_hash = sha256_bytes(args.spec.read_bytes())
    raw_path = args.root / spec["source_extract"]
    raw_hash = sha256_bytes(raw_path.read_bytes())
    expected_raw_hash = manifest["working_inputs"]["raw_extract_sha256"]
    if raw_hash != expected_raw_hash:
        raise SystemExit(f"Raw extract hash mismatch: {raw_hash} != {expected_raw_hash}")

    objects = transform(spec, manifest, spec_hash, raw_hash)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_errors: list[str] = []
    for obj in objects:
        for err in validator.iter_errors(obj):
            schema_errors.append(f"{obj['object_id']}: {err.message}")
    integrity = validate_integrity(objects)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for obj in objects:
            f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")

    counts: dict[str, int] = {}
    for o in objects:
        counts[o["object_type"]] = counts.get(o["object_type"], 0) + 1
    report = {
        "protocol": "2.1",
        "transform_version": TRANSFORM_VERSION,
        "spec_version": spec["spec_version"],
        "semantic_spec_sha256": spec_hash,
        "source_extract_sha256": raw_hash,
        "canonical_source_integrity_status": manifest["canonical_source"]["integrity_status"],
        "canonical_source_checksum": manifest["canonical_source"].get("source_checksum"),
        "object_count": len(objects),
        "object_types": counts,
        "high_risk_objects": sum(1 for o in objects if o["risk"]["risk_level"] == "high"),
        "schema_valid": not schema_errors,
        "schema_errors": schema_errors,
        "integrity_checks": integrity,
        "integrity_valid": all(integrity.values()),
        "publication_status": "BLOCKED" if manifest["canonical_source"]["integrity_status"] != "verified" else "ELIGIBLE_FOR_REVIEW_ONLY",
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not schema_errors and all(integrity.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
