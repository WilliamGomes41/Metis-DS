"""Source-grounded shared outcomes, cross-page references and explicit choice modes.

# release-control-evidence: kwaliteit
# release-control-evidence: scope/belofte
"""
from copy import deepcopy
import fitz
import pytest

from src.decision_graph_v1 import graph_issues
from tests.test_decision_graph_chain import _console, _accounts, _ingest_boom, policy


def structure(tmp_path, mode):
    with fitz.open() as doc:
        page = doc.new_page()
        for y, text in [(80, "Hoe vaak?"), (130, "Vaak"), (180, "Soms"),
                        (260, "Bespreek dit. Ga verder op pagina 2.")]:
            page.insert_text((70, y), text)
        page.draw_line((110, 90), (110, 245))
        page = doc.new_page()
        page.insert_text((70, 80), "Maak een vervolgafspraak.")
        data = doc.tobytes()
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = _ingest_boom(console, accounts, data=data, filename="shared.pdf", content_type="application/pdf",
        named_reviewers=[], review_policy=policy(accounts))["snapshot_id"]
    env = console._envelope(sid)
    objects = console.snapshot_objects(sid)
    by_text = {o["content"]["clean_text"]: o for o in objects if o["object_type"] != "document"}
    question, step, outcome = [by_text[t]["object_id"] for t in
        ("Hoe vaak?", "Bespreek dit. Ga verder op pagina 2.", "Maak een vervolgafspraak.")]
    graph = deepcopy(env["decision_graph"])
    for node in graph["nodes"]:
        node["mode"] = {question: mode, step: "continue", outcome: "terminal"}.get(node["object_id"], "context")
    line = next(k for k, v in env["decision_graph_evidence"]["items"].items() if v["kind"] == "graphic")
    label_id = lambda text: by_text[text]["provenance"]["source_fragments"][0]["raw_object_id"]
    graph["edges"] = [
        {"id": "frequent", "from": question, "to": outcome, "kind": "answer", "label": "Vaak", "evidence_ids": [line, label_id("Vaak")]},
        {"id": "sometimes", "from": question, "to": step, "kind": "answer", "label": "Soms", "evidence_ids": [line, label_id("Soms")]},
        {"id": "next-page", "from": step, "to": outcome, "kind": "continue", "label": "", "evidence_ids": [line, label_id("Bespreek dit. Ga verder op pagina 2.")]},
    ]
    graph["entrypoints"] = [question]
    graph["unresolved"] = []
    return graph, objects, env["decision_graph_evidence"]


@pytest.mark.parametrize("mode", ["single", "multiple"])
def test_shared_cross_page_outcome_and_non_boolean_choices(tmp_path, mode):
    graph, objects, evidence = structure(tmp_path, mode)
    assert graph_issues(graph, objects, evidence) == []
    missing = deepcopy(graph)
    missing["edges"].pop(1)
    assert "decision_graph_answers_incomplete" in graph_issues(missing, objects, evidence)
    invented = deepcopy(graph)
    invented["edges"][0]["label"] = "Ja"
    assert "decision_graph_label_not_literal" in graph_issues(invented, objects, evidence)
    cycle = deepcopy(graph)
    cycle["edges"][-1]["to"] = graph["entrypoints"][0]
    assert "decision_graph_cycle_unresolved" in graph_issues(cycle, objects, evidence)
