#!/usr/bin/env python3
"""Source-neutral deterministic semantic transform for Protocol v2.1.

A versioned semantic spec explicitly maps raw fragment IDs to canonical knowledge
objects. No source-specific clinical rules are encoded in this transformer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from src.integrity_kernel import stamp_canonical_hashes, stable_hash
from src.semantic_passage_v1 import (
    SELECTION_ORIGIN_COVERAGE,
    SELECTION_ORIGIN_PROPOSAL,
    SEMANTIC_PASSAGE_VERSION,
    LEGACY_SEMANTIC_PASSAGE_VERSION,
)
from src.serving_relations_v1 import confirm_relation_set, proposed_relations

LEGACY_TRANSFORM_VERSION = "semantic-generic-v1.0.0"
TRANSFORM_VERSION = "semantic-generic-v1.1.0"
_SEMANTIC_PASSAGE_BASE_KEYS = frozenset(
    {"version", "source_bound", "selection_origin", "spans"}
)
_SEMANTIC_PASSAGE_PROPOSAL_KEYS = _SEMANTIC_PASSAGE_BASE_KEYS | frozenset(
    {"formation_mode", "model", "source_blocks_hash", "proposal_hash"}
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _semantic_passage_metadata(item: dict[str, Any]) -> dict[str, Any] | None:
    value = item.get("semantic_passage")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("semantic_passage_metadata_invalid")
    if (
        value.get("source_bound") is not True
        or value.get("version") not in {LEGACY_SEMANTIC_PASSAGE_VERSION, SEMANTIC_PASSAGE_VERSION}
    ):
        raise ValueError("semantic_passage_metadata_invalid")

    origin = str(value.get("selection_origin") or "")
    expected_keys = (
        _SEMANTIC_PASSAGE_PROPOSAL_KEYS
        if origin == SELECTION_ORIGIN_PROPOSAL
        else _SEMANTIC_PASSAGE_BASE_KEYS
        if origin == SELECTION_ORIGIN_COVERAGE
        else None
    )
    if expected_keys is None or set(value) - {"source_mapping"} != expected_keys:
        raise ValueError("semantic_passage_metadata_invalid")

    if value["version"] == SEMANTIC_PASSAGE_VERSION and "source_mapping" not in value:
        raise ValueError("semantic_source_mapping_invalid")

    spans = value.get("spans")
    if not isinstance(spans, list) or not spans:
        raise ValueError("semantic_passage_metadata_invalid")
    for span in spans:
        if (
            not isinstance(span, dict)
            or set(span) != {"block_id", "start", "end"}
            or not str(span.get("block_id") or "").strip()
            or isinstance(span.get("start"), bool)
            or isinstance(span.get("end"), bool)
            or not isinstance(span.get("start"), int)
            or not isinstance(span.get("end"), int)
            or span["start"] < 0
            or span["end"] <= span["start"]
        ):
            raise ValueError("semantic_passage_metadata_invalid")

    result = {
        "version": value["version"],
        "source_bound": True,
        "selection_origin": origin,
        "spans": [dict(span) for span in spans],
    }
    if "source_mapping" in value:
        mapping = value["source_mapping"]
        if not isinstance(mapping, list):
            raise ValueError("semantic_source_mapping_invalid")
        for row in mapping:
            if not isinstance(row, dict):
                raise ValueError("semantic_source_mapping_invalid")
            if row.get("kind") == "join_separator":
                valid = (value["version"] == SEMANTIC_PASSAGE_VERSION
                         and set(row) == {"kind", "text", "left_fragment_id", "right_fragment_id"}
                         and row["text"] == " "
                         and all(isinstance(row.get(key), str) and row[key].strip()
                                 for key in ("left_fragment_id", "right_fragment_id")))
            else:
                valid = (set(row) == {"fragment_id", "raw_start", "raw_end", "source_page", "bbox"}
                         and type(row["raw_start"]) is int and type(row["raw_end"]) is int
                         and 0 <= row["raw_start"] < row["raw_end"])
            if not valid:
                raise ValueError("semantic_source_mapping_invalid")
        result["source_mapping"] = deepcopy(mapping)
    if origin == SELECTION_ORIGIN_PROPOSAL:
        if str(value.get("formation_mode") or "") not in {"semantic-source-bound-v1", "semantic-source-bound-v2"}:
            raise ValueError("semantic_passage_metadata_invalid")
        if not str(value.get("model") or "").strip():
            raise ValueError("semantic_passage_metadata_invalid")
        for key in ("source_blocks_hash", "proposal_hash"):
            if not _SHA256_RE.fullmatch(str(value.get(key) or "")):
                raise ValueError("semantic_passage_metadata_invalid")
        result.update(
            {
                "formation_mode": value["formation_mode"],
                "model": str(value["model"]),
                "source_blocks_hash": str(value["source_blocks_hash"]),
                "proposal_hash": str(value["proposal_hash"]),
            }
        )
    return result


def _system_candidate_metadata(item: dict[str, Any]) -> dict[str, Any]:
    """Persist only closed system-generated F1 evidence from the semantic spec."""

    source = item.get("metadata")
    source = source if isinstance(source, dict) else {}
    out: dict[str, Any] = {}
    for key in ("passage_formation", "source_occurrence_authority", "decision_unit_construction"):
        value = source.get(key)
        if isinstance(value, dict):
            out[key] = deepcopy(value)
    semantics_evidence = item.get("recommendation_semantics_evidence")
    if isinstance(semantics_evidence, dict):
        out["recommendation_semantics_evidence"] = deepcopy(semantics_evidence)
    relation_evidence = item.get("knowledge_relation_evidence")
    if isinstance(relation_evidence, dict):
        out["knowledge_relation_evidence"] = deepcopy(relation_evidence)
    return out


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
    evidence_blocks = None
    mapping_blocks = None
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
        semantic_passage = _semantic_passage_metadata(item)
        if semantic_passage is not None and "source_mapping" in semantic_passage:
            from src.semantic_passage_v1 import _reconstructed_blocks
            from src.source_layout_v1 import mapped_raw_spans
            from src.object_taxonomy_v1 import extract_object_type
            if mapping_blocks is None:
                mapping_blocks = {public["block_id"]: (public, source) for public, source in _reconstructed_blocks(
                    row for row in raw_rows if extract_object_type(row)[0] != "heading")}
            expected_mapping = []
            for span in semantic_passage["spans"]:
                if span["block_id"] not in mapping_blocks:
                    raise ValueError("semantic_source_mapping_unknown_block")
                public, source = mapping_blocks[span["block_id"]]
                if span["end"] > len(public["text"]):
                    raise ValueError("source_bound_field_bounds_invalid")
                expected_mapping.extend(mapped_raw_spans(source, start=span["start"], end=span["end"]))
            if semantic_passage["version"] == LEGACY_SEMANTIC_PASSAGE_VERSION:
                expected_mapping = [row for row in expected_mapping if row.get("kind") != "join_separator"]
            if semantic_passage["source_mapping"] != expected_mapping:
                raise ValueError("semantic_source_mapping_invalid")
        object_transform_version = (TRANSFORM_VERSION
            if semantic_passage and semantic_passage["version"] == SEMANTIC_PASSAGE_VERSION
            else LEGACY_TRANSFORM_VERSION)
        system_metadata = _system_candidate_metadata(item)
        from src.decision_unit_construction_v1 import KEY as DECISION_UNIT_KEY, reconstruct
        if DECISION_UNIT_KEY in system_metadata:
            rebuilt = reconstruct(system_metadata[DECISION_UNIT_KEY], raw_by_id)
            if rebuilt != item.get("clean_text", item.get("text")):
                raise ValueError("decision_unit_source_fidelity_failure")
        from src.source_bound_fields_v2 import KEY, bind_fields, MODE
        if semantic_passage and semantic_passage.get("formation_mode") == MODE:
            from src.semantic_passage_v1 import semantic_source_blocks
            from src.object_taxonomy_v1 import extract_object_type
            if evidence_blocks is None:
                evidence_blocks = {b["block_id"]: b for b in semantic_source_blocks(
                    r for r in raw_rows if extract_object_type(r)[0] != "heading")}
            selected = []
            for span in semantic_passage["spans"]:
                block = evidence_blocks.get(span["block_id"])
                if block is None:
                    raise ValueError("source_bound_field_unknown_block")
                if span["end"] > len(block["text"]):
                    raise ValueError("source_bound_field_bounds_invalid")
                selected.append({**span, "text": block["text"][span["start"]:span["end"]]})
            record = item.get(KEY)
            rebuilt = bind_fields(record.get("evidence") if isinstance(record, dict) else None,
                                  selected=selected, candidate_text=item.get("clean_text", item["text"]),
                                  proposed_type=item.get("proposed_object_type", "unclassified"))
            if record != rebuilt:
                raise ValueError("source_bound_fields_invalid")
            system_metadata[KEY] = rebuilt
        elif KEY in item:
            raise ValueError("source_bound_fields_contract_mismatch")
        if semantic_passage is not None:
            system_metadata["semantic_passage"] = semantic_passage
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
            **(
                {"proposed_recommendation_semantics": deepcopy(item["proposed_recommendation_semantics"])}
                if isinstance(item.get("proposed_recommendation_semantics"), dict)
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
            **(
                {"proposed_knowledge_relations": deepcopy(item["proposed_knowledge_relations"])}
                if isinstance(item.get("proposed_knowledge_relations"), list)
                else {}
            ),
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
            **({"metadata": system_metadata} if system_metadata else {}),
            "governance": _governance(item.get("review_track", "clinical"), high),
            "provenance": {
                "transformation_mode": "deterministic",
                "created_by": f"system:{object_transform_version}",
                "source_extract_hash": raw_extract_hash,
                "semantic_spec_version": spec["spec_version"],
                "semantic_spec_hash": spec_hash,
                "transform_version": object_transform_version,
                "content_hash": "0" * 64,
                "proposal_id": None,
                "canonical_object_hash": "0" * 64,
                "source_fragments": refs,
                "previous_object_version": None,
                "revision_reason": None,
                "revision_patch_hash": None,
            },
        }
        from src.source_bound_fields_v2 import CONTEXT_KEY, bind_context, context_record
        if CONTEXT_KEY in item:
            if not semantic_passage or semantic_passage.get("formation_mode") != MODE:
                raise ValueError("source_bound_context_requires_v2")
            entries = item[CONTEXT_KEY]
            if not isinstance(entries, list):
                raise ValueError("source_bound_context_invalid")
            raw_context = [{key: row[key] for key in ("role", "span", "unresolved_reason")} for row in entries]
            rebuilt_context = bind_context(raw_context, fragments=raw_rows)
            if rebuilt_context != entries:
                raise ValueError("source_bound_context_invalid")
            obj.setdefault("metadata", {})[CONTEXT_KEY] = context_record(rebuilt_context, obj=obj)
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
    ap.add_argument("--schema", type=Path, default=Path("schemas/knowledge_object.schema.v1.4.json"))
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
