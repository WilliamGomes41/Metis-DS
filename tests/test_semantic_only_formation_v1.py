"""Protocol 4.3.0: semantic formation is the only route; deterministic checks stay the guarantee.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from src.decision_tree_route_v1 import EXPORT_PROMPT, PROPOSER_PROMPT, prepare, request_input
from src.knowledge_materialisation_v1 import (
    MaterialisationError,
    materialise_knowledge_candidates,
    selection_source_blocks,
)
from src.operations_console_v1 import ConsoleError
from tests.semantic_fixture_support import export_tree_proposal

ROOT = Path(__file__).resolve().parents[1]

EXPORT = {
    "kind": "beslisboom-freeze",
    "paths": [{"id": "path-screening", "text": "Screening op valrisico"}],
    "nodes": [{"id": "node-vraag", "text": "Is er een verhoogd valrisico?", "scorelist": False},
              {"id": "node-score", "text": "Score 2: evenwicht", "scorelist": True}],
    "outcomes": [{"id": "out-verwijs", "text": "Verwijs naar de valpoli."},
                 {"id": "out-plan", "text": "Plan:\n- Neem contact op.\n- Maak een afspraak."}],
    "branches": [{"from": "path-screening", "to": "node-vraag"},
                 {"from": "node-vraag", "to": "out-verwijs", "label": "Ja"},
                 {"from": "node-vraag", "to": "out-plan", "label": "Nee"},
                 {"from": "node-vraag", "to": "missing-node", "label": "Misschien"}],
}


def _data(payload=EXPORT) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def _prepare(proposer, data=None, kind="boom"):
    return prepare(kind, Path("tree.json"), data=data or _data(), document_id="doc", source_id="src",
                   title="Valrisico", family="valrisico", class_="beslisboom", formation_context=None,
                   proposer=proposer)


def _faithful(mutate=None):
    def proposer(frozen):
        proposal = export_tree_proposal(request_input(frozen)[1])
        if mutate:
            mutate(proposal)
        return proposal, "test-model"
    return proposer


def _graph(spec):
    construction = spec["_decision_tree_formation"]["construction"]
    texts = {o["object_id"]: o["clean_text"] for o in spec["objects"][1:]}
    edges = sorted((texts[e["from"]], texts[e["to"]], e["kind"], e["label"]) for e in construction["graph_plan"]["edges"])
    bundles = [(texts[b["container"]], sorted(texts[m] for m in b["members"])) for b in construction["result_bundles"]]
    return texts, edges, bundles, construction


def test_faithful_export_proposal_keeps_every_explicit_item_route_label_and_bundle() -> None:
    fragments, spec = _prepare(_faithful())
    texts, edges, bundles, construction = _graph(spec)
    assert sorted(texts.values()) == sorted(
        " ".join(f["clean_text"].split()) for f in fragments if f["clean_text"].strip())
    assert edges == sorted([
        ("Screening op valrisico", "Is er een verhoogd valrisico?", "continue", ""),
        ("Is er een verhoogd valrisico?", "Verwijs naar de valpoli.", "answer", "Ja"),
        ("Is er een verhoogd valrisico?", "Plan: - Neem contact op. - Maak een afspraak.", "answer", "Nee"),
    ])
    assert [(container, len(members)) for container, members in bundles] == [("Plan: - Neem contact op. - Maak een afspraak.", 2)]
    # The malformed export branch stays visible; it is never silently dropped or repaired.
    assert "invalid_export_branch:3" in construction["graph_plan"]["unresolved"]
    # Every candidate is materialised; the export's item kind stays literal type evidence.
    assert all(o["object_id"].startswith("doc-sem-") and o["semantic_passage"]["model"] == "test-model"
               for o in spec["objects"][1:])
    assert {o["clean_text"]: o.get("proposed_object_type") for o in spec["objects"][1:]}["Score 2: evenwicht"] == "node"
    assert spec["_decision_tree_formation"]["formation"]["model"] == "test-model"


def _drop_connection(p):
    p["connections"].pop()


def _add_connection(p):
    first, last = p["units"][0]["ref"], p["units"][-1]["ref"]
    p["connections"].append({"ref": "cx", "from": first, "to": last, "kind": "continue", "label_span": None,
                             "evidence_ids": [p["connections"][0]["evidence_ids"][0]]})


def _redirect_connection(p):
    row = next(c for c in p["connections"] if c["kind"] == "answer")
    row["to"] = p["units"][0]["ref"]


def _relabel_connection(p):
    next(c for c in p["connections"] if c["kind"] == "answer")["kind"] = "continue"


def _doubt_connection(p):
    p["unresolved"].append({"ref": "rx", "subject": p["connections"][0]["ref"], "code": "role_ambiguous"})


def _partial_unit(p):
    unit = next(u for u in p["units"] if u["quoted_text"] == "Verwijs naar de valpoli.")
    unit["spans"][0]["end"] -= len(" valpoli.")
    unit["quoted_text"] = "Verwijs naar de"


def _drop_bundle(p):
    p["result_bundles"].clear()


def _uncited_connection(p):
    first, second = p["units"][0]["ref"], p["units"][2]["ref"]
    p["connections"].append({"ref": "cy", "from": first, "to": second, "kind": "continue", "label_span": None,
                             "evidence_ids": []})


def _routed_entrypoint(p):
    next(u for u in p["units"] if u["quoted_text"] == "Is er een verhoogd valrisico?")["entry"] = True


@pytest.mark.parametrize("mutate, code", [
    (_drop_connection, "decision_export_route_not_preserved"),
    (_routed_entrypoint, "decision_export_route_not_preserved"),
    (_add_connection, "decision_export_route_not_preserved"),
    (_redirect_connection, "decision_export_route_not_preserved"),
    (_relabel_connection, "decision_export_route_not_preserved"),
    (_doubt_connection, "decision_export_route_not_preserved"),
    (_uncited_connection, "decision_export_route_not_preserved"),
    (_partial_unit, "decision_export_node_not_preserved"),
    (_drop_bundle, "decision_export_bundle_not_preserved"),
])
def test_export_proposal_that_changes_the_explicit_graph_fails_closed(mutate, code) -> None:
    with pytest.raises(ConsoleError) as error:
        _prepare(_faithful(mutate))
    assert error.value.code == "pre_review_llm_proposal_rejected"
    assert str(error.value) == code


def test_export_root_may_be_proposed_as_entrypoint() -> None:
    def root_entry(p):
        next(u for u in p["units"] if u["quoted_text"] == "Screening op valrisico")["entry"] = True
    texts, _edges, _bundles, construction = _graph(_prepare(_faithful(root_entry))[1])
    assert [texts[oid] for oid in construction["graph_plan"]["entrypoints"]] == ["Screening op valrisico"]


def test_model_cannot_add_words_reorder_spans_or_fabricate_a_block() -> None:
    def proposer(text_change=None, spans_change=None):
        def propose(frozen):
            proposal = export_tree_proposal(request_input(frozen)[1])
            unit = proposal["units"][1]
            if text_change:
                unit["quoted_text"] = text_change(unit["quoted_text"])
            if spans_change:
                unit["spans"] = spans_change(unit["spans"])
            return proposal, "test-model"
        return propose
    for kwargs in ({"text_change": lambda t: t + " Altijd."},
                   {"spans_change": lambda s: [dict(s[0], block_id="semblock-fabricated")]}):
        with pytest.raises(ConsoleError) as error:
            _prepare(proposer(**kwargs))
        assert error.value.code == "pre_review_llm_proposal_rejected"

    fragments = [{"fragment_id": "f1", "fragment_hash": "h", "raw_text": "Eerst dit. Dan dat.",
                  "clean_text": "Eerst dit. Dan dat.", "section_path": [], "source_locator": {
                      "locator_type": "web_line_range", "locator_value": "lines:1-1;p:1"}}]
    [block] = selection_source_blocks(fragments)
    reversed_spans = [{"block_id": block["block_id"], "start": 11, "end": 19},
                      {"block_id": block["block_id"], "start": 0, "end": 10}]
    with pytest.raises(MaterialisationError, match="materialisation_span_order_invalid"):
        materialise_knowledge_candidates([{"decision_kind": "semantic_selection",
                                           "selection_origin": "proposal_selected",
                                           "spans": reversed_spans, "source_text": "Dan dat. Eerst dit."}],
                                         document_id="doc", fragments=fragments)
    with pytest.raises(MaterialisationError, match="materialisation_text_mismatch"):
        materialise_knowledge_candidates([{"decision_kind": "semantic_selection",
                                           "selection_origin": "proposal_selected",
                                           "spans": [{"block_id": block["block_id"], "start": 0, "end": 10}],
                                           "source_text": "Eerst niet dit."}],
                                         document_id="doc", fragments=fragments)


def test_failing_or_missing_model_never_falls_back_for_exports() -> None:
    def failing(_frozen):
        raise ConsoleError("pre_review_llm_timeout")
    with pytest.raises(ConsoleError) as error:
        _prepare(failing)
    assert error.value.code == "pre_review_llm_timeout"
    with pytest.raises(ConsoleError) as unbound:
        _prepare(None)
    assert unbound.value.code == "pre_review_llm_decision_tree_proposer_unbound"


def test_export_request_names_export_ids_while_pdf_request_and_recorded_evidence_stay_unchanged() -> None:
    from src.beslisboom_path_v1 import extract_boom_fragments
    from src.decision_bundles_v1 import split_bundles
    from src.decision_graph_v1 import source_evidence
    data = _data()
    fragments = split_bundles(extract_boom_fragments(data, document_id="doc", source_id="src"))
    inventory = source_evidence(None, data, "boom", fragments, "a" * 64)
    recorded = deepcopy(inventory)
    prompt, source = request_input({"kind": "boom", "fragments": fragments, "inventory": inventory})
    assert prompt == PROPOSER_PROMPT + EXPORT_PROMPT
    assert inventory == recorded
    named = {item["record"]["export_id"] for item in source["evidence_items"].values() if item["kind"] == "text"}
    assert named == {str(f["boom_id"]) for f in fragments}
    pdf_prompt, pdf_source = request_input({"kind": "pdf", "fragments": fragments, "inventory": recorded})
    assert pdf_prompt == PROPOSER_PROMPT
    assert all("record" not in item for item in pdf_source["evidence_items"].values() if item["kind"] == "text")


def test_no_deterministic_formation_route_or_its_configuration_remains() -> None:
    assert not (ROOT / "src/atomic_split_v1.py").exists()
    retired = re.compile(r"split_context_aware_units|_deterministic_fragments_and_spec|\b_spec_from_fragments"
                         r"|\bexport_proposal\b|deterministic-export-v1|atomic_split_v1|DETERMINISTIC_MODE"
                         r"|STRATEGY_DETERMINISTIC|proposed_relations_for_units|REASON_EXPLICIT_ROLLBACK")
    offenders = [str(path.relative_to(ROOT)) for folder in ("src", "scripts")
                 for path in (ROOT / folder).rglob("*.py") if retired.search(path.read_text(encoding="utf-8"))]
    assert offenders == []
    # Only the materialiser assigns knowledge-candidate identity.
    creators = [str(path.relative_to(ROOT)) for path in (ROOT / "src").rglob("*.py")
                if re.search(r'-sem-\{', path.read_text(encoding="utf-8"))]
    assert creators == ["src/knowledge_materialisation_v1.py"]


def _accounts(console):
    return {role: console.create_account(username=role, password=f"{role}-secret", roles=(role,),
                                         display_name=role.title())
            for role in ("researcher", "reviewer", "publisher")}


def _ingest(console, accounts, *, data, filename, content_type, class_="richtlijn", **extra):
    return console.ingest(actor_id=accounts["researcher"]["account_id"], filename=filename, data=data,
                          content_type=content_type, ingest_kind="new", title="Bron", version="1.0",
                          date="2026-10-22", live_url="", class_=class_, family="kwaliteit",
                          named_reviewers=[accounts["reviewer"]["account_id"]], **extra)


HTML = ("<!doctype html><html lang=\"nl\"><body><h1>Behandeling</h1>"
        "<p>Bespreek de behandeling met de zorgvrager. Gebruik middel X niet bij nierfalen.</p>"
        "</body></html>").encode("utf-8")


def test_unconfigured_runtime_fails_explicitly_and_a_configured_runtime_forms_semantically(
        tmp_path: Path, *, production_console) -> None:
    from tests.semantic_fixture_support import bind_fixture_selections
    paths = dict(root=tmp_path / "root", source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    console = production_console(processing_binder=lambda console: None, **paths)
    accounts = _accounts(console)
    # No implicit formation route: the configuration error surfaces and no candidate exists.
    with pytest.raises(ConsoleError) as error:
        _ingest(console, accounts, data=HTML, filename="bron.html", content_type="text/html")
    assert error.value.code == "source_processing_strategy_unconfigured"
    assert all(console.snapshot_objects(e["snapshot_id"]) == [] for e in console.list_envelopes())

    restarted = production_console(processing_binder=bind_fixture_selections, **paths)
    receipt = _ingest(restarted, accounts, data=HTML, filename="bron.html", content_type="text/html")
    objects = [o for o in restarted.snapshot_objects(receipt["snapshot_id"]) if o["object_type"] != "document"]
    candidates = [o for o in objects if (o.get("metadata") or {}).get("semantic_passage", {}).get(
        "selection_origin") == "proposal_selected"]
    headings = [o for o in objects if o["object_type"] == "heading"]
    assert candidates and all("-sem-" in o["object_id"] for o in candidates)
    assert all(o["metadata"]["passage_formation"]["strategy"] == "semantic" for o in candidates)
    assert [o["content"]["clean_text"] for o in headings] == ["Behandeling"]
    assert all("-sem-" not in o["object_id"] for o in headings)
    # The negation stays exactly as in the source.
    assert any("Gebruik middel X niet bij nierfalen." in o["content"]["clean_text"] for o in candidates)


def test_export_outside_the_decision_tree_class_is_formed_semantically(tmp_path: Path, *, production_console) -> None:
    from tests.semantic_fixture_support import bind_fixture_selections
    from tests.test_explicit_review_policy import policy
    from tests.test_v225_beslisboom_path import _accounts as tree_accounts, _ingest_boom
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path / "root",
                                 source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    accounts = tree_accounts(console)
    receipt = _ingest_boom(console, accounts, class_="richtlijn", named_reviewers=[],
                           review_policy=policy(accounts))
    envelope = console._envelope(receipt["snapshot_id"])
    assert envelope["content_kind"] == "boom" and "decision_tree_formation" not in envelope
    objects = [o for o in console.snapshot_objects(receipt["snapshot_id"]) if o["object_type"] != "document"]
    assert objects and all("-sem-" in o["object_id"] for o in objects)
    assert all(o["metadata"]["semantic_passage"]["formation_mode"] == "semantic-source-bound-v1" for o in objects)
