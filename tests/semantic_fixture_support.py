"""Explicit source selections for lifecycle fixtures through the real creator.

These fixtures exercise Review/storage/publication, not provider inference.
They never stamp admission or bypass source resolution.
"""
import json

from src.object_taxonomy_v1 import propose_object_type
from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.vorming.recommendation_semantics_v1 import source_literal_strength, source_label_direction


def bind_fixture_selections(console, selections=None, relations=None):
    """Select literal paragraphs; optionally restrict to (literal, type) pairs.

    With ``relations`` [(source literal, relation type, target literal)] the
    fake model also proposes those source-bound relations and may select
    several literals within one block.
    """
    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        if payload["text"]["format"]["name"] == "decision_tree_proposal":
            return _decision_tree_response(data)
        objects = []
        chosen = []
        for block in data["source_blocks"]:
            text = block["text"]
            if selections is None:
                chosen.append((block, text, propose_object_type(text, is_heading=False) or "unclassified"))
            elif relations is None:
                first = next(((literal, type_) for literal, type_ in selections if literal in text), None)
                if first is not None:
                    chosen.append((block, *first))
            else:
                chosen.extend(sorted(((block, literal, type_) for literal, type_ in selections if literal in text),
                                     key=lambda row: text.index(row[1])))
        for block, literal, type_ in chosen:
            text = block["text"]
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
        proposal = {"objects": objects, "relations": [_relation(data, *row) for row in relations or []],
                    "abstain_reason": None if objects else "uncertain"}
        return {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(proposal)}]}]}
    # Fixture consoles may be re-bound with narrower selections after creation.
    console._pre_review_semantic_bound = False
    bind_pre_review_semantic_processing(console, environ={
        "METIS_PASSAGE_FORMATION_MODE": "semantic-source-bound-v1",
        "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": "fixture",
    }, post_json=provider)
    console._metis_fixture_binding = True


def rebinding(bind):
    """Test harness: an explicit later binding replaces the fixture model, never itself."""
    def rebind(console, *args, **kwargs):
        if getattr(console, "_metis_fixture_binding", False):
            console._pre_review_semantic_bound = False
            console._metis_fixture_binding = False
        return bind(console, *args, **kwargs)
    rebind.__wrapped__ = bind
    return rebind


def _relation(data, source, relation_type, target):
    def span(literal):
        block = next(b for b in data["source_blocks"] if literal in b["text"])
        start = block["text"].index(literal)
        return {"block_id": block["block_id"], "start": start, "end": start + len(literal)}
    return {"source_spans": [span(source)], "relation_type": relation_type,
            "target_spans": [span(target)], "evidence_spans": [span(target)]}


def _decision_tree_response(data):
    """One unit per source block, open roles, no connections: the reviewer builds the graph.

    A structured export is answered as a faithful model would: its items and
    explicit branches and bundles, read only from the request payload.
    """
    from src.vorming.decision_tree_proposal_v1 import CONTRACT
    if any((item.get("record") or {}).get("export_id") for item in data["evidence_items"].values()):
        proposal = export_tree_proposal(data)
        return {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(proposal)}]}]}
    units = [{"ref": f"u{i + 1}", "role": "action", "selection": None, "entry": False,
              "quoted_text": block["text"], "spans": [{"block_id": block["block_id"], "start": 0,
                                                       "end": len(block["text"])}]}
             for i, block in enumerate(data["source_blocks"])]
    proposal = {"contract": CONTRACT, "units": units, "connections": [], "context_bindings": [],
                "result_bundles": [], "unresolved": [{"ref": f"r{i + 1}", "subject": u["ref"],
                                                      "code": "role_ambiguous"} for i, u in enumerate(units)]}
    return {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(proposal)}]}]}


def export_tree_proposal(data, *, roles=None):
    """Units, connections and bundles exactly as the export states them."""
    from src.vorming.decision_tree_proposal_v1 import CONTRACT
    items = data["evidence_items"]
    block_of = {fid: block for block in data["source_blocks"] for fid in block["source_fragment_ids"]}
    units, ref_of, containers = [], {}, {}
    for key, item in items.items():
        record = item.get("record") or {}
        text = " ".join(str(item.get("text") or "").split())
        if item["kind"] != "text" or not record.get("export_id") or not text:
            continue
        block = block_of[key]
        start = block["text"].index(text)
        ref = f"u{len(units) + 1}"
        role = ("context" if record.get("bundle_role") == "member" else "outcome"
                if record.get("export_kind") == "outcome" else "start"
                if record.get("export_kind") == "path" else "action")
        units.append({"ref": ref, "role": (roles or {}).get(record["export_id"], role),
                      "selection": None, "entry": False, "quoted_text": text,
                      "spans": [{"block_id": block["block_id"], "start": start, "end": start + len(text)}]})
        ref_of[record["export_id"]] = ref
        if record.get("bundle_role") == "container":
            containers[record["bundle_id"]] = (ref, [])
    for item in items.values():
        record = item.get("record") or {}
        if record.get("bundle_role") == "member" and record.get("export_id") in ref_of:
            containers[record["bundle_id"]][1].append(ref_of[record["export_id"]])
    connections = [{"ref": f"c{len(units) + index}", "from": ref_of[item["record"]["from"]],
                    "to": ref_of[item["record"]["to"]],
                    "kind": "answer" if item["record"].get("label") else "continue",
                    "label_span": None, "evidence_ids": [key]}
                   for index, (key, item) in enumerate(items.items())
                   if item["kind"] == "export_edge" and item["record"]["from"] in ref_of
                   and item["record"]["to"] in ref_of]
    bundles = [{"ref": f"b{index + 1}", "container": container, "members": members}
               for index, (container, members) in enumerate(containers.values())]
    # The export states kinds and branches, not answer semantics: roles stay open.
    unresolved = [{"ref": f"r{index + 1}", "subject": unit["ref"], "code": "role_ambiguous"}
                  for index, unit in enumerate(u for u in units if u["role"] != "context")]
    return {"contract": CONTRACT, "units": units, "connections": connections, "context_bindings": [],
            "result_bundles": bundles, "unresolved": unresolved}


def legacy_recommendation_fixture(console, snapshot_id):
    """Represent a persisted pre-D3 candidate without rewriting review evidence."""
    from src.integrity_kernel import stamp_canonical_hashes
    rows = console._load_objects(snapshot_id)
    current = {(row["object_id"], row["object_version"]) for row in console.snapshot_objects(snapshot_id)}
    changed = False
    for row in rows:
        if (row["object_id"], row["object_version"]) not in current:
            continue
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
    from src.vorming.semantic_passage_v1 import semantic_source_blocks, semantic_units_from_proposal
    from src.vorming.knowledge_materialisation_v1 import materialise_knowledge_candidates
    from src.vorming.semantic_transform_generic_v1 import transform
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
    """Seed synthetic isolated history, never invoke a production mutation.

    Legacy/corruption fixtures deliberately model already persisted states.
    T11 storage commands must reject such in-place rewrites, so test setup writes
    the isolated fixture file directly and then refreshes its concurrency token.
    """
    store = getattr(console, "workflow_document_store", None)
    if store is not None:
        with store._connect() as connection:
            connection.execute("DELETE FROM workflow.document_objects WHERE snapshot_id=%s", (snapshot_id,))
            for position, row in enumerate(rows):
                connection.execute(
                    "INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload,position) "
                    "VALUES(%s,%s,%s,%s::jsonb,%s)",
                    (snapshot_id, row["object_id"], row["object_version"], json.dumps(row), position))
        console.refresh_workflow_documents()
        return
    path = (console.runtime / "objects" / f"{snapshot_id}.jsonl")
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    console.refresh_objects_expected_revision(snapshot_id)
