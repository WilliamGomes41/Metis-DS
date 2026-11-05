"""KO-1 (#995): derived KO state through the real PostgreSQL console.

Review, publish, withdraw and restart move the derived state; the inventory
reads through the production composition with read-only sessions and prints
counts only.

# release-control-evidence: scope/belofte een afgeleide toestand per kennisobject
# release-control-evidence: opslag postgres read-only inventaris, herstart stale recovery
# release-control-evidence: toegang bootstrap-account alleen via build_app, niet via compose_console
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

from src.review import knowledge_object_state_v1 as ko
from tests.production_support import configure_production
from tests.test_vsa_publish_document_v1 import MemorySourceStore, _console, _ready_console, canonical_store

ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _states(console, snapshot_id):
    envelope = console._envelope(snapshot_id)
    objects = console.snapshot_objects(snapshot_id)
    rows = ko.snapshot_ko_states(console, envelope)
    return {obj["object_id"]: row for obj, row in zip(objects, rows)}


def _target(console, snapshot_id):
    return next(obj["object_id"] for obj in console.snapshot_objects(snapshot_id)
                if obj.get("confirmed_object_type") == "explanation")


@pytest.fixture
def ready(tmp_path, complete_postgres):
    durable = canonical_store(complete_postgres)
    source = MemorySourceStore()
    console, accounts, receipt = _ready_console(tmp_path, complete_postgres, durable, source)
    return console, accounts, receipt["snapshot_id"], (tmp_path, complete_postgres, durable, source)


def test_reviewed_document_classifies_every_knowledge_object(ready):
    console, _accounts, snapshot_id, _ = ready
    rows = list(_states(console, snapshot_id).values())
    counts = ko.count_states(rows)
    assert counts["ko_state_unclassified"] == 0
    assert counts["invalid_total"] == 0
    assert counts["states"][ko.GOEDGEKEURD] >= 1
    # Publication readiness held, so nothing is still waiting for a reviewer.
    assert counts["states"][ko.IN_REVIEW] == counts["states"][ko.TWEEDE_REVIEW] == 0


def test_publish_withdraw_and_restart_move_the_derived_state(ready):
    console, accounts, snapshot_id, (tmp_path, config, durable, source) = ready
    target = _target(console, snapshot_id)
    assert _states(console, snapshot_id)[target]["state"] == ko.GOEDGEKEURD

    published = console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id)
    assert published["status"] == "PASS"
    assert _states(console, snapshot_id)[target]["state"] == ko.GEPUBLICEERD

    restarted = _console(tmp_path, config, durable, source, runtime_name="runtime-b")
    assert _states(restarted, snapshot_id) == _states(console, snapshot_id)

    console.withdraw_document(actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id,
                              expected_release_id=published["release_id"], reason="KO-1 test")
    assert _states(console, snapshot_id)[target]["state"] == ko.INGETROKKEN


def test_rejected_candidates_are_afgewezen(ready):
    console, _accounts, snapshot_id, _ = ready
    objects = {obj["object_id"]: obj for obj in console.snapshot_objects(snapshot_id)}
    for object_id, row in _states(console, snapshot_id).items():
        if (objects[object_id].get("governance") or {}).get("validation_status") == "rejected":
            assert row["state"] == ko.AFGEWEZEN


def test_inventory_script_reads_only_and_prints_counts(ready, tmp_path, complete_postgres, monkeypatch, capsys):
    console, _accounts, snapshot_id, _ = ready
    expected = ko.count_states(_states(console, snapshot_id).values())
    configure_production(monkeypatch, tmp_path / "inventory", complete_postgres)
    monkeypatch.setenv("PGOPTIONS", "")
    monkeypatch.setattr(sys, "argv", ["ko_state_inventory.py", "--counts-only", "--json"])
    with pytest.raises(SystemExit) as done:
        runpy.run_path(str(ROOT / "scripts" / "ko_state_inventory.py"), run_name="__main__")
    assert done.value.code == 0
    printed = capsys.readouterr().out
    counts = json.loads(printed)
    assert counts["documents"] == 1
    assert counts["states"] == expected["states"]
    assert snapshot_id not in printed
    assert not any(obj["object_id"] in printed for obj in console.snapshot_objects(snapshot_id))


def test_inventory_sessions_refuse_writes(tmp_path, complete_postgres, monkeypatch):
    import psycopg
    from src.console_asgi import compose_console
    configure_production(monkeypatch, tmp_path, complete_postgres)
    monkeypatch.setenv("PGOPTIONS", "-c default_transaction_read_only=on")
    console, _ = compose_console()
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        with console.workflow_document_store._connect() as con:
            con.execute("CREATE TEMP TABLE ko_probe (x int)")
            con.execute("INSERT INTO workflow.accounts SELECT * FROM workflow.accounts WHERE false")
            con.execute("UPDATE workflow.documents SET title = title WHERE false")


def test_fresh_ingest_is_before_approval_and_approval_moves_one_object(tmp_path, complete_postgres):
    from tests.semantic_fixture_support import bind_fixture_selections
    from tests.test_vsa_publish_document_v1 import HTML_FIXTURE, TEST_PASSWORD
    console = _console(tmp_path, complete_postgres, canonical_store(complete_postgres), MemorySourceStore(),
                       runtime_name="runtime-fresh")
    researcher = console.create_account(username="researcher.ko", password=TEST_PASSWORD, roles=("researcher",))
    reviewer = console.create_account(username="reviewer.ko", password=TEST_PASSWORD, roles=("reviewer",))
    bind_fixture_selections(console)
    snapshot_id = console.ingest(
        actor_id=researcher["account_id"], filename="continentie.html", data=HTML_FIXTURE.read_bytes(),
        content_type="text/html", ingest_kind="new", title="KO-1 fixture", version="1.0", date="2025-04-01",
        live_url="https://example.test/ko1", class_="richtlijn", family="continentie",
        named_reviewers=[reviewer["account_id"]],
    )["snapshot_id"]
    before = _states(console, snapshot_id)
    open_states = {ko.KANDIDAAT, ko.CONTEXT_OPEN, ko.BEWIJS_OPEN, ko.SAMENGESTELD, ko.IN_REVIEW}
    knowledge = {oid: row for oid, row in before.items() if row["state"] is not None}
    assert knowledge, "the fixture must yield knowledge objects"
    assert {row["state"] for row in knowledge.values()} <= open_states
    assert ko.count_states(before.values())["invalid_total"] == 0

    target = next(obj["object_id"] for obj in console.snapshot_objects(snapshot_id)
                  if obj.get("object_type") == "unclassified")
    console.review_object(actor_id=reviewer["account_id"], snapshot_id=snapshot_id, object_id=target,
                          decision="approve", confirmed_object_type="explanation")
    after = _states(console, snapshot_id)
    assert after[target]["state"] in {ko.GOEDGEKEURD, ko.TWEEDE_REVIEW}
    assert after[target]["invalid"] == []
    assert {oid: row for oid, row in after.items() if oid != target} == {
        oid: row for oid, row in before.items() if oid != target}


def test_only_build_app_bootstraps_accounts(tmp_path, complete_postgres, monkeypatch):
    from src import console_asgi
    configure_production(monkeypatch, tmp_path, complete_postgres)
    monkeypatch.setenv("CONSOLE_BOOTSTRAP_USERNAME", "beheer.ko1")
    monkeypatch.setenv("CONSOLE_BOOTSTRAP_PASSWORD", "ko1-" + "x" * 16)
    composed, _ = console_asgi.compose_console()
    assert composed.workflow_identity_store.account_by_username("beheer.ko1") is None
    app = console_asgi.build_app()
    kernel = app.state.operations_kernel
    assert kernel.workflow_identity_store.account_by_username("beheer.ko1") is not None
