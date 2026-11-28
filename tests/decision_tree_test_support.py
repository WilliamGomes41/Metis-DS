"""Test double for the decision-tree model proposer.

It proposes one unit per source fragment with open roles and no connections,
so tests exercise the real contract, materialiser, constructor and review
graph without a provider. For a structured export it answers like a faithful
model, from the same request input a model receives. Production has no such
default: an unbound proposer fails closed.
"""
from __future__ import annotations

from src.vorming.decision_tree_construction_v1 import proposal_inputs
from src.vorming.decision_tree_proposal_v1 import CONTRACT


def historical_proposal_input(frozen):
    evidence_items = {key: {k: v for k, v in item.items() if k in {"kind", "text", "page", "bbox", "record"}}
                      for key, item in frozen["inventory"]["items"].items()}
    if frozen.get("kind") == "boom":
        # Request-only view: which exported item each text item is, so export_edge
        # records can be read. The recorded inventory itself is unchanged.
        for fragment in frozen["fragments"]:
            item = evidence_items.get(fragment["fragment_id"])
            if item is not None and item["kind"] == "text":
                item["record"] = {"export_id": fragment.get("boom_id"), "export_kind": fragment.get("boom_kind"),
                                  "bundle_id": fragment.get("bundle_id"), "bundle_role": fragment.get("bundle_role")}
    return {"source_blocks": proposal_inputs(frozen["fragments"]), "evidence_items": evidence_items}


def fragment_proposal(frozen):
    if frozen.get("kind") == "boom":
        from tests.semantic_fixture_support import export_tree_proposal
        return export_tree_proposal(historical_proposal_input(frozen)), "test-proposer"
    blocks = proposal_inputs(frozen["fragments"])
    units = []
    for fragment in frozen["fragments"]:
        text = " ".join(str(fragment.get("clean_text") or "").split())
        block = next((b for b in blocks if fragment["fragment_id"] in b["source_fragment_ids"]), None)
        if not text or block is None or block["text"].count(text) != 1:
            continue
        start = block["text"].index(text)
        units.append({"ref": f"u{len(units) + 1}", "role": "action", "selection": None, "entry": False,
                      "quoted_text": text,
                      "spans": [{"block_id": block["block_id"], "start": start, "end": start + len(text)}]})
    proposal = {"contract": CONTRACT, "units": units, "connections": [], "context_bindings": [],
                "result_bundles": [],
                "unresolved": [{"ref": f"r{i + 1}", "subject": u["ref"], "code": "role_ambiguous"}
                               for i, u in enumerate(units)]}
    return proposal, "test-proposer"


def install_fragment_proposer(console):
    """Install the only source strategy with this test proposer for decision trees."""
    from tests.semantic_fixture_support import bind_fixture_selections
    bind_fixture_selections(console)
    console._decision_tree_proposer = fragment_proposal
    return console


def pdf_data(question_lines=None, *, columns=False, ambiguous=False):
    """A small boxed decision page: question, Ja/Nee labels, two actions, one line."""
    import fitz
    with fitz.open() as doc:
        page = doc.new_page()
        page.draw_rect(fitz.Rect(60, 45, 235, 150))
        lines = question_lines or ["Is er sprake van een", "mantelzorger?"]
        for i, text in enumerate(lines):
            page.insert_text((75, 70 + i * 18), text, fontsize=11)
        if columns:
            page.draw_rect(fitz.Rect(280, 45, 470, 150))
            page.insert_text((295, 70), "Is er sprake van een", fontsize=11)
            page.insert_text((295, 88), "probleem?", fontsize=11)
        if ambiguous:
            page.insert_text((77, 88), "probleem?", fontsize=11)
        page.insert_text((75, 185), "Ja", fontsize=11)
        page.insert_text((180, 185), "Nee", fontsize=11)
        page.insert_text((75, 260), "Bespreek de situatie.", fontsize=11)
        page.insert_text((280, 260), "Maak een afspraak.", fontsize=11)
        page.draw_line((100, 150), (100, 240))
        return doc.tobytes()
