"""D4.2 source-bound many-to-many KnowledgeRelation proposal regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: metrics teller noemer score-must-drop
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED, admission_of, apply_admission_gate
from src.knowledge_relation_proposal_v1 import (
    relation_endpoint_compatible,
    relation_proposal_admission_codes,
)
from src.knowledge_relations_v1 import (
    PROPOSED_FIELD as PROPOSED_RELATIONS_FIELD,
    build_knowledge_relation,
)
from src.operations_console_v1 import OperationsConsole, SCHEMA_V13, SCHEMA_V14
from src.pre_review_semantic_v1 import _proposal_schema, semantic_spec_from_fragments
from src.processing_diagnostics_v1 import processing_issue_family
from src.semantic_passage_v1 import semantic_source_blocks
from src.semantic_transform_generic_v1 import transform, validate


ROOT = Path(__file__).resolve().parents[1]


def _fragment(
    fragment_id: str,
    text: str,
    *,
    section_path: list[str] | None = None,
) -> dict:
    return {
        "fragment_id": fragment_id,
        "fragment_hash": hashlib.sha256(fragment_id.encode("utf-8")).hexdigest(),
        "raw_text": text,
        "clean_text": text,
        "section_path": list(section_path or ["Behandeling"]),
        "source_page": 1,
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "source_locator": {
            "locator_type": "page_bbox",
            "locator_value": f"page:1;bbox:{fragment_id}",
        },
        "parser_version": "test-parser-v1",
    }


def _span(block: dict) -> dict:
    return {
        "block_id": block["block_id"],
        "start": 0,
        "end": len(block["text"]),
    }


def _recommendation_semantics(block: dict) -> dict:
    return {
        "direction": "for",
        "direction_evidence": _span(block),
        "strength": None,
        "strength_status": "not_stated",
        "strength_evidence": None,
    }


def _manifest() -> dict:
    return {
        "canonical_source": {
            "source_id": "source-d42",
            "title": "D4.2 source",
            "publisher": "V&VN",
            "source_url": "https://example.org/d42",
            "source_type": "pdf",
            "source_level": 1,
            "canonicality": "canonical",
            "source_checksum": "f" * 64,
            "checksum_algorithm": "sha256",
            "integrity_status": "verified",
            "publication_date": "2026-09-25",
            "version": "1.0",
        }
    }


def _response(proposal: dict) -> dict:
    return {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(proposal)}],
            }
        ]
    }


def _many_to_many_proposal(blocks: list[dict]) -> dict:
    by_text = {block["text"]: block for block in blocks}
    condition = by_text[
        "De patiënt heeft een verhoogd risico wanneer score X aanwezig is."
    ]
    explanation = by_text[
        "Deze toelichting beschrijft waarom intensieve monitoring nodig is."
    ]
    rec_a = by_text[
        "De werkgroep adviseert de verpleegkundige interventie A te gebruiken."
    ]
    rec_b = by_text[
        "De werkgroep adviseert de verpleegkundige interventie B te gebruiken."
    ]
    return {
        "objects": [
            {
                "spans": [_span(condition)],
                "proposed_object_type": "condition",
                "recommendation_semantics": None,
            },
            {
                "spans": [_span(rec_a)],
                "proposed_object_type": "recommendation",
                "recommendation_semantics": _recommendation_semantics(rec_a),
            },
            {
                "spans": [_span(explanation)],
                "proposed_object_type": "explanation",
                "recommendation_semantics": None,
            },
            {
                "spans": [_span(rec_b)],
                "proposed_object_type": "recommendation",
                "recommendation_semantics": _recommendation_semantics(rec_b),
            },
        ],
        "relations": [
            {
                "source_spans": [_span(rec_a)],
                "relation_type": "applies_if",
                "target_spans": [_span(condition)],
                "evidence_spans": [_span(condition)],
            },
            {
                "source_spans": [_span(rec_b)],
                "relation_type": "applies_if",
                "target_spans": [_span(condition)],
                "evidence_spans": [_span(condition)],
            },
        ],
        "abstain_reason": None,
    }


def test_provider_schema_has_closed_source_bound_relation_contract() -> None:
    schema = _proposal_schema()
    assert "relations" in schema["required"]
    relation = schema["properties"]["relations"]["items"]
    assert set(relation["required"]) == {
        "source_spans",
        "relation_type",
        "target_spans",
        "evidence_spans",
    }
    assert set(relation["properties"]["relation_type"]["enum"]) == {
        "applies_if",
        "except_if",
        "defines",
        "explains",
        "supported_by",
        "supersedes",
    }
    assert "parent" not in relation["properties"]["relation_type"]["enum"]
    assert "child" not in relation["properties"]["relation_type"]["enum"]


def test_endpoint_policy_keeps_semantic_roles_explicit() -> None:
    assert relation_endpoint_compatible(
        "applies_if",
        source_type="recommendation",
        target_type="condition",
    )
    assert relation_endpoint_compatible(
        "except_if",
        source_type="recommendation",
        target_type="exception",
    )
    assert relation_endpoint_compatible(
        "supported_by",
        source_type="recommendation",
        target_type="explanation",
    )
    assert not relation_endpoint_compatible(
        "applies_if",
        source_type="recommendation",
        target_type="recommendation",
    )
    assert not relation_endpoint_compatible(
        "parent",
        source_type="recommendation",
        target_type="condition",
    )


def test_end_to_end_semantic_proposal_persists_non_adjacent_many_to_many_relations() -> None:
    fragments = [
        _fragment(
            "condition",
            "De patiënt heeft een verhoogd risico wanneer score X aanwezig is.",
        ),
        _fragment(
            "rec-a",
            "De werkgroep adviseert de verpleegkundige interventie A te gebruiken.",
        ),
        _fragment(
            "explanation",
            "Deze toelichting beschrijft waarom intensieve monitoring nodig is.",
        ),
        _fragment(
            "rec-b",
            "De werkgroep adviseert de verpleegkundige interventie B te gebruiken.",
        ),
    ]

    def fake_post(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        source_payload = json.loads(payload["input"][1]["content"])
        return _response(_many_to_many_proposal(source_payload["source_blocks"]))

    spec = semantic_spec_from_fragments(
        document_id="doc-d42",
        title="D4.2",
        family="kwaliteit",
        class_="richtlijn",
        fragments=fragments,
        content_kind="pdf",
        api_key="product-key",
        model="test-model",
        post_json=fake_post,
    )
    rows = transform(spec, _manifest(), fragments)
    assert validate(rows, SCHEMA_V14) == []

    condition = next(row for row in rows if row.get("proposed_object_type") == "condition")
    recommendations = [
        row for row in rows if row.get("proposed_object_type") == "recommendation"
    ]
    assert len(recommendations) == 2

    relation_ids = set()
    for recommendation in recommendations:
        relations = recommendation[PROPOSED_RELATIONS_FIELD]
        assert len(relations) == 1
        [relation] = relations
        assert relation["relation_type"] == "applies_if"
        assert relation["target_object_id"] == condition["object_id"]
        assert relation["target_object_version"] == condition["object_version"]
        relation_ids.add(relation["relation_id"])

        # Legacy is compatibility mirror only and remains unconfirmed.
        assert recommendation["relations"] == [
            {
                "relation_type": "applies_if",
                "target_object_id": condition["object_id"],
                "target_object_version": condition["object_version"],
                "confirmed": False,
            }
        ]
        evidence = recommendation["metadata"]["knowledge_relation_evidence"]
        assert evidence["version"] == "knowledge-relation-evidence-v1"
        [evidence_row] = evidence["relations"]
        assert evidence_row["relation_id"] == relation["relation_id"]
        assert evidence_row["target_spans"][0]["source_fragment_ids"] == ["condition"]

    assert len(relation_ids) == 2, "many-to-many edges must retain source-specific identity"

    gated = apply_admission_gate(
        rows,
        klasse="richtlijn",
        fragments=fragments,
        document_version="1.0",
        source_hash="f" * 64,
    )
    gated_by_id = {row["object_id"]: row for row in gated}
    for recommendation in recommendations:
        admission = admission_of(gated_by_id[recommendation["object_id"]])
        assert admission["gate_result"] == GATE_ALLOWED, admission["reason_codes"]
        assert not any(code.startswith("relation_") for code in admission["reason_codes"])
        assert "confirmed_knowledge_relations" not in gated_by_id[recommendation["object_id"]]


def test_empty_provider_relation_set_does_not_reintroduce_adjacency_relation() -> None:
    fragments = [
        _fragment(
            "condition",
            "De patiënt heeft een verhoogd risico wanneer score X aanwezig is.",
        ),
        _fragment(
            "rec",
            "De werkgroep adviseert de verpleegkundige interventie A te gebruiken.",
        ),
    ]
    blocks = semantic_source_blocks(fragments)
    by_text = {block["text"]: block for block in blocks}
    condition = by_text[fragments[0]["clean_text"]]
    rec = by_text[fragments[1]["clean_text"]]
    proposal = {
        "objects": [
            {
                "spans": [_span(condition)],
                "proposed_object_type": "condition",
                "recommendation_semantics": None,
            },
            {
                "spans": [_span(rec)],
                "proposed_object_type": "recommendation",
                "recommendation_semantics": _recommendation_semantics(rec),
            },
        ],
        "relations": [],
        "abstain_reason": None,
    }

    def fake_post(_url: str, _headers: dict, _payload: dict, _timeout: int) -> dict:
        return _response(proposal)

    spec = semantic_spec_from_fragments(
        document_id="doc-d42-no-adj",
        title="D4.2 no adjacency",
        family="kwaliteit",
        class_="richtlijn",
        fragments=fragments,
        content_kind="pdf",
        api_key="product-key",
        model="test-model",
        post_json=fake_post,
    )
    recommendation = next(
        row
        for row in spec["objects"]
        if row.get("proposed_object_type") == "recommendation"
    )
    assert recommendation.get(PROPOSED_RELATIONS_FIELD) is None
    assert recommendation.get("relations") == []


def test_admission_blocks_missing_target_version_endpoint_mismatch_and_missing_evidence() -> None:
    source = {
        "object_id": "rec-1",
        "object_version": "1.0",
        "object_type": "unclassified",
        "proposed_object_type": "recommendation",
        "relations": [],
        "confirmed_relations": [],
        "metadata": {},
    }
    target = {
        "object_id": "rec-2",
        "object_version": "1.0",
        "object_type": "unclassified",
        "proposed_object_type": "recommendation",
        "relations": [],
        "confirmed_relations": [],
        "metadata": {},
    }
    relation = build_knowledge_relation(
        source_object_id="rec-1",
        source_object_version="1.0",
        relation_type="applies_if",
        target_object_id="rec-2",
        target_object_version="1.0",
    )
    source[PROPOSED_RELATIONS_FIELD] = [relation]
    codes = relation_proposal_admission_codes(source, objects=[source, target])
    assert "relation_endpoint_type_invalid" in codes
    assert "relation_evidence_missing" in codes

    target["object_version"] = "1.1"
    codes = relation_proposal_admission_codes(source, objects=[source, target])
    assert "relation_target_version_mismatch" in codes


def test_divergent_legacy_mirror_is_blocked_and_diagnosable() -> None:
    source = {
        "object_id": "rec-1",
        "object_version": "1.0",
        "object_type": "unclassified",
        "proposed_object_type": "recommendation",
        "confirmed_relations": [],
        "metadata": {},
    }
    target = {
        "object_id": "condition-1",
        "object_version": "1.0",
        "object_type": "unclassified",
        "proposed_object_type": "condition",
        "relations": [],
        "confirmed_relations": [],
        "metadata": {},
    }
    relation = build_knowledge_relation(
        source_object_id="rec-1",
        source_object_version="1.0",
        relation_type="applies_if",
        target_object_id="condition-1",
        target_object_version="1.0",
    )
    source[PROPOSED_RELATIONS_FIELD] = [relation]
    source["relations"] = [
        {
            "relation_type": "applies_if",
            "target_object_id": "other-condition",
            "target_object_version": "1.0",
            "confirmed": False,
        }
    ]
    codes = relation_proposal_admission_codes(source, objects=[source, target])
    assert "relation_proposal_invalid" in codes
    assert "relation_legacy_mirror_conflict" in codes
    assert processing_issue_family("relation_legacy_mirror_conflict") == "semantic_contract"


def test_runtime_current_schema_moves_to_v14_without_rewriting_v13(tmp_path: Path) -> None:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
    )
    assert console.schema_path == SCHEMA_V14
    assert Path(SCHEMA_V13).name == "knowledge_object.schema.v1.3.json"
    assert Path(SCHEMA_V14).name == "knowledge_object.schema.v1.4.json"
