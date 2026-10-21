"""Synthetic multi-page PDF proof through provider validation and transform.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json

import fitz
import pytest

from src.extract_pdf_v2 import extract, fragment_payload
from src.integrity_kernel import stable_hash
from src.semantic_passage_v1 import SemanticPassageError, semantic_source_blocks, semantic_units_from_proposal
from src.pre_review_semantic_v1 import semantic_spec_from_fragments
from src.semantic_transform_generic_v1 import transform
from src.source_bound_fields_v2 import FIELDS


def test_nineteen_synthetic_recommendations_keep_exact_evidence(tmp_path):
    path = tmp_path / "synthetic.pdf"
    pdf = fitz.open()
    for page_no in range(3):
        page = pdf.new_page()
        for i in range(8):
            number = page_no * 8 + i + 1
            marker = str(number * 5)
            y = 80 + i * 80
            page.insert_text((55 - fitz.get_text_length(marker, fontsize=10), y), marker + " ", fontsize=10)
            texts = [f"Gebruik maatregel {number} volgens de instructie.", "Sterk - voor",
                     "Controleer het resultaat.", "Bespreek de uitkomst.", "Leg de bevinding vast."]
            for step, text in enumerate(texts):
                page.insert_text((90, y + step * 16), text, fontsize=10)
    pdf.save(path)
    pdf.close()
    fragments = extract(path, document_id="synthetic", source_id="synthetic-source")
    assert sum(len(f.get("source_text_view", {}).get("exclusions", [])) for f in fragments) == 24
    assert all(f["fragment_hash"] == stable_hash(fragment_payload(f)) for f in fragments)
    raw_texts = [f["raw_text"] for f in fragments]
    responses = []

    def provider(_url, _headers, payload, _timeout):
        inputs = json.loads(payload["input"][1]["content"])
        objects = []
        def ref(block, literal):
            return {"block_id": block["block_id"], "literal": literal, "occurrence": None}
        for number in range(1, 20):
            literal = f"Gebruik maatregel {number} volgens de instructie."
            block = next(b for b in inputs["source_blocks"] if literal in b["text"])
            evidence_index = next(i for i, b in enumerate(inputs["evidence_blocks"])
                                  if b["block_id"] == block["block_id"])
            label = inputs["evidence_blocks"][evidence_index + 1]
            assert label["text"] == "Sterk - voor"
            fields = {field: {"span": None, "missing_reason": "not_stated"} for field in FIELDS}
            for field in ("predicate_span", "recommended_action", "type_evidence_spans", "recommendation_evidence_span"):
                fields[field] = {"span": ref(block, literal), "missing_reason": None}
            objects.append({"spans": [ref(block, literal)], "proposed_object_type": "recommendation",
                "recommendation_semantics": {"direction": "for", "strength": "strong", "strength_status": "explicit",
                    "direction_evidence": ref(block, literal), "strength_evidence": ref(label, "Sterk - voor")},
                "field_evidence": fields, "context_evidence": []})
        proposal = {"objects": objects, "relations": [], "abstain_reason": None}
        responses.append(proposal)
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(proposal)}]}]}

    spec = semantic_spec_from_fragments(document_id="synthetic", title="Synthetic test",
        family="test", class_="richtlijn", fragments=fragments, content_kind="pdf", api_key="test",
        model="test", post_json=provider, field_contract_v2=True)
    assert len(responses[0]["objects"]) == 19
    selected = [o for o in spec["objects"] if o.get("semantic_passage", {}).get("selection_origin") == "proposal_selected"]
    assert len(selected) == 19
    manifest = {"canonical_source": {"source_id": "synthetic-source", "title": "Synthetic test",
        "source_type": "pdf", "source_url": "test", "source_level": "national", "canonicality": "canonical",
        "integrity_status": "verified", "source_checksum": "a" * 64}}
    assert len(transform(spec, manifest, fragments)) == len(spec["objects"])
    assert [f["raw_text"] for f in fragments] == raw_texts
    block = next(b for b in semantic_source_blocks(fragments) if "Gebruik maatregel 1 " in b["text"])
    start = block["text"].index("maatregel")
    with pytest.raises(SemanticPassageError, match="semantic_span_hidden_gap"):
        semantic_units_from_proposal(fragments, document_id="synthetic", proposal={"objects": [{
            "proposed_object_type": "recommendation", "recommendation_semantics": None,
            "spans": [{"block_id": block["block_id"], "start": 0, "end": start},
                      {"block_id": block["block_id"], "start": start + len("maatregel"), "end": len(block["text"])}]}]})
