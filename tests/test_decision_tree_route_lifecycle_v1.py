"""The single decision-tree route in the real console, plus retired-route boundaries.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
# release-control-evidence: slop
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from src.decision_graph_v1 import read_active_graph, verify_source_evidence
from src.decision_unit_construction_v1 import CONTRACT as LEGACY_CONTRACT, KEY as LEGACY_KEY, unit_issues
from src.integrity_kernel import stable_hash, stamp_canonical_hashes
from src.operations_console_v1 import ConsoleError
from tests.semantic_fixture_support import install_fixture_history
from tests.test_decision_graph_chain import _accounts, _console, _ingest_boom, command, complete_graph, ingest, policy

ROOT = Path(__file__).resolve().parents[1]


def _objects(console, sid):
    return [o for o in console.snapshot_objects(sid) if o["object_type"] != "document"]


def test_pdf_and_export_trees_are_formed_by_the_sole_materialiser_and_record_the_route(tmp_path, *, production_console):
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    pdf = ingest(console, accounts)["snapshot_id"]
    export = _ingest_boom(console, accounts, review_policy=policy(accounts), named_reviewers=[])["snapshot_id"]
    for sid, model in ((pdf, "test-proposer"), (export, "test-proposer")):
        envelope = console._envelope(sid)
        formation = envelope["decision_tree_formation"]
        assert formation["route"] == "decision-tree-source-bound-v1" and formation["model"] == model
        assert formation["actor"] == accounts["researcher"]["account_id"]
        assert "decision_unit_contract" not in envelope
        assert envelope["decision_graph"]["unresolved"][0] == "human_route_confirmation_required"
        for obj in _objects(console, sid):
            semantic = obj["metadata"]["semantic_passage"]
            assert semantic["formation_mode"] == "decision-tree-source-bound-v1"
            assert obj["object_id"].startswith(f'{envelope["document_id"]}-sem-')
            assert LEGACY_KEY not in obj["metadata"]
    # Export-stated proposals survive as proposals for the reviewer to confirm.
    outcome = next(o for o in _objects(console, export) if o["content"]["clean_text"] == "Verwijs naar de valpoli.")
    question = next(o for o in _objects(console, export) if o["content"]["clean_text"] == "Is er een verhoogd valrisico?")
    assert outcome["proposed_object_type"] == "outcome"
    assert [(r["relation_type"], r["target_object_id"], r["confirmed"]) for r in outcome["relations"]] == [
        ("applies_if", question["object_id"], False)]


def test_unbound_or_failing_proposer_blocks_without_objects_or_fallback(tmp_path, monkeypatch, *, production_console):
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    del console._decision_tree_proposer
    sid = ingest(console, accounts)["snapshot_id"]
    envelope = console._envelope(sid)
    assert envelope["processing_blocker"] == "pre_review_llm_decision_tree_proposer_unbound"
    assert console.snapshot_objects(sid) == [] and "decision_graph" not in envelope

    def fabricated(frozen):
        from tests.decision_tree_test_support import fragment_proposal
        proposal, model = fragment_proposal(frozen)
        proposal["units"][0]["quoted_text"] = "Verzonnen tekst."
        return proposal, model
    console._decision_tree_proposer = fabricated
    sid = ingest(console, accounts)["snapshot_id"]
    envelope = console._envelope(sid)
    assert envelope["processing_blocker"] == "pre_review_llm_proposal_rejected"
    assert console.snapshot_objects(sid) == []


def test_released_route_graph_is_read_whole_and_tampering_is_rejected(tmp_path, *, production_console):
    from tests.decision_tree_test_support import install_fragment_proposer
    from tests.test_durable_publication_console_v1 import MemorySourceStore

    source = MemorySourceStore()

    def state():
        return install_fragment_proposer(production_console(processing_binder=bind_fixture_selections,
            root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime",
            immutable_source_store=source))
    console = state()
    store = console.canonical_publication_store
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    console.update_decision_graph(**command(console, accounts, sid, "graph", graph=complete_graph(console, sid)))
    for obj in _objects(console, sid):
        console.review_object(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                              object_id=obj["object_id"], decision="approve", confirmed_object_type="node")
    console.update_decision_graph(**command(console, accounts, sid, "graph-2", graph=complete_graph(console, sid)))
    console.confirm_decision_graph(**command(console, accounts, sid, "confirm"))
    result = console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
    assert result["status"] == "PASS", result
    payload = read_active_graph(store, source, sid)
    restarted = state()
    restarted.reconcile_durable_publications()
    assert read_active_graph(store, source, sid) == payload
    released = deepcopy(store.release_for_snapshot(sid)["decision_graph_release"])
    original = deepcopy(released)
    for tamper in ("text", "span", "mode", "review"):
        target = next(o for o in released["objects"] if o["object_type"] != "document")
        if tamper == "text":
            target["content"]["clean_text"] += " Altijd."
        elif tamper == "span":
            target["metadata"]["semantic_passage"]["spans"][0]["end"] -= 1
        elif tamper == "mode":
            released["graph"]["nodes"][0]["mode"] = "context"
        else:
            released["reviews"] = []
        def persist_fixture(value):
            from psycopg.types.json import Jsonb
            with store._connect() as connection:
                connection.execute("UPDATE audit_events SET details=jsonb_set(details,'{decision_graph_release}',%s::jsonb) "
                                   "WHERE entity_id=%s AND event_type='release_published'",
                                   (Jsonb(value), result['release_id']))
        persist_fixture(released)
        with pytest.raises(ValueError, match="decision_graph_release_invalid|decision_graph_release_mismatch"):
            read_active_graph(store, source, sid)
        persist_fixture(original)
        released = deepcopy(original)


def _legacy_fixture(console, sid):
    """A persisted pre-cutover unit: evidence in the retired contract, no route marker."""
    envelope = console._envelope(sid)
    path, _ = console._verified_source_bytes(envelope)
    fragments = {f["fragment_id"]: f for f in console._read_source_fragments(envelope, path)}
    rows = console._load_objects(sid, remember=False)
    current = {(o["object_id"], o["object_version"]) for o in console.snapshot_objects(sid)}
    for row in rows:
        if row["object_type"] == "document" or (row["object_id"], row["object_version"]) not in current:
            continue
        refs = row["provenance"]["source_fragments"]
        fragment = fragments[refs[0]["raw_object_id"]]
        text = fragment["clean_text"]
        row["metadata"].pop("semantic_passage")
        row["provenance"]["source_fragments"] = refs[:1]
        row["content"]["clean_text"] = row["content"]["raw_text"] = text
        row["metadata"][LEGACY_KEY] = {
            "contract": LEGACY_CONTRACT, "separator": "\n", "literal_hash": stable_hash(text),
            "role": "action", "reason_codes": [], "grouping_evidence": [],
            "spans": [{"fragment_id": fragment["fragment_id"], "start": 0, "end": len(text),
                       "fragment_text_hash": stable_hash(text), "source_fragment_hash": fragment["fragment_hash"],
                       "text_sha256": stable_hash(text), "locator": deepcopy(fragment["source_locator"])}]}
        stamp_canonical_hashes(row)
    install_fixture_history(console, sid, rows)
    legacy = deepcopy(envelope)
    for key in ("decision_tree_formation", "decision_tree_construction"):
        legacy.pop(key)
    legacy["decision_unit_contract"] = LEGACY_CONTRACT
    console._envelopes[sid] = legacy
    console._save_envelopes()
    return legacy


def test_retired_route_work_stays_readable_but_is_never_re_formed(tmp_path, monkeypatch, *, production_console):
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    legacy = _legacy_fixture(console, sid)
    # Historical reading reconstructs evidence only: no formation, no materialiser.
    import src.knowledge_materialisation_v1 as materialiser

    def forbidden(*_args, **_kwargs):
        raise AssertionError("historical read invoked formation")
    monkeypatch.setattr(materialiser, "materialise_knowledge_candidates", forbidden)
    monkeypatch.setattr(console, "_fragments_and_spec", forbidden)
    verify_source_evidence(console, legacy)
    for obj in _objects(console, sid):
        assert unit_issues(obj) in ([], ["decision_unit_incomplete"])
    target = _objects(console, sid)[0]
    console.review_object(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                          object_id=target["object_id"], decision="revise", comment="Bronselectie aanpassen.")
    before = deepcopy(console.snapshot_objects(sid))
    with pytest.raises(ConsoleError, match="decision_unit_legacy_revision_retired"):
        console.correct_object(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                               object_id=target["object_id"], expected_revision=console.objects_revision(sid),
                               patch={"reason": "Bron", "operations": [
                                   {"op": "set", "path": "content.clean_text", "value": "Bespreek"}]})
    with pytest.raises(ConsoleError, match="decision_tree_legacy_route_retired"):
        console.reextract_unpublished(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid)
    assert console.snapshot_objects(sid) == before


def test_retired_formation_code_is_gone_and_unreachable():
    """Import graph and symbol proof; text search alone cannot cover dynamic calls."""
    import importlib
    import src.decision_unit_construction_v1 as legacy
    import src.beslisboom_path_v1 as boom
    import src.decision_graph_v1 as graph
    for name in ("construction_spec", "groups", "record", "rebuild_for_revision", "add_layout", "source_lines"):
        assert not hasattr(legacy, name)
    assert not hasattr(boom, "boom_spec_from_fragments")
    assert not hasattr(graph, "prepare_graph")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("src.pdf_route_proposals_v1")
    retired = {"construction_spec", "boom_spec_from_fragments", "prepare_graph", "propose_routes",
               "rebuild_for_revision", "pdf_route_proposals_v1"}
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        names |= {a.name.split(".")[-1] for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                  for a in n.names}
        names |= {(n.module or "").split(".")[-1] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not names & retired, (path.name, names & retired)
