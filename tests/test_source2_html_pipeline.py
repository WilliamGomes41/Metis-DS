from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.extract_html_v1 import extract, validate as validate_raw
from src.semantic_transform_generic_v1 import transform, validate as validate_objects
from src.prepublication_gate_v3 import evaluate as prepublish

ROOT = Path(__file__).resolve().parents[1]


def test_html_extractor_emits_source_neutral_locators(tmp_path: Path):
    html = tmp_path / "source.html"
    html.write_text("""<!doctype html><html><body>
<h1>Richtlijn test</h1>
<h2>Aanbevelingen</h2>
<p>Adviseer passende zorg.</p>
<ul><li>Controleer een relevante grenswaarde.</li></ul>
<script>ignore me</script>
</body></html>""", encoding="utf-8")
    rows = extract(html, document_id="doc-test", source_id="source-test")
    assert len(rows) == 4
    assert rows[2]["section_path"] == ["Richtlijn test", "Aanbevelingen"]
    assert rows[2]["source_page"] is None
    assert rows[2]["bbox"] is None
    assert rows[2]["source_locator"]["locator_type"] == "web_line_range"
    assert "lines:" in rows[2]["source_locator"]["locator_value"]
    assert not validate_raw(rows, ROOT / "schemas/raw_fragment.schema.v1.1.json")


def test_generic_transform_validates_v12_and_keeps_html_locator(tmp_path: Path):
    html = tmp_path / "source.html"
    html.write_text("<h1>Test</h1>\n<h2>Aanbeveling</h2>\n<p>Gebruik de afgesproken interventie.</p>", encoding="utf-8")
    raw = extract(html, document_id="doc-test", source_id="source-test")
    recommendation_fragment = raw[-1]["fragment_id"]
    manifest = {
        "canonical_source": {
            "source_id": "source-test",
            "title": "Test source",
            "publisher": "V&VN",
            "source_url": "https://example.org/test",
            "source_type": "html",
            "source_level": 1,
            "canonicality": "canonical",
            "source_checksum": None,
            "checksum_algorithm": "sha256",
            "integrity_status": "binary_unavailable",
            "publication_date": "2025-04-01",
            "version": "1.0"
        }
    }
    spec = {
        "spec_version": "1.0",
        "document_id": "doc-test",
        "object_version": "1.0",
        "target_group": ["verpleegkundige"],
        "care_setting": ["wijkzorg"],
        "topic": ["test"],
        "objects": [
            {
                "object_id": "doc-test-document",
                "object_type": "document",
                "text": "Test source",
                "review_track": "technical"
            },
            {
                "object_id": "doc-test-rec-01",
                "object_type": "recommendation",
                "text": "Gebruik de afgesproken interventie.",
                "source_fragment_ids": [recommendation_fragment],
                "section_path": ["Test", "Aanbeveling"]
            }
        ]
    }
    rows = transform(spec, manifest, raw)
    assert len(rows) == 2
    assert not validate_objects(rows, ROOT / "schemas/knowledge_object.schema.v1.2.json")
    ref = rows[1]["provenance"]["source_fragments"][0]
    assert ref["source_locator"]["locator_type"] == "web_line_range"
    assert ref["coordinate_status"] == "not_applicable"
    assert rows[1]["source"]["integrity_status"] == "binary_unavailable"


def test_source2_manifest_is_fail_closed_until_binary_available():
    manifest = json.loads((ROOT / "data/source_manifest.continentie.v1.json").read_text(encoding="utf-8"))
    source = manifest["canonical_source"]
    assert source["source_type"] == "html"
    assert source["source_checksum"] is None
    assert source["integrity_status"] == "binary_unavailable"
    assert manifest["scope"]["publication_allowed"] is False


def test_v12_schema_does_not_mutate_v11_contract():
    v11 = json.loads((ROOT / "schemas/knowledge_object.schema.v1.1.json").read_text(encoding="utf-8"))
    v12 = json.loads((ROOT / "schemas/knowledge_object.schema.v1.2.json").read_text(encoding="utf-8"))
    assert v11["$id"].endswith("v1.1.json")
    assert v12["$id"].endswith("v1.2.json")
    old_frag = v11["properties"]["provenance"]["properties"]["source_fragments"]["items"]
    new_frag = v12["properties"]["provenance"]["properties"]["source_fragments"]["items"]
    assert "source_locator" not in old_frag["properties"]
    assert "source_locator" in new_frag["properties"]


def test_integrity_kernel_accepts_v11_locator_hash(tmp_path: Path):
    from src.integrity_kernel import load_raw_objects, validate_source_fragments
    html = tmp_path / "source.html"
    html.write_text("<h1>Test</h1><p>Een fragment.</p>", encoding="utf-8")
    raw = extract(html, document_id="doc-test", source_id="source-test")
    raw_path = tmp_path / "raw.jsonl"
    raw_path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True)+"\n" for r in raw), encoding="utf-8")
    target = raw[-1]
    obj = {
        "object_type": "recommendation",
        "provenance": {
            "source_fragments": [{
                "raw_object_id": target["fragment_id"],
                "page": None,
                "raw_content_hash": target["fragment_hash"],
                "bbox": None,
                "coordinate_status": "not_applicable",
                "source_locator": target["source_locator"],
            }]
        }
    }
    assert validate_source_fragments(obj, load_raw_objects(raw_path)) == []
