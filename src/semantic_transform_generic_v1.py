#!/usr/bin/env python3
"""Source-neutral deterministic semantic transform for Protocol v2.1.

A versioned semantic spec explicitly maps raw fragment IDs to canonical knowledge
objects. No source-specific clinical rules are encoded in this transformer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from src.integrity_kernel import stamp_canonical_hashes, stable_hash
from src.serving_relations_v1 import confirm_relation_set, proposed_relations

TRANSFORM_VERSION = "semantic-generic-v1.0.0"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _governance(review_track: str, second_required: bool) -> dict[str, Any]:
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


def _source(manifest: dict[str, Any], source_page: int | None) -> dict[str, Any]:
    src = manifest["canonical_source"]
    return {
        "source_id": src["source_id"],
        "title": src["title"],
        "publisher": src.get("publisher", "V&VN"),
        "source_url": src["source_url"],
        "source_type": src["source_type"],
        "source_level": src["source_level"],
        "canonicality": src["canonicality"],
        "source_checksum": src.get("source_checksum"),
        "checksum_algorithm": src.get("checksum_algorithm", "sha256"),
        "integrity_status": src["integrity_status"],
        "publication_date": src.get("publication_date"),
        "version": src.get("version"),
        "source_page": source_page,
    }


def _fragment_ref(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_object_id": raw["fragment_id"],
        "page": raw.get("source_page"),
        "raw_content_hash": raw["fragment_hash"],
        "bbox": raw.get("bbox"),
        "coordinate_status": "available" if raw.get("bbox") is not None else "not_applicable",
        "source_locator": raw["source_locator"],
    }


def transform(spec: dict[str, Any], manifest: dict[str, Any], raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_by_id = {r["fragment_id"]: r for r in raw_rows}
    spec_hash = stable_hash(spec)
    raw_extract_hash = hashlib.sha256("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in raw_rows).encode("utf-8")).hexdigest()
    out: list[dict[str, Any]] = []
    for seq, item in enumerate(spec["objects"], 1):
        refs = []
        for rid in item.get("source_fragment_ids", []):
            if rid not in raw_by_id:
                raise ValueError(f"unknown source_fragment_id:{rid}")
            refs.append(_fragment_ref(raw_by_id[rid]))
        if item["object_type"] != "document" and not refs:
            raise ValueError(f"source fragments required:{item['object_id']}")
        risk_fields = list(dict.fromkeys(item.get("risk_fields", [])))
        high = bool(risk_fields)
        page = next((r.get("source_page") for r in (raw_by_id[x] for x in item.get("source_fragment_ids", [])) if r.get("source_page")), None)
        obj = {
            "object_id": item["object_id"],
            "document_id": spec["document_id"],
            "object_version": spec["object_version"],
            "parent_object_id": item.get("parent_object_id"),
            "object_type": item["object_type"],
            **(
                {"proposed_object_type": item["proposed_object_type"]}
                if item.get("proposed_object_type")
                else {}
            ),
            **(
                {"confirmed_object_type": item["confirmed_object_type"]}
                if item.get("confirmed_object_type")
                else {}
            ),
            **(
                {"proposed_recommendation_strength": item["proposed_recommendation_strength"]}
                if item.get("proposed_recommendation_strength")
                else {}
            ),
            **(
                {"confirmed_recommendation_strength": item["confirmed_recommendation_strength"]}
                if item.get("confirmed_recommendation_strength")
                else {}
            ),
            "source": _source(manifest, page),
            "structure": {
                "section_path": item.get("section_path", []),
                "heading": item.get("heading"),
                "sequence": item.get("sequence", seq),
            },
            "content": {
                "raw_text": item["text"],
                "clean_text": item.get("clean_text", item["text"]),
                "context_text": item.get("context_text"),
                "target_group": spec.get("target_group", []),
                "care_setting": spec.get("care_setting", []),
                "topic": spec.get("topic", []),
            },
            "logic": item.get("logic"),
            "relations": proposed_relations({"relations": item.get("relations", [])}),
            "confirmed_relations": confirm_relation_set(item["confirmed_relations"])
            if item.get("confirmed_relations")
            else [],
            "decision_graph": item.get("decision_graph"),
            "risk": {
                "risk_level": "high" if high else "standard",
                "risk_fields": risk_fields,
                "requires_second_review": high,
            },
            "uncertainty": {
                "has_uncertainty": bool(item.get("uncertainty_items")),
                "items": item.get("uncertainty_items", []),
            },
            "governance": _governance(item.get("review_track", "clinical"), high),
            "provenance": {
                "transformation_mode": "deterministic",
                "created_by": f"system:{TRANSFORM_VERSION}",
                "source_extract_hash": raw_extract_hash,
                "semantic_spec_version": spec["spec_version"],
                "semantic_spec_hash": spec_hash,
                "transform_version": TRANSFORM_VERSION,
                "content_hash": "0" * 64,
                "proposal_id": None,
                "canonical_object_hash": "0" * 64,
                "source_fragments": refs,
                "previous_object_version": None,
                "revision_reason": None,
                "revision_patch_hash": None,
            },
        }
        out.append(stamp_canonical_hashes(obj))
    return out


def validate(rows: list[dict[str, Any]], schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    v = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = []
    for i, row in enumerate(rows):
        errors.extend(f"row[{i}] {'.'.join(map(str,e.absolute_path))}: {e.message}" for e in v.iter_errors(row))
    return errors


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--schema", type=Path, default=Path("schemas/knowledge_object.schema.v1.2.json"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a=ap.parse_args()
    spec, manifest, raw=load_json(a.spec), load_json(a.manifest), load_jsonl(a.raw)
    try:
        rows=transform(spec,manifest,raw)
        errors=validate(rows,a.schema)
        status="PASS" if rows and not errors else "BLOCKED"
    except Exception as exc:
        rows=[]; errors=[f"{type(exc).__name__}:{exc}"]; status="BLOCKED"
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows),encoding="utf-8")
    report={"status":status,"transform_version":TRANSFORM_VERSION,"object_count":len(rows),"schema_errors":errors}
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if status=="PASS" else 2

if __name__=="__main__": raise SystemExit(main())
