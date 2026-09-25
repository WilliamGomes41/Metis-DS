"""D3.2 source-bound recommendation semantics proposal and Admission.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: metrics teller noemer score-must-drop
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED, admission_of, apply_admission_gate
from src.operations_console_v1 import OperationsConsole, SCHEMA_V12, SCHEMA_V13
from src.pre_review_semantic_v1 import (
    _proposal_schema,
    _replay_identity,
    semantic_spec_from_fragments,
)
from src.processing_diagnostics_v1 import processing_issue_family
from src.recommendation_semantics_v1 import (
    PROPOSED_FIELD,
    source_literal_strength,
)
from src.semantic_passage_v1 import (
    SemanticPassageError,
    semantic_source_blocks,
    semantic_units_from_proposal,
)
from src.semantic_transform_generic_v1 import transform, validate


ROOT = Path(__file__).resolve().parents[1]


def _fragment(
    fragment_id: str,
    text: str,
    *,
    object_type: str | None = None,
    section_path: list[str] | None = None,
) -> dict:
    row = {
        "fragment_id": fragment_id,
        "fragment_hash": (fragment_id[0] if fragment_id else "a") * 64,
        "raw_text": text,
        "clean_text": text,
        "section_path": list(section_path or ["Aanbeveling"]),
        "source_page": 1,
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "source_locator": {
            "locator_type": "page_bbox",
            "locator_value": f"page:1;bbox:{fragment_id}",
        },
        "parser_version": "test-parser-v1",
    }
    if object_type:
        row["object_type"] = object_type
    return row


def _span(block: dict, text: str | None = None) -> dict:
    selected = block["text"] if text is None else text
    start = block["text"].index(selected)
    return {
        "block_id": block["block_id"],
        "start": start,
        "end": start + len(selected),
    }


def _proposal(
    candidate_block: dict,
    *,
    direction: str = "for",
    strength: str | None = "weak",
    status: str = "explicit",
    strength_block: dict | None = None,
) -> dict:
    return {
        "objects": [
            {
                "spans": [_span(candidate_block)],
                "proposed_object_type": "recommendation",
                "recommendation_semantics": {
                    "direction": direction,
                    "direction_evidence": _span(candidate_block),
                    "strength": strength,
                    "strength_status": status,
                    "strength_evidence": (
                        _span(strength_block) if strength_block is not None else None
                    ),
                },
            }
        ],
        "abstain_reason": None,
    }


def _manifest() -> dict:
    return {
        "canonical_source": {
            "source_id": "source-d32",
            "title": "D3.2 source",
            "publisher": "V&VN",
            "source_url": "https://example.org/d32",
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


def test_source_literal_normalization_never_maps_conditional_alone_to_weak() -> None:
    assert source_literal_strength("Sterke aanbeveling") == "strong"
    assert source_literal_strength("Zwakke aanbeveling") == "weak"
    assert source_literal_strength("Zwakke (conditionele) aanbeveling") == "weak"
    assert source_literal_strength("Conditionele aanbeveling") is None
    assert source_literal_strength("Voorwaardelijke aanbeveling") is None


def test_semantic_kernel_reconstructs_strength_label_outside_candidate_text() -> None:
    path = ["Behandeling", "Zwakke (conditionele) aanbeveling"]
    heading = _fragment(
        "h",
        "Zwakke (conditionele) aanbeveling",
        object_type="heading",
        section_path=path,
    )
    candidate = _fragment(
        "p",
        "De werkgroep adviseert de verpleegkundige de interventie te gebruiken.",
        section_path=path,
    )
    candidate_block = semantic_source_blocks([candidate])[0]
    evidence_blocks = semantic_source_blocks([heading, candidate])
    strength_block = next(block for block in evidence_blocks if block["text"].startswith("Zwakke"))

    units = semantic_units_from_proposal(
        [candidate],
        evidence_fragments=[heading, candidate],
        document_id="doc-d32",
        proposal=_proposal(candidate_block, strength_block=strength_block),
    )

    [unit] = units
    semantics = unit[PROPOSED_FIELD]
    assert semantics["direction"] == "for"
    assert semantics["strength"] == "weak"
    assert semantics["strength_status"] == "explicit"
    assert semantics["direction_evidence_span"] == candidate["clean_text"]
    assert semantics["strength_evidence_span"] == "Zwakke (conditionele) aanbeveling"
    assert semantics["source_label"] == "Zwakke (conditionele) aanbeveling"
    assert semantics["normalization_scheme"] == "source_literal_v1"
    evidence = unit["recommendation_semantics_evidence"]
    assert evidence["direction"]["source_fragment_ids"] == ["p"]
    assert evidence["strength"]["source_fragment_ids"] == ["h"]


def test_explicit_weak_with_only_conditional_evidence_fails_closed() -> None:
    path = ["Behandeling", "Conditionele aanbeveling"]
    heading = _fragment(
        "h",
        "Conditionele aanbeveling",
        object_type="heading",
        section_path=path,
    )
    candidate = _fragment(
        "p",
        "De werkgroep adviseert de verpleegkundige de interventie te gebruiken.",
        section_path=path,
    )
    candidate_block = semantic_source_blocks([candidate])[0]
    strength_block = semantic_source_blocks([heading, candidate])[0]

    with pytest.raises(SemanticPassageError, match="recommendation_strength_literal_mismatch"):
        semantic_units_from_proposal(
            [candidate],
            evidence_fragments=[heading, candidate],
            document_id="doc-d32",
            proposal=_proposal(candidate_block, strength_block=strength_block),
        )


def test_unmapped_explicit_label_is_preserved_for_admission_block() -> None:
    path = ["Behandeling", "Conditionele aanbeveling"]
    heading = _fragment(
        "h",
        "Conditionele aanbeveling",
        object_type="heading",
        section_path=path,
    )
    candidate = _fragment(
        "p",
        "De werkgroep adviseert de verpleegkundige de interventie te gebruiken.",
        section_path=path,
    )
    candidate_block = semantic_source_blocks([candidate])[0]
    strength_block = semantic_source_blocks([heading, candidate])[0]
    proposal = _proposal(
        candidate_block,
        strength=None,
        status="unmapped",
        strength_block=strength_block,
    )

    [unit] = semantic_units_from_proposal(
        [candidate],
        evidence_fragments=[heading, candidate],
        document_id="doc-d32",
        proposal=proposal,
    )
    assert unit[PROPOSED_FIELD]["strength"] is None
    assert unit[PROPOSED_FIELD]["strength_status"] == "unmapped"
    assert unit[PROPOSED_FIELD]["source_label"] == "Conditionele aanbeveling"


def test_not_stated_strength_is_valid_without_strength_evidence() -> None:
    candidate = _fragment(
        "p",
        "De werkgroep adviseert de verpleegkundige de interventie te gebruiken.",
    )
    block = semantic_source_blocks([candidate])[0]
    proposal = _proposal(
        block,
        strength=None,
        status="not_stated",
        strength_block=None,
    )
    [unit] = semantic_units_from_proposal(
        [candidate],
        document_id="doc-d32",
        proposal=proposal,
    )
    semantics = unit[PROPOSED_FIELD]
    assert semantics["strength"] is None
    assert semantics["strength_status"] == "not_stated"
    assert semantics["strength_evidence_span"] is None
    assert semantics["source_label"] is None


def test_not_stated_conflicts_with_literal_strength_in_candidate_context() -> None:
    candidate = _fragment(
        "p",
        "Zwakke aanbeveling: de werkgroep adviseert de verpleegkundige de interventie te gebruiken.",
    )
    block = semantic_source_blocks([candidate])[0]
    proposal = _proposal(
        block,
        strength=None,
        status="not_stated",
        strength_block=None,
    )
    with pytest.raises(SemanticPassageError, match="recommendation_strength_not_stated_conflict"):
        semantic_units_from_proposal(
            [candidate],
            document_id="doc-d32",
            proposal=proposal,
        )


def test_direction_evidence_must_be_inside_candidate_selection() -> None:
    candidate = _fragment(
        "p",
        "De werkgroep adviseert de verpleegkundige de interventie te gebruiken.",
    )
    other = _fragment(
        "q",
        "Dit is geen richtingbewijs.",
        section_path=["Aanbeveling"],
    )
    candidate_block = semantic_source_blocks([candidate])[0]
    other_block = semantic_source_blocks([other])[0]
    proposal = _proposal(
        candidate_block,
        strength=None,
        status="not_stated",
        strength_block=None,
    )
    proposal["objects"][0]["recommendation_semantics"]["direction_evidence"] = _span(other_block)

    with pytest.raises(SemanticPassageError, match="recommendation_direction_evidence_outside_candidate"):
        semantic_units_from_proposal(
            [candidate],
            evidence_fragments=[candidate, other],
            document_id="doc-d32",
            proposal=proposal,
        )


def test_non_recommendation_cannot_carry_recommendation_semantics() -> None:
    candidate = _fragment("p", "Een definitie is een omschrijving.")
    block = semantic_source_blocks([candidate])[0]
    proposal = _proposal(block, strength=None, status="not_stated", strength_block=None)
    proposal["objects"][0]["proposed_object_type"] = "definition"

    with pytest.raises(SemanticPassageError, match="recommendation_semantics_on_non_recommendation"):
        semantic_units_from_proposal(
            [candidate],
            document_id="doc-d32",
            proposal=proposal,
        )


def test_provider_schema_requires_closed_recommendation_semantics_property() -> None:
    schema = _proposal_schema()
    item = schema["properties"]["objects"]["items"]
    assert "recommendation_semantics" in item["required"]
    sem = item["properties"]["recommendation_semantics"]
    assert set(sem["properties"]["direction"]["enum"]) == {"for", "against"}
    assert set(value for value in sem["properties"]["strength"]["enum"] if value) == {
        "strong",
        "weak",
    }


def test_replay_identity_hashes_evidence_blocks_as_part_of_semantic_input() -> None:
    source = [_fragment("p", "Gebruik behandeling X.")]
    blocks = semantic_source_blocks(source)
    evidence_a = semantic_source_blocks(source)
    evidence_b = semantic_source_blocks(
        [_fragment("h", "Zwakke aanbeveling", object_type="heading"), *source]
    )
    context = {"snapshot_id": "snap-1", "source_sha256": "f" * 64}
    first = _replay_identity(
        document_id="doc-d32",
        model="test-model",
        blocks=blocks,
        evidence_blocks=evidence_a,
        source_fragments=source,
        formation_context=context,
    )
    second = _replay_identity(
        document_id="doc-d32",
        model="test-model",
        blocks=blocks,
        evidence_blocks=evidence_b,
        source_fragments=source,
        formation_context=context,
    )
    assert first is not None and second is not None
    assert first["source_blocks_hash"] != second["source_blocks_hash"]


def test_end_to_end_semantic_proposal_persists_v13_and_admits_source_bound_weak_recommendation() -> None:
    path = ["Behandeling", "Zwakke aanbeveling"]
    heading = _fragment(
        "h",
        "Zwakke aanbeveling",
        object_type="heading",
        section_path=path,
    )
    candidate = _fragment(
        "p",
        "De werkgroep adviseert de verpleegkundige de interventie te gebruiken.",
        section_path=path,
    )
    fragments = [heading, candidate]

    def fake_post(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        source_payload = json.loads(payload["input"][1]["content"])
        candidate_block = source_payload["source_blocks"][0]
        strength_block = next(
            block
            for block in source_payload["evidence_blocks"]
            if block["text"] == "Zwakke aanbeveling"
        )
        return _response(_proposal(candidate_block, strength_block=strength_block))

    spec = semantic_spec_from_fragments(
        document_id="doc-d32",
        title="D3.2",
        family="kwaliteit",
        class_="richtlijn",
        fragments=fragments,
        content_kind="pdf",
        api_key="product-key",
        model="test-model",
        post_json=fake_post,
    )
    rows = transform(spec, _manifest(), fragments)
    assert validate(rows, SCHEMA_V13) == []

    recommendation = next(
        row for row in rows if row.get("proposed_object_type") == "recommendation"
    )
    assert recommendation[PROPOSED_FIELD]["direction"] == "for"
    assert recommendation[PROPOSED_FIELD]["strength"] == "weak"
    evidence = recommendation["metadata"]["recommendation_semantics_evidence"]
    assert evidence["strength"]["source_fragment_ids"] == ["h"]

    gated = apply_admission_gate(
        rows,
        klasse="richtlijn",
        fragments=fragments,
        document_version="1.0",
        source_hash="f" * 64,
    )
    admitted = next(row for row in gated if row["object_id"] == recommendation["object_id"])
    assert admission_of(admitted)["gate_result"] == GATE_ALLOWED
    assert "confirmed_recommendation_semantics" not in admitted


def test_unmapped_semantic_strength_is_blocked_and_diagnostic_family_is_semantic_contract() -> None:
    path = ["Behandeling", "Conditionele aanbeveling"]
    heading = _fragment(
        "h",
        "Conditionele aanbeveling",
        object_type="heading",
        section_path=path,
    )
    candidate = _fragment(
        "p",
        "De werkgroep adviseert de verpleegkundige de interventie te gebruiken.",
        section_path=path,
    )
    candidate_block = semantic_source_blocks([candidate])[0]
    strength_block = semantic_source_blocks([heading, candidate])[0]
    [unit] = semantic_units_from_proposal(
        [candidate],
        evidence_fragments=[heading, candidate],
        document_id="doc-d32",
        proposal=_proposal(
            candidate_block,
            strength=None,
            status="unmapped",
            strength_block=strength_block,
        ),
    )
    spec = {
        "spec_version": "test",
        "document_id": "doc-d32",
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": ["test"],
        "objects": [unit],
    }
    [obj] = transform(spec, _manifest(), [heading, candidate])
    [gated] = apply_admission_gate(
        [obj],
        klasse="richtlijn",
        fragments=[heading, candidate],
        document_version="1.0",
        source_hash="f" * 64,
    )
    admission = admission_of(gated)
    assert admission["gate_result"] == GATE_BLOCKED
    assert "recommendation_strength_unmapped" in admission["reason_codes"]
    assert processing_issue_family("recommendation_strength_unmapped") == "semantic_contract"


def test_coverage_remainder_has_no_semantics_and_no_admission() -> None:
    selected = _fragment(
        "a",
        "De werkgroep adviseert de verpleegkundige de interventie te gebruiken.",
    )
    remainder = _fragment("b", "Aanvullende achtergrondinformatie.")
    blocks = semantic_source_blocks([selected, remainder])
    units = semantic_units_from_proposal(
        [selected, remainder],
        document_id="doc-d32",
        proposal=_proposal(
            blocks[0],
            strength=None,
            status="not_stated",
            strength_block=None,
        ),
    )
    spec = {
        "spec_version": "test",
        "document_id": "doc-d32",
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": ["test"],
        "objects": units,
    }
    rows = transform(spec, _manifest(), [selected, remainder])
    gated = apply_admission_gate(
        rows,
        klasse="richtlijn",
        fragments=[selected, remainder],
        document_version="1.0",
        source_hash="f" * 64,
    )
    coverage = next(
        row
        for row in gated
        if ((row.get("metadata") or {}).get("semantic_passage") or {}).get("selection_origin")
        == "coverage_remainder"
    )
    assert PROPOSED_FIELD not in coverage
    assert admission_of(coverage) == {}


def test_semantic_recommendation_without_new_semantics_is_hard_blocked_not_legacy_migrated() -> None:
    candidate = _fragment(
        "p",
        "De werkgroep adviseert de verpleegkundige de interventie te gebruiken.",
    )
    block = semantic_source_blocks([candidate])[0]
    units = semantic_units_from_proposal(
        [candidate],
        document_id="doc-d32",
        proposal={
            "objects": [
                {
                    "spans": [_span(block)],
                    "proposed_object_type": "recommendation",
                }
            ],
            "abstain_reason": None,
        },
    )
    spec = {
        "spec_version": "test",
        "document_id": "doc-d32",
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": ["test"],
        "objects": units,
    }
    [obj] = transform(spec, _manifest(), [candidate])
    [gated] = apply_admission_gate(
        [obj],
        klasse="richtlijn",
        fragments=[candidate],
        document_version="1.0",
        source_hash="f" * 64,
    )
    admission = admission_of(gated)
    assert admission["gate_result"] == GATE_BLOCKED
    assert "recommendation_direction_missing" in admission["reason_codes"]
    assert "recommendation_semantics_invalid" in admission["reason_codes"]
    assert "proposed_recommendation_strength" not in gated


def test_runtime_current_schema_is_v13_while_legacy_v12_remains_addressable(tmp_path: Path) -> None:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
    )
    assert console.schema_path == SCHEMA_V13
    assert Path(SCHEMA_V12).name == "knowledge_object.schema.v1.2.json"
    assert Path(SCHEMA_V13).name == "knowledge_object.schema.v1.3.json"
