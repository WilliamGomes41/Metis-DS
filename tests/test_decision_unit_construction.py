"""Source reconstruction, repair routing and existing transaction/review contracts.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: metrics teller noemer score-must-drop
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json
from pathlib import Path

import fitz
import pytest

from src.admission_gate_v1 import admission_of, ordinary_review_queue, blocked_audit_lane
from src.beslisboom_path_v1 import boom_spec_from_fragments
from src.decision_graph_v1 import pdf_fragments, graph_issues, verify_source_evidence
from src.decision_unit_construction_v1 import KEY, construction_spec, reconstruct, groups
from src.operations_console_v1 import ConsoleError
from src.passage_register_v1 import passage_register_of
from src.review_duty_v1 import repair_duty_count, review_duty_for
from tests.test_decision_graph_chain import _console, _accounts, _ingest_boom, policy, command


def pdf_data(question_lines=None, *, columns=False, ambiguous=False):
    with fitz.open() as doc:
        page = doc.new_page()
        page.draw_rect(fitz.Rect(60, 45, 235, 150))
        lines = question_lines or ["Is er sprake van een", "mantelzorger?"]
        for i, text in enumerate(lines):
            # Independent text blocks in PDF insertion order, not one text box.
            page.insert_text((75, 70+i*18), text, fontsize=11)
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


def extracted(tmp_path, data):
    path = tmp_path / "tree.pdf"
    path.write_bytes(data)
    return pdf_fragments(path, document_id="test-doc", source_id="test-source")


def spec_for(fragments):
    return construction_spec(boom_spec_from_fragments(document_id="test-doc", title="Tree",
        family="Family", class_="beslisboom", fragments=fragments), fragments)


@pytest.mark.parametrize("lines", [
    ["Is er sprake van een", "mantelzorger?"],
    ["Uit de mantelzorger", "zich over het in de", "knel komen van", "andere sociale", "rollen?"],
])
def test_real_pdf_fragments_become_one_literal_question(tmp_path, lines):
    fragments = extracted(tmp_path, pdf_data(lines))
    spec = spec_for(fragments)
    question = next(i for i in spec["objects"] if i.get("clean_text", "").startswith(lines[0]))
    assert question["clean_text"] == "\n".join(lines)
    assert len(question["source_fragment_ids"]) == len(lines)
    assert reconstruct(question["metadata"][KEY], fragments) == question["clean_text"]
    assert question["metadata"][KEY]["reason_codes"] == []
    assert spec_for(list(reversed(fragments))) == spec
    used = [fid for i in spec["objects"] for fid in i.get("source_fragment_ids", [])]
    assert sorted(used) == sorted(f["fragment_id"] for f in fragments)


def test_columns_and_complete_neighbors_do_not_merge(tmp_path):
    fragments = extracted(tmp_path, pdf_data(columns=True))
    units = groups(fragments)
    assert [f["clean_text"] for f in units[0]] == ["Is er sprake van een", "mantelzorger?"]
    assert all(len({f["_decision_layout"]["container"][0] for f in unit}) <= 1
               for unit in units if unit[0]["_decision_layout"].get("container"))
    texts = [i.get("clean_text") for i in spec_for(fragments)["objects"]]
    assert "Bespreek de situatie." in texts and "Maak een afspraak." in texts


def test_ambiguous_followers_or_missing_geometry_are_not_guessed(tmp_path):
    fragments = extracted(tmp_path, pdf_data(ambiguous=True))
    assert next(g for g in groups(fragments) if g[0]["clean_text"] == "Is er sprake van een") == [fragments[0]]
    for f in fragments:
        f["bbox"] = None
    assert all(len(g) == 1 for g in groups(fragments))


@pytest.mark.parametrize("mutation", ["text", "span", "locator", "duplicate"])
def test_construction_rejects_invented_or_stale_source(tmp_path, mutation):
    fragments = extracted(tmp_path, pdf_data())
    item = next(i for i in spec_for(fragments)["objects"] if len(i.get("source_fragment_ids", [])) == 2)
    evidence = deepcopy(item["metadata"][KEY])
    if mutation == "text": fragments[0]["clean_text"] += " verzonnen"
    elif mutation == "span": evidence["spans"][0]["end"] = 10000
    elif mutation == "locator": evidence["spans"][0]["locator"] = {}
    else: evidence["spans"].append(evidence["spans"][0])
    with pytest.raises(ValueError, match="decision_unit_source_fidelity_failure"):
        reconstruct(evidence, fragments)


def ingest(console, accounts, data):
    return _ingest_boom(console, accounts, data=data, filename="tree.pdf", content_type="application/pdf",
                        named_reviewers=[], review_policy=policy(accounts))["snapshot_id"]


def complete_graph(console, sid):
    env = console._envelope(sid)
    graph = deepcopy(env["decision_graph"])
    objects = console.snapshot_objects(sid)
    versions = {o["object_id"]:o["object_version"] for o in objects}
    for node in graph["nodes"]:
        node["object_version"] = versions[node["object_id"]]
    by_text = {o["content"]["clean_text"]: o for o in objects}
    question = next(o for o in objects if o["content"]["clean_text"].startswith("Is er sprake van een"))
    graph["entrypoints"] = [question["object_id"]]
    graph["unresolved"] = []
    for n in graph["nodes"]:
        n["mode"] = "single" if n["object_id"] == question["object_id"] else "context" if n["object_id"] in {by_text["Ja"]["object_id"], by_text["Nee"]["object_id"]} else "terminal"
    graphic = next(k for k,v in env["decision_graph_evidence"]["items"].items() if v["kind"] == "graphic")
    graph["edges"] = [{"id": label, "from": question["object_id"], "to": by_text[target]["object_id"],
                       "kind": "answer", "label": label, "evidence_ids": [graphic, by_text[label]["provenance"]["source_fragments"][0]["raw_object_id"]]}
                      for label,target in [("Ja", "Bespreek de situatie."), ("Nee", "Maak een afspraak.")]]
    return graph


def test_ingest_graph_repair_queue_and_restart_are_one_existing_workflow(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data())
    objects = console.snapshot_objects(sid)
    assert not ordinary_review_queue(objects, review_path="boom")
    assert repair_duty_count(objects, review_path="boom") == 5
    assert all(review_duty_for(o, review_path="boom") is None for o in objects)
    graph = complete_graph(console, sid)
    assert graph_issues(graph, objects, console._envelope(sid)["decision_graph_evidence"]) == []
    cmd = command(console, accounts, sid, "construction-graph", graph=graph)
    console.update_decision_graph(**cmd)
    assert console.update_decision_graph(**cmd)["idempotent"]
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        console.update_decision_graph(**{**cmd,"command_id":"stale"})
    objects = console.snapshot_objects(sid)
    assert len(ordinary_review_queue(objects, review_path="boom")) == 3
    for o in objects:
        if o["object_type"] == "document": continue
        if o["content"]["clean_text"] in {"Ja", "Nee"}:
            assert passage_register_of(o)["status"] == "used_as_context"
            with pytest.raises(ConsoleError, match="blocked_candidate_not_reviewable"):
                console.confirm_object_type(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                                            object_id=o["object_id"], confirmed_object_type="node")
        else:
            console.review_object(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                                  object_id=o["object_id"], decision="approve", confirmed_object_type="node")
    graph = complete_graph(console, sid)
    console.update_decision_graph(**command(console, accounts, sid, "current-endpoints", graph=graph))
    console.confirm_decision_graph(**command(console, accounts, sid, "confirm-construction"))
    restarted = _console(tmp_path)
    verify_source_evidence(restarted, restarted._envelope(sid))
    assert len(ordinary_review_queue(restarted.snapshot_objects(sid), review_path="boom")) == 3
    from src.decision_graph_v1 import publication_issues
    assert publication_issues(restarted._envelope(sid), restarted.snapshot_objects(sid)) == []


def test_label_as_active_node_and_dangling_question_fail_closed(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data())
    graph = complete_graph(console, sid)
    label = next(o for o in console.snapshot_objects(sid) if o["content"]["clean_text"] == "Ja")
    next(n for n in graph["nodes"] if n["object_id"] == label["object_id"])["mode"] = "terminal"
    assert "decision_branch_label_not_node" in graph_issues(graph, console.snapshot_objects(sid), console._envelope(sid)["decision_graph_evidence"])
    broken = ingest(console, accounts, pdf_data(["Is er sprake van een"]))
    obj = next(o for o in console.snapshot_objects(broken) if o["content"]["clean_text"] == "Is er sprake van een")
    assert "decision_unit_incomplete" in admission_of(obj)["reason_codes"]
    assert obj in blocked_audit_lane(console.snapshot_objects(broken))


def test_context_mode_cannot_hide_changed_source_literal_or_provenance(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data())
    graph = complete_graph(console, sid)
    objects = deepcopy(console.snapshot_objects(sid))
    label = next(o for o in objects if o["content"]["clean_text"] == "Nee")
    label["content"]["clean_text"] = "Ja"
    assert "decision_unit_source_fidelity_failure" in graph_issues(graph, objects, console._envelope(sid)["decision_graph_evidence"])
    label["content"]["clean_text"] = "Nee"
    label["provenance"]["source_fragments"][0]["source_locator"] = {}
    assert "decision_unit_source_fidelity_failure" in graph_issues(graph, objects, console._envelope(sid)["decision_graph_evidence"])


def test_actual_csv_keeps_all_139_source_fragments_and_marks_ambiguity():
    fragments = json.loads((Path(__file__).resolve().parents[1] / "data/fixtures/decision_mantelzorg_fragments.json").read_text())
    spec = spec_for(fragments)
    assert len(fragments) == 139
    assert len(spec["objects"]) == 140  # CSV contains no font or enclosure evidence: no guessed merges.
    label_items = [i for i in spec["objects"] if i.get("clean_text") in {"Ja", "Nee"}]
    assert label_items and all("decision_branch_label_not_node" in i["metadata"][KEY]["reason_codes"] for i in label_items)
    assert all(not i.get("proposed_object_type") for i in label_items)
    for text in ["Is er sprake van een", "mantelzorger?*", "signaleren"]:
        assert any(i.get("clean_text") == text and "decision_unit_incomplete" in i["metadata"][KEY]["reason_codes"] for i in spec["objects"])


def test_legacy_pdf_evidence_remains_verifiable_after_upgrade(tmp_path, monkeypatch):
    console = _console(tmp_path)
    accounts = _accounts(console)
    def legacy(kind, path, **kwargs):
        rows = pdf_fragments(path, document_id=kwargs["document_id"], source_id=kwargs["source_id"], construct_units=False)
        return rows, boom_spec_from_fragments(document_id=kwargs["document_id"], title=kwargs["title"],
                    family=kwargs["family"], class_=kwargs["class_"], fragments=rows)
    monkeypatch.setattr(console, "_fragments_and_spec", legacy)
    sid = ingest(console, accounts, pdf_data())
    assert "decision_unit_contract" not in console._envelope(sid)
    assert not any(KEY in o.get("metadata", {}) for o in console.snapshot_objects(sid))
    verify_source_evidence(console, console._envelope(sid))


def test_concurrent_graph_commands_and_interrupted_commit_preserve_work(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data())
    env_before, objects_before = deepcopy(console._envelope(sid)), deepcopy(console.snapshot_objects(sid))
    cmd = command(console, accounts, sid, "interrupted", graph=complete_graph(console, sid))
    original_commit = console._commit_prepared_store
    def fail(**kwargs):
        raise OSError("simulated_precommit_failure")
    monkeypatch.setattr(console, "_commit_prepared_store", fail)
    with pytest.raises(OSError, match="simulated_precommit_failure"):
        console.update_decision_graph(**cmd)
    assert console._envelope(sid) == env_before
    assert console.snapshot_objects(sid) == objects_before
    monkeypatch.setattr(console, "_commit_prepared_store", original_commit)
    def run(command_id):
        try:
            console.update_decision_graph(**{**cmd, "command_id": command_id})
            return "ok"
        except ConsoleError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ["concurrent-a", "concurrent-b"]))
    assert sorted(results) == ["ok", "snapshot_object_write_conflict"]
    assert len(ordinary_review_queue(_console(tmp_path).snapshot_objects(sid), review_path="boom")) == 3


def test_diagnostics_count_only_constructed_reviewable_units_and_drop_on_invalid_graph(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data())
    graph = complete_graph(console, sid)
    console.update_decision_graph(**command(console, accounts, sid, "valid", graph=graph))
    objects = console.snapshot_objects(sid)
    teller = len(ordinary_review_queue(objects, review_path="boom"))
    noemer = len([o for o in objects if o["object_type"] != "document"])
    assert (teller, noemer) == (3, 5)
    graph = complete_graph(console, sid)
    graph["unresolved"] = ["unverified_route"]
    console.update_decision_graph(**command(console, accounts, sid, "uncertain", graph=graph))
    # score-must-drop: an unresolved graph cannot retain prior admission.
    assert len(ordinary_review_queue(console.snapshot_objects(sid), review_path="boom")) == 0
