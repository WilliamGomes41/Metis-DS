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


def legacy_recommendation_fixture(console, snapshot_id):
    """Represent a persisted pre-D3 candidate without rewriting review evidence."""
    from src.integrity_kernel import stamp_canonical_hashes
    rows = console._load_objects(snapshot_id)
    changed = False
    for row in rows:
        if (row.get("metadata") or {}).get("semantic_passage", {}).get("selection_origin") != "proposal_selected":
            continue
        if "proposed_recommendation_semantics" not in row:
            continue
        changed = True
        row.pop("proposed_recommendation_semantics", None)
        row.get("metadata", {}).pop("recommendation_semantics_evidence", None)
        stamp_canonical_hashes(row)
    if changed:
        install_fixture_history(console, snapshot_id, rows)


def materialised_fixture(text, *, proposed_type="recommendation", document_id="doc-fixture"):
    """Build one source-valid canonical fixture through selection and its creator."""
    from hashlib import sha256
    from src.semantic_passage_v1 import semantic_source_blocks, semantic_units_from_proposal
    from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
    from src.semantic_transform_generic_v1 import transform
    from src.integrity_kernel import stable_hash
    digest = sha256(text.encode()).hexdigest()
    fragments = [{"fragment_id": "fixture-source", "fragment_hash": digest,
                  "raw_text": text, "clean_text": text, "section_path": ["Behandeling"],
                  "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:1-1"}}]
    block = semantic_source_blocks(fragments)[0]
    proposal = {"objects": [{"spans": [{"block_id": block["block_id"], "start": 0, "end": len(text)}],
                             "proposed_object_type": proposed_type}], "relations": [], "abstain_reason": None}
    decisions = semantic_units_from_proposal(fragments, document_id=document_id, proposal=proposal)
    candidates = materialise_knowledge_candidates(decisions, document_id=document_id, fragments=fragments)
    for candidate in candidates:
        candidate["semantic_passage"].update(formation_mode="semantic-source-bound-v1", model="fixture",
            source_blocks_hash=stable_hash([block]), proposal_hash=stable_hash(proposal))
    spec = {"spec_version": "console-ingest-1.0", "document_id": document_id,
            "object_version": "1.0", "target_group": [], "care_setting": [], "topic": [], "objects": candidates}
    manifest = {"canonical_source": {"source_id": "fixture", "title": "Fixture", "source_type": "html",
                "source_url": "https://example.test/fixture", "source_level": 1, "canonicality": "canonical",
                "integrity_status": "verified", "source_checksum": digest, "version": "1.0"}}
    return transform(spec, manifest, fragments), fragments


def install_fixture_history(console, snapshot_id, rows):
    """Seed synthetic file-backed history, never invoke a production mutation.

    Legacy/corruption fixtures deliberately model already persisted states.
    T11 storage commands must reject such in-place rewrites, so test setup writes
    the isolated fixture file directly and then refreshes its concurrency token.
    """
    assert getattr(console, "workflow_document_store", None) is None
    path = console._objects_path(snapshot_id)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    console.refresh_objects_expected_revision(snapshot_id)
