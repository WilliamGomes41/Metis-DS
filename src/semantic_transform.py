#!/usr/bin/env python3
"""V&VN Data Service - semantic transform v0.1.

Transforms a source-grounded semantic specification into structured knowledge
objects. The transform itself is generic; clinical source interpretation lives
in the spec and remains needs_review until human approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

TRANSFORM_VERSION = "semantic-0.1.0"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def base(spec: dict[str, Any], object_id: str, object_type: str, text: str,
         sequence: int, parent: str | None = None, logic: dict[str, Any] | None = None,
         heading: str | None = None) -> dict[str, Any]:
    path = spec["section"].split(" > ")
    return {
        "object_id": object_id,
        "document_id": spec["document_id"],
        "parent_object_id": parent,
        "object_type": object_type,
        "source": {
            "title": spec["title"],
            "publisher": "V&VN",
            "source_url": spec["source_url"],
            "source_type": "pdf",
            "publication_date": None,
            "version": spec.get("version"),
            "source_page": spec["page"]
        },
        "structure": {
            "section_path": path,
            "heading": heading,
            "sequence": sequence
        },
        "content": {
            "raw_text": text,
            "clean_text": text,
            "context_text": spec["section"],
            "target_group": ["verpleegkundige", "verzorgende", "verpleegkundig specialist"],
            "care_setting": ["eerste lijn"],
            "topic": ["osteoporose", "fractuurpreventie"]
        },
        "logic": logic,
        "governance": {
            "validation_status": "needs_review",
            "validated_by": None,
            "validation_date": None,
            "valid_from": None,
            "valid_until": None
        },
        "technical": {
            "parser_version": TRANSFORM_VERSION,
            "chunk_method": "semantic_source_grouping",
            "content_hash": digest(text),
            "embedding_model": None,
            "embedding_version": None
        }
    }


def transform(spec: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seq = 0
    doc = spec["document_id"]

    # Scenario conditions and their recommendations.
    for scenario in spec["scenarios"]:
        seq += 1
        parent_id = f"{doc}-p{spec['page']:03d}-condition-{scenario['id']}"
        out.append(base(spec, parent_id, "condition", scenario["condition"], seq,
                        logic={"condition": scenario["condition"], "operator": None,
                               "threshold": None, "unit": None, "score_points": None,
                               "branches": []}))
        for i, recommendation in enumerate(scenario["recommendations"], 1):
            seq += 1
            oid = f"{doc}-p{spec['page']:03d}-rec-{scenario['id']}-{i:02d}"
            logic = None
            # Explicitly encode the actionable referral threshold where present.
            if "score van ≥ 4 punten" in recommendation:
                logic = {"condition": "risicofactorenscore", "operator": "gte",
                         "threshold": 4, "unit": "punten", "score_points": None,
                         "branches": []}
            out.append(base(spec, oid, "recommendation", recommendation, seq,
                            parent=parent_id, logic=logic))

    # Whole score table as a semantic container.
    seq += 1
    table_id = f"{doc}-p{spec['page']:03d}-table-risk-score"
    table_text = spec["score_table"]["title"]
    out.append(base(spec, table_id, "table", table_text, seq,
                    heading=spec["score_table"]["title"]))

    # Row-level machine-readable score rules.
    for i, rule in enumerate(spec["score_table"]["rules"], 1):
        seq += 1
        oid = f"{doc}-p{spec['page']:03d}-score-{i:02d}"
        logic = {
            "condition": rule["condition"],
            "operator": rule["operator"],
            "threshold": rule["threshold"],
            "unit": rule["unit"],
            "score_points": rule["score_points"],
            "branches": []
        }
        text = f"{rule['condition']} -> {rule['score_points']} punt" + ("en" if rule["score_points"] != 1 else "")
        out.append(base(spec, oid, "score_rule", text, seq, parent=table_id, logic=logic))

    # Footnote is context, not a score rule by itself.
    seq += 1
    foot_id = f"{doc}-p{spec['page']:03d}-background-score-footnote"
    out.append(base(spec, foot_id, "background", spec["score_table"]["footnote"], seq,
                    parent=table_id))
    return out


def validate(objects: list[dict[str, Any]], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for i, obj in enumerate(objects):
        for err in validator.iter_errors(obj):
            errors.append(f"object[{i}] {obj['object_id']}: {err.message}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("--schema", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    objects = transform(spec)
    errors = validate(objects, schema)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for obj in objects:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    type_counts: dict[str, int] = {}
    for obj in objects:
        type_counts[obj["object_type"]] = type_counts.get(obj["object_type"], 0) + 1

    report = {
        "transform_version": TRANSFORM_VERSION,
        "source_spec": str(args.spec),
        "object_count": len(objects),
        "object_types": type_counts,
        "schema_valid": not errors,
        "schema_errors": errors,
        "all_clinical_objects_status": "needs_review",
        "quality_gates": {
            "scenario_grouping": len(spec["scenarios"]) == 3,
            "score_rules": len(spec["score_table"]["rules"]) == 8,
            "referral_threshold_present": any(
                o.get("logic") and o["logic"].get("threshold") == 4 and o["logic"].get("unit") == "punten"
                for o in objects
            ),
            "source_traceability": all(o["source"]["source_page"] == spec["page"] for o in objects),
            "no_embeddings": all(o["technical"]["embedding_model"] is None for o in objects)
        },
        "known_limitations": [
            "The page-15 semantic specification was visually checked against the rendered PDF because the PDF text layer drops some comparison symbols/text.",
            "Clinical correctness is not approved; all objects remain needs_review.",
            "Age score rows are represented independently; whether age bands are mutually exclusive/cumulative is not inferred.",
            "The footnote is preserved as contextual background and is not decomposed into separate clinical conditions in this pilot."
        ]
    }
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors and all(report["quality_gates"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
