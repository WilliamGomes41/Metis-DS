"""Explicit source selections for lifecycle fixtures through the real creator.

These fixtures exercise Review/storage/publication, not provider inference.
They never stamp admission or bypass source resolution.
"""
import json

from src.object_taxonomy_v1 import propose_object_type
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.recommendation_semantics_v1 import source_literal_strength, source_label_direction


def bind_fixture_selections(console, selections=None):
    """Select literal paragraphs; optionally restrict to (literal, type) pairs."""
    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        objects = []
        for block in data["source_blocks"]:
            text = block["text"]
            selected = (next(((literal, type_) for literal, type_ in selections if literal in text), None)
                        if selections is not None else (text, propose_object_type(text, is_heading=False) or "unclassified"))
            if selected is None:
                continue
            literal, type_ = selected
            def ref(value, owner=block):
                return {"block_id": owner["block_id"], "literal": value, "occurrence": None}
            semantics = None
            if type_ == "recommendation":
                path = block.get("section_path") or []
                label = next((b for b in data["evidence_blocks"]
                              if b["text"] in path and source_literal_strength(b["text"])), None)
                strength = source_literal_strength(label["text"]) if label else None
                semantics = {"direction": source_label_direction(label["text"]) if label else None,
                             "direction_evidence": ref(literal),
                             "strength": strength, "strength_status": "explicit" if strength else "not_stated",
                             "strength_evidence": ref(label["text"], label) if label else None}
                semantics["direction"] = semantics["direction"] or "for"
            objects.append({"spans": [ref(literal)], "proposed_object_type": type_,
                            "recommendation_semantics": semantics})
        proposal = {"objects": objects, "relations": [], "abstain_reason": None if objects else "uncertain"}
        return {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(proposal)}]}]}
    bind_pre_review_semantic_processing(console, environ={
        "METIS_PASSAGE_FORMATION_MODE": "semantic-source-bound-v1",
        "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": "fixture",
    }, post_json=provider)
