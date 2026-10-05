"""Clinical-column retention and explicit reconstruction-boundary evidence.

# release-control-evidence: scope/belofte kwaliteit slop releasebewijs
"""
from copy import deepcopy
import csv
import io
import json
from zipfile import ZipFile

import fitz
import pytest

from src.extract_pdf_v2 import extract
from src.source_reconstruction_v1 import reconstruct_source_fragments
from src.source_layout_v1 import mapped_raw_spans
from src.object_taxonomy_v1 import normalize_visible_prose


def test_five_line_dose_column_is_not_removed(tmp_path):
    path = tmp_path / "doses.pdf"
    doc = fitz.open()
    page = doc.new_page()
    for i, dose in enumerate((20, 25, 30)):
        y = 100 + i * 80
        page.insert_text((25, y), str(dose), fontsize=10)
        page.insert_text((90, y), "mg als dosis voor deze groep.", fontsize=10)
        for j in range(1, 5):
            page.insert_text((90, y + j * 16), "Gebruik geen andere dosis, tenzij de arts dit adviseert.", fontsize=10)
    doc.save(path)
    doc.close()
    fragments = extract(path, document_id="doc", source_id="source")
    assert not any(row.get("source_text_view", {}).get("exclusions") for row in fragments)
    assert any(row.get("source_layout_findings") for row in fragments)
    from src.semantic_passage_v1 import semantic_source_blocks
    blocks = semantic_source_blocks(fragments)
    for dose in (20, 25, 30):
        assert str(dose) in " ".join(row["text"] for row in blocks)
    assert "geen andere dosis" in " ".join(row["text"] for row in blocks)


def fragments():
    return [dict(fragment_id=str(i), raw_text=text, clean_text=text,
                 source_page=1, section_path=["Advies"], fragment_hash="a" * 64, source_locator={"locator_type": "page", "locator_value": "1"}, bbox=[10, 10, 100, 20])
            for i, text in enumerate(("De eerste helft", "gaat hier verder", "en eindigt hier."))]


def rebuild(mapping, source):
    by_id = {row["fragment_id"]: row for row in source}
    return normalize_visible_prose("".join(
        row["text"] if row.get("kind") == "join_separator" else
        by_id[row["fragment_id"]]["raw_text"][row["raw_start"]:row["raw_end"]]
        for row in mapping))


@pytest.mark.parametrize("count", [2, 3])
def test_join_mapping_reconstructs_inserted_spaces(count):
    source = fragments()[:count]
    joined = reconstruct_source_fragments(source)[0]
    mapping = mapped_raw_spans(joined, start=0, end=len(joined["clean_text"]))
    assert rebuild(mapping, source) == joined["clean_text"]
    separators = [row for row in mapping if row.get("kind") == "join_separator"]
    assert len(separators) == count - 1
    assert all(row["text"] == " " for row in separators)
    assert separators[0]["left_fragment_id"] == "0"
    assert separators[0]["right_fragment_id"] == "1"


def test_selection_can_include_only_join_boundary_or_exclude_it():
    source = fragments()[:2]
    joined = reconstruct_source_fragments(source)[0]
    boundary = len(source[0]["clean_text"])
    assert mapped_raw_spans(joined, start=boundary, end=boundary + 1) == [
        {"kind": "join_separator", "text": " ", "left_fragment_id": "0", "right_fragment_id": "1"}]
    mapping = mapped_raw_spans(joined, start=boundary + 1, end=len(joined["clean_text"]))
    assert not any(row.get("kind") == "join_separator" for row in mapping)
    assert rebuild(mapping, source) == source[1]["clean_text"]


def test_join_boundary_is_validated_and_exported():
    from src.pre_review_semantic_v1 import semantic_spec_from_fragments
    from src.semantic_transform_generic_v1 import transform
    from src.processing_evidence_export_v1 import processing_evidence_tables, processing_evidence_zip
    source = fragments()
    def provider(_url, _headers, payload, _timeout):
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        proposal = {"objects": [{"spans": [{"block_id": block["block_id"], "start": 0, "end": len(block["text"])}],
                                 "proposed_object_type": "recommendation", "recommendation_semantics": None}],
                    "abstain_reason": None}
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(proposal)}]}]}
    spec = semantic_spec_from_fragments(document_id="doc", title="Fixture", family="test", class_="richtlijn",
        fragments=source, content_kind="pdf", api_key="test", model="test", post_json=provider)
    manifest = {"canonical_source": {"source_id": "source", "title": "Fixture", "source_type": "pdf",
        "source_url": "test", "source_level": "national", "canonicality": "canonical",
        "integrity_status": "verified", "source_checksum": "a" * 64}}
    # A serialized spec must retain its advertised schema across readers.
    spec = json.loads(json.dumps(spec))
    rows = transform(spec, manifest, source)
    assert all(row["provenance"]["transform_version"] == "semantic-generic-v1.1.0"
               for row in rows if row.get("metadata", {}).get("semantic_passage"))
    passages = [row["metadata"]["semantic_passage"] for row in rows
                if row.get("metadata", {}).get("semantic_passage")]
    assert passages and all(row["version"] == "semantic-passage-v1.1.0" for row in passages)
    legacy = deepcopy(spec)
    for item in legacy["objects"]:
        passage = item.get("semantic_passage")
        if passage:
            passage["version"] = "semantic-passage-v1.0.0"
            passage["source_mapping"] = [row for row in passage["source_mapping"]
                                         if row.get("kind") != "join_separator"]
    legacy_rows = transform(json.loads(json.dumps(legacy)), manifest, source)
    assert all(row["provenance"]["transform_version"] == "semantic-generic-v1.0.0" for row in legacy_rows)
    assert all(row["metadata"]["semantic_passage"]["version"] == "semantic-passage-v1.0.0"
               for row in legacy_rows if row.get("metadata", {}).get("semantic_passage"))
    for invalid_version in ("semantic-passage-v1.0.0", "semantic-passage-v99"):
        invalid = deepcopy(spec)
        for item in invalid["objects"]:
            if item.get("semantic_passage"):
                item["semantic_passage"]["version"] = invalid_version
        with pytest.raises(ValueError, match="semantic_(source_mapping|passage_metadata)_invalid"):
            transform(invalid, manifest, source)
    tables, projected_manifest = processing_evidence_tables(snapshot_id="snap", revision="r", envelope={}, objects=rows)
    assert all(row["schema_version"] == "processing-evidence-export-v11" for row in projected_manifest)
    boundaries = [row for row in tables["lineage"] if row["relation"] == "inserted_join_separator"]
    assert len(boundaries) == 2
    assert all(row["text"] == " " for row in boundaries)
    # Inspect the user's downloadable artifact, not only the in-memory table.
    with ZipFile(io.BytesIO(processing_evidence_zip(
            snapshot_id="snap", revision="r", envelope={}, objects=rows))) as archive:
        manifest_rows = list(csv.DictReader(io.StringIO(archive.read("manifest.csv").decode("utf-8-sig"))))
        assert all(row["schema_version"] == "processing-evidence-export-v11" for row in manifest_rows)
        assert "CSV v4 adds text, left_fragment_id and right_fragment_id" in archive.read("README.txt").decode()
        exported = list(csv.DictReader(io.StringIO(archive.read("lineage.csv").decode("utf-8-sig"))))
        exported_boundaries = [row for row in exported if row["relation"] == "inserted_join_separator"]
        assert [(row["text"], row["left_fragment_id"], row["right_fragment_id"])
                for row in exported_boundaries] == [(" ", "0", "1"), (" ", "1", "2")]
        original_ranges = [row for row in exported if row["relation"] == "selected_raw_fragment_range"]
        assert all(row["target_id"] and row["start"] and row["end"] for row in original_ranges)
    unmapped = deepcopy(spec)
    for item in unmapped["objects"]:
        if item.get("semantic_passage"):
            del item["semantic_passage"]["source_mapping"]
    with pytest.raises(ValueError, match="semantic_source_mapping_invalid"):
        transform(unmapped, manifest, source)
    for change in ("text", "missing", "source", "extra"):
        forged = deepcopy(spec)
        target = next(row for row in forged["objects"] if row.get("semantic_passage", {}).get("source_mapping"))
        mapping = target["semantic_passage"]["source_mapping"]
        boundary = next(row for row in mapping if row.get("kind") == "join_separator")
        if change == "text": boundary["text"] = " geen "
        elif change == "missing": mapping.remove(boundary)
        elif change == "source": boundary["left_fragment_id"] = "unknown"
        else: boundary["raw_start"] = 0
        with pytest.raises(ValueError, match="semantic_source_mapping_invalid"):
            transform(forged, manifest, source)


@pytest.mark.parametrize("field_contract_v2", [False, True])
def test_replay_identity_binds_mapping_version(monkeypatch, field_contract_v2):
    from src import pre_review_semantic_v1 as semantic
    args = dict(document_id="doc", model="test", blocks=[], evidence_blocks=[],
                source_fragments=fragments(), formation_context={
                    "snapshot_id": "snap", "source_sha256": "a" * 64},
                field_contract_v2=field_contract_v2)
    current = semantic._replay_identity(**args)
    monkeypatch.setattr(semantic, "SEMANTIC_PASSAGE_VERSION", "semantic-passage-v1.0.0")
    legacy = semantic._replay_identity(**args)
    assert current != legacy
