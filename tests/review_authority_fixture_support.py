"""Materialised source fixtures for review projection tests.

The source registry contains explicit fixture input, never reconstructed
production evidence. Candidates go through the production materialiser.
"""
from copy import deepcopy
from hashlib import sha256

_SOURCES = {}

def materialised_row(row):
    from src.integrity_kernel import stamp_canonical_hashes
    from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
    from src.semantic_passage_v1 import semantic_source_blocks
    from src.semantic_transform_generic_v1 import _fragment_ref
    from test_t4_single_knowledge_path_invariants import _allowed_candidate

    row = deepcopy(row)
    row.setdefault("object_version", "1.0")
    if (row.get("confirmed_object_type") is None
            and row.get("governance", {}).get("validation_status") == "approved"):
        row["confirmed_object_type"] = row.get("proposed_object_type") or row.get("object_type")
    kind = row.get("proposed_object_type") or row.get("object_type")
    if kind in {"heading", "document", "node", "outcome", "path"}:
        stamp_canonical_hashes(row)
        return row
    text = str(row.get("content", {}).get("clean_text") or "")
    if not text.strip():
        stamp_canonical_hashes(row)
        return row
    digest = sha256(text.encode()).hexdigest()
    fragment = {
        "fragment_id": "fixture-" + digest, "fragment_hash": digest,
        "clean_text": text, "raw_text": text, "section_path": [],
        "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:1-1"},
    }
    _SOURCES[fragment["fragment_id"]] = fragment
    block = semantic_source_blocks([fragment])[0]
    [candidate] = materialise_knowledge_candidates(
        [{"decision_kind": "semantic_selection", "selection_origin": "proposal_selected",
          "spans": [{"block_id": block["block_id"], "start": 0, "end": len(block["text"])}],
          "source_text": text}], document_id=row.get("document_id") or "fixture",
        fragments=[fragment])
    row.setdefault("source", deepcopy(_allowed_candidate()["source"]))
    row.setdefault("metadata", {})["semantic_passage"] = candidate["semantic_passage"]
    row.setdefault("provenance", {})["source_fragments"] = [_fragment_ref(fragment)]
    stamp_canonical_hashes(row)
    return row

def source_fragments():
    return deepcopy(list(_SOURCES.values()))

def approved_bindings(objects, reviewer="reviewer-1"):
    from src.integrity_kernel import exact_review_snapshot_hash
    from src.publish_authorization_v1 import tuple_record
    return [tuple_record(object_id=o["object_id"], object_version=o["object_version"],
            canonical_object_hash=exact_review_snapshot_hash(o),
            confirmed_object_type=o.get("confirmed_object_type"),
            reviewer=reviewer, reviewer_id=reviewer, decision="approve")
            for o in objects if o.get("governance", {}).get("validation_status") == "approved"
            and o.get("confirmed_object_type") not in {"heading", "document"}]
