"""Coordinate-bearing PDF proof, exact raw mapping and clinical-gap protection.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json

import fitz
import pytest

from src.extract_pdf_v2 import extract
from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
from src.semantic_passage_v1 import semantic_source_blocks, semantic_units_from_proposal, SemanticPassageError
from src.source_layout_v1 import text_view
from src.source_reconstruction_v1 import reconstruct_source_fragments


def pdf(tmp_path, markers=(20, 25, 30), marker_x=25, text_x=90, intervening_lines=True):
    path = tmp_path / "layout.pdf"
    doc = fitz.open()
    page = doc.new_page()
    for i, marker in enumerate(markers):
        y = 100 + i * 80
        page.insert_text((marker_x, y), str(marker), fontsize=10)
        page.insert_text((text_x, y), "Gebruik geen 5 mg binnen 4 uur, tenzij de arts anders adviseert.", fontsize=10)
        if intervening_lines and i < len(markers) - 1:
            for step in range(1, 5):
                page.insert_text((text_x, y + step * 16), "Behoud de individuele situatie en alle uitzonderingen.", fontsize=10)
    doc.save(path)
    doc.close()
    return path


def test_ambiguous_margin_markers_keep_original_extract_and_map_every_clinical_character(tmp_path):
    fragments = extract(pdf(tmp_path), document_id="doc", source_id="source")
    assert not any(row.get("source_text_view") for row in fragments)
    assert any(row.get("source_layout_findings") for row in fragments)
    assert all(row["clean_text"] == row["raw_text"] for row in fragments)
    blocks = semantic_source_blocks(fragments)
    assert any("geen 5 mg binnen 4 uur, tenzij" in block["text"] for block in blocks)
    proposal = {"objects": [{"spans": [{"block_id": blocks[0]["block_id"], "start": 0, "end": len(blocks[0]["text"])}],
                              "proposed_object_type": "recommendation", "recommendation_semantics": None}]}
    decisions = semantic_units_from_proposal(fragments, document_id="doc", proposal=proposal)
    units = materialise_knowledge_candidates(decisions, document_id="doc", fragments=fragments)
    mapping = units[0]["semantic_passage"]["source_mapping"]
    by_id = {row["fragment_id"]: row for row in fragments}
    from src.object_taxonomy_v1 import normalize_visible_prose
    assert normalize_visible_prose("".join(row["text"] if row.get("kind") == "join_separator" else by_id[row["fragment_id"]]["raw_text"][row["raw_start"]:row["raw_end"]] for row in mapping)) == blocks[0]["text"]
    assert all(row["source_page"] == 1 and row["bbox"] for row in mapping if row.get("kind") != "join_separator")
    # Repeated identical prose has distinct position-bound source identities.
    assert len({block["block_id"] for block in blocks}) == len(blocks)


def test_numbered_table_rows_without_five_prose_lines_remain_content(tmp_path):
    fragments = extract(pdf(tmp_path, intervening_lines=False), document_id="doc", source_id="source")
    assert not any(row.get("source_text_view") for row in fragments)
    assert any(row.get("source_layout_findings") for row in fragments)


def test_transform_validates_mapping_and_export_retains_raw_and_view(tmp_path):
    from src.pre_review_semantic_v1 import semantic_spec_from_fragments
    from src.semantic_transform_generic_v1 import transform
    from src.quality_evidence_v1 import record_processing, instant
    from src.processing_evidence_export_v1 import processing_evidence_tables
    fragments = extract(pdf(tmp_path), document_id="doc", source_id="source")
    def provider(_url, _headers, payload, _timeout):
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        proposal = {"objects": [{"spans": [{"block_id": block["block_id"], "start": 0, "end": len(block["text"])}],
                                 "proposed_object_type": "recommendation", "recommendation_semantics": None}],
                    "abstain_reason": None}
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(proposal)}]}]}
    spec = semantic_spec_from_fragments(document_id="doc", title="Fixture", family="test", class_="richtlijn",
        fragments=fragments, content_kind="pdf", api_key="test", model="test", post_json=provider)
    manifest = {"canonical_source": {"source_id": "source", "title": "Fixture", "source_type": "pdf",
        "source_url": "test", "source_level": "national", "canonicality": "canonical",
        "integrity_status": "verified", "source_checksum": "a" * 64}}
    rows = transform(spec, manifest, fragments)
    envelope = {"sha256": "a" * 64}
    record_processing(envelope, rows, fragments=fragments, replay=None, started_at=instant())
    tables, _ = processing_evidence_tables(snapshot_id="snap", revision="r", envelope=envelope, objects=rows)
    assert not any(row["source_text_view"] for row in tables["source_views"])
    assert any(row.get("source_layout_findings") for row in fragments)
    assert any(row["relation"] == "selected_raw_fragment_range" for row in tables["lineage"])
    assert tables["source_views"][0]["raw_text"] == fragments[0]["raw_text"]
    forged = deepcopy(spec)
    item = next(item for item in forged["objects"] if item.get("semantic_passage", {}).get("source_mapping"))
    item["semantic_passage"]["source_mapping"][0]["raw_end"] += 1
    with pytest.raises(ValueError, match="semantic_source_mapping_invalid"):
        transform(forged, manifest, fragments)


@pytest.mark.parametrize("markers,marker_x", [((20,), 25), ((20, 20, 20), 25), ((20, 30, 25), 25),
                                               ((1, 2, 3), 25), ((20, 25, 30), 200)])
def test_ambiguous_numbers_and_body_columns_remain_content(tmp_path, markers, marker_x):
    fragments = extract(pdf(tmp_path, markers, marker_x), document_id="doc", source_id="source")
    assert not any(row.get("source_text_view") for row in fragments)
    assert all(str(value) in " ".join(row["raw_text"] for row in fragments) for value in markers)


def test_mixed_block_exclusion_is_reversible_and_keeps_negation_and_exception():
    raw = "Gebruik geen 5 mg bij de individuele\n825\nsituatie, tenzij de arts anders adviseert."
    start = raw.index("825")
    exclusion = {"text": "825", "raw_start": start, "raw_end": start + 3,
                 "bbox": [1, 2, 3, 4], "reason": "repeated_five_line_left_margin"}
    fragment = {"fragment_id": "f", "raw_text": raw, "clean_text": raw, "section_path": ["Advies"],
                "source_text_view": text_view(raw, [exclusion])}
    block = semantic_source_blocks([fragment])[0]
    assert block["text"] == "Gebruik geen 5 mg bij de individuele situatie, tenzij de arts anders adviseert."
    assert fragment["raw_text"] == raw
    rebuilt = reconstruct_source_fragments([fragment])[0]
    from src.source_layout_v1 import mapped_raw_spans
    mapping = mapped_raw_spans(rebuilt, start=0, end=len(block["text"]))
    assert not any(row["raw_start"] <= start < row["raw_end"] for row in mapping)
    from src.object_taxonomy_v1 import normalize_visible_prose
    assert normalize_visible_prose("".join(raw[row["raw_start"]:row["raw_end"]] for row in mapping)) == block["text"]
    bad = deepcopy(fragment)
    bad["source_text_view"]["text"] = block["text"].replace("geen ", "")
    with pytest.raises(ValueError, match="source_layout_view_invalid"):
        reconstruct_source_fragments([bad])
    offset = block["text"].index("geen")
    with pytest.raises(SemanticPassageError, match="semantic_span_hidden_gap"):
        semantic_units_from_proposal([fragment], document_id="doc", proposal={"objects": [{
            "spans": [{"block_id": block["block_id"], "start": 0, "end": offset},
                      {"block_id": block["block_id"], "start": offset + 4, "end": len(block["text"])}],
            "proposed_object_type": "recommendation", "recommendation_semantics": None}]})


def numbered_document(tmp_path, *, table=False, broken=False, body_column=False):
    path = tmp_path / "document-gutter.pdf"
    doc = fitz.open()
    for page_no in range(3):
        page = doc.new_page()
        for i in range(8):
            marker = (page_no * 8 + i + 1) * 5
            if broken and marker == 60:
                marker = 61
            y = 80 + i * 80
            value = str(marker)
            edge = 130 if body_column else 55
            x = edge - fitz.get_text_length(value, fontsize=10)
            page.insert_text((x, y), value + " ", fontsize=10)
            for step in range(1 if table else 5):
                page.insert_text((90, y + step * 16),
                    "Gebruik geen 5 mg binnen 4 uur, tenzij de arts anders adviseert.", fontsize=10)
    doc.save(path)
    doc.close()
    return path


def test_document_wide_gutter_is_removed_only_from_reading_view(tmp_path):
    fragments = extract(numbered_document(tmp_path), document_id="doc", source_id="source")
    exclusions = [ex for row in fragments for ex in row.get("source_text_view", {}).get("exclusions", [])]
    assert len(exclusions) == 24
    assert all(ex["recognition"]["page_count"] == 3 for ex in exclusions)
    assert {ex["text"].strip() for ex in exclusions} == {str(i * 5) for i in range(1, 25)}
    for row in fragments:
        for ex in row.get("source_text_view", {}).get("exclusions", []):
            assert row["raw_text"][ex["raw_start"]:ex["raw_end"]] == ex["text"]
    blocks = semantic_source_blocks(fragments)
    assert all("5 mg binnen 4 uur, tenzij" in b["text"] for b in blocks)
    # Extraction is deterministic and every original raw fragment remains available.
    assert extract(numbered_document(tmp_path), document_id="doc", source_id="source") == fragments


@pytest.mark.parametrize("options", [{"table": True}, {"broken": True}, {"body_column": True}])
def test_document_wide_ambiguous_columns_keep_numbers(tmp_path, options):
    fragments = extract(numbered_document(tmp_path, **options), document_id="doc", source_id="source")
    assert not any(row.get("source_text_view") for row in fragments)


def test_trimmed_numeric_span_preserves_geometry_and_exact_raw_bounds(tmp_path, monkeypatch):
    import src.source_layout_v1 as layout
    monkeypatch.setattr(layout, "mark_pdf_layout", lambda rows: None)
    fragments = extract(numbered_document(tmp_path), document_id="doc", source_id="source")
    numeric = [span for row in fragments for span in row["_pdf_spans"] if span["text"].strip().isdigit()]
    assert len(numeric) == 24
    for row in fragments:
        for span in row["_pdf_spans"]:
            assert row["raw_text"][span["raw_start"]:span["raw_end"]] == span["text"]
            assert 0 <= span["raw_start"] < span["raw_end"] <= len(row["raw_text"])
