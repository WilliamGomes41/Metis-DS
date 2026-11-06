"""KO-3 exact publication facts, without a second serving authority.

# release-control-evidence: scope/belofte exact snapshot/version/hash membership
# release-control-evidence: opslag native PostgreSQL read-only history and registry
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.integrity_kernel import compute_canonical_object_hash
from src.publication.canonical_publication_postgres_v1 import (
    PostgresCanonicalPublicationStore, REQUIRED_TABLES,
)
from src.review import knowledge_object_state_v1 as ko
from tests.test_successor_release_cutover_v1 import _object

pytestmark = [pytest.mark.release_control_scope_belofte, pytest.mark.release_control_opslag,
              pytest.mark.release_control_slop, pytest.mark.release_control_releasebewijs]


def publish(store, *, sid="source-1", release="release-1", oid="ko-1", version="1",
            checksum="a" * 64, at="2026-11-01T12:00:00+00:00", recovery=False):
    obj = _object(object_id=oid, version=version, document_id="document-1",
                  checksum=checksum, text="A synthetic knowledge object.")
    store.persist_published_release(logical_document_id="logical-1", working_revision_id="work-" + sid,
        snapshot_id=sid, source_sha256=checksum, source_locator="g2://fixture/" + checksum,
        release_id=release, release_version=version, release_owner="fixture-publisher", published_at=at,
        objects=[obj], preserve_newer_registry=recovery)
    return obj


def key(obj):
    return (obj["object_id"], obj["object_version"], compute_canonical_object_hash(obj))


def facts(store, obj, sid="source-1"):
    return store.object_publication_membership(sid, [key(obj)])[key(obj)]


def physical_state(store):
    with store._connect() as con:
        return {table: con.execute("SELECT COALESCE(jsonb_agg(to_jsonb(row)), '[]'::jsonb) AS rows "
                                  "FROM " + table + " row").fetchone()["rows"]
                for table in sorted(REQUIRED_TABLES)}


def test_exact_active_tuple_and_wrong_snapshot_hash_or_working_version(complete_postgres, monkeypatch):
    store = PostgresCanonicalPublicationStore(complete_postgres)
    obj = publish(store)
    before = physical_state(store)
    connections, statements = [], []
    original = store._connect

    class ReadConnection:
        def __enter__(self):
            self.connection = original().__enter__()
            connections.append(self.connection)
            return self

        def __exit__(self, *args):
            return self.connection.__exit__(*args)

        def execute(self, statement, params=None):
            statements.append(statement)
            return self.connection.execute(statement, params)

    changed = deepcopy(obj)
    changed["object_version"] = "2"
    selected = [key(obj), key(changed), (obj["object_id"], obj["object_version"], "f" * 64)]
    with monkeypatch.context() as patch:
        patch.setattr(store, "_connect", ReadConnection)
        rows = store.object_publication_membership("source-1", selected)
    assert len(connections) == len(statements) == 1
    assert "canonical_json" not in statements[0]
    assert len(rows) == 3
    assert ko.object_release_status(obj, rows[key(obj)]) == "published"
    assert ko.object_release_status(obj, {**rows[key(obj)], "registry_has_release_item": "false"}) == "none"
    assert ko.object_release_status(obj, {**rows[key(obj)], "snapshot_id": None,
                                         "registry_snapshot_id": None}) == "none"
    assert ko.object_release_status(changed, rows[key(changed)]) == "none"
    assert rows[selected[2]]["release_id"] is None
    assert rows[selected[2]]["registry_content_hash"] == key(obj)[2]
    wrong_source = facts(store, obj, "a-different-source")
    assert wrong_source["release_id"] is None
    assert ko.object_release_status(obj, wrong_source) == "none"
    assert physical_state(store) == before


def test_active_registry_is_not_gated_by_historical_release_status(complete_postgres):
    store = PostgresCanonicalPublicationStore(complete_postgres)
    obj = publish(store)
    with store._connect() as con:
        con.execute("UPDATE publication_releases SET status='withdrawn' WHERE release_id='release-1'")
    row = facts(store, obj)
    assert row["release_status"] == "withdrawn"
    assert row["registry_state"] == "active"
    assert ko.object_release_status(obj, row) == "published"
    assert store.active_publication_rows()[0]["knowledge_object"] == obj


def test_withdrawal_remains_inactive_after_reopening_store(complete_postgres):
    store = PostgresCanonicalPublicationStore(complete_postgres)
    obj = publish(store)
    store.withdraw_logical_document(logical_document_id="logical-1", expected_release_id="release-1",
        actor="fixture-publisher", reason="Fixture withdrawal", withdrawn_at="2026-11-02T12:00:00+00:00")
    restarted = PostgresCanonicalPublicationStore(complete_postgres)
    row = facts(restarted, obj)
    assert row["registry_state"] == "emergency_unpublished"
    assert row["withdrawn_at"]
    assert ko.object_release_status(obj, row) == "withdrawn"
    assert restarted.active_publication_rows() == []


def test_successor_removing_old_id_uses_durable_supersession_evidence(complete_postgres):
    store = PostgresCanonicalPublicationStore(complete_postgres)
    old = publish(store)
    new = publish(store, sid="source-2", release="release-2", oid="different-ko", version="2",
                  checksum="b" * 64, at="2026-11-02T12:00:00+00:00")
    row = facts(store, old)
    assert row["registry_state"] is None
    assert row["successor_release_id"] == row["later_logical_release_id"] == "release-2"
    assert ko.object_release_status(old, row) == "superseded"
    assert ko.object_release_status(new, facts(store, new, "source-2")) == "published"
    assert {r["knowledge_object"]["object_id"] for r in store.active_publication_rows()} == {new["object_id"]}


@pytest.mark.parametrize("new_oid", ["new-ko", "ko-1"])
def test_new_version_and_historical_recovery_preserve_current_serving(complete_postgres, new_oid):
    store = PostgresCanonicalPublicationStore(complete_postgres)
    new = publish(store, sid="source-2", release="release-2", oid=new_oid, version="2",
                  checksum="b" * 64, at="2026-11-02T12:00:00+00:00")
    old = publish(store, recovery=True)
    row = facts(store, old)
    assert row["historical_recovery"] is row["registry_preserved"] is True
    assert row["registry_state"] == ("active" if new_oid == old["object_id"] else None)
    assert row["successor_release_id"] is None
    assert row["later_logical_release_id"] == "release-2"
    assert ko.object_release_status(old, row) == "superseded"
    assert {r["knowledge_object"]["object_id"] for r in store.active_publication_rows()} == {new["object_id"]}


def test_missing_registry_without_retirement_proof_is_not_invented(complete_postgres):
    store = PostgresCanonicalPublicationStore(complete_postgres)
    obj = publish(store)
    with store._connect() as con:
        con.execute("DELETE FROM publication_registry WHERE object_id=%s", (obj["object_id"],))
    row = facts(store, obj)
    assert row["release_id"] == "release-1"
    assert row["successor_release_id"] is row["later_logical_release_id"] is row["registry_state"] is None
    assert ko.object_release_status(obj, row) == "none"


@pytest.mark.parametrize("remove_binding", [False, True])
def test_active_tuple_with_open_review_reports_invalid_without_writing(
    tmp_path, remove_binding, monkeypatch, *, production_console,
):
    from tests.test_d5_3b_review_routing_cutover import _console
    console, _accounts, sid, oid = _console(tmp_path, production_console=production_console)
    if remove_binding:
        console._bindings[sid] = []
        console._save_bindings()
    obj = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    envelope = console._envelope(sid)
    store = console.canonical_publication_store
    store.persist_published_release(snapshot_id=sid,
        source_sha256=obj["source"]["source_checksum"], source_locator="g2://fixture/invalid-approval",
        release_id="invalid-approved-release", release_version="1", release_owner="fixture-publisher",
        published_at="2026-11-01T12:00:00+00:00", objects=[obj])
    before = physical_state(store)
    original = store.object_publication_membership

    def read_after_workflow_scope(*args, **kwargs):
        from src.workflows.workflow_transaction_v1 import workflow_transaction_active
        assert console._document_reads() is None
        assert not workflow_transaction_active()
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "object_publication_membership", read_after_workflow_scope)
    states = ko.snapshot_ko_states(console, envelope)
    current = console.snapshot_objects(sid)
    result = next(row for row, selected in zip(states, current, strict=True) if selected["object_id"] == oid)
    assert result["state"] == (ko.IN_REVIEW if remove_binding else ko.TWEEDE_REVIEW)
    assert "published_not_approved" in result["invalid"]
    assert ko.has_recorded_approval(obj)
    assert physical_state(store) == before


def test_inventory_keeps_unconfirmed_history_explicit(complete_postgres, tmp_path):
    from tests.test_vsa_publish_document_v1 import MemorySourceStore, _ready_console, canonical_store
    store = canonical_store(complete_postgres)
    console, accounts, receipt = _ready_console(tmp_path, complete_postgres, store, MemorySourceStore())
    sid = receipt["snapshot_id"]
    assert console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)["status"] == "PASS"
    target = next(obj for obj in console.snapshot_objects(sid) if obj.get("confirmed_object_type") == "explanation")
    with store._connect() as con:
        con.execute("DELETE FROM publication_registry WHERE object_id=%s", (target["object_id"],))
    before = physical_state(store)
    states = ko.snapshot_ko_states(console, console._envelope(sid))
    current = console.snapshot_objects(sid)
    result = next(row for row, obj in zip(states, current, strict=True) if obj["object_id"] == target["object_id"])
    assert result["state"] == ko.GOEDGEKEURD
    assert "publication_activation_unconfirmed" in result["reasons"]
    assert result["invalid"] == []
    assert physical_state(store) == before


def test_published_projection_keeps_structural_context_without_workflow_reads(monkeypatch):
    from tests.test_retrieval_projection_v2 import by_id, published_envelope
    from src.retrieval.retrieval_projection_v2 import build_projection
    objects = by_id()
    rec = deepcopy(objects["vvn-osteoporose-fractuurpreventie-2024-p015-rec-recent-fracture-50plus-01"])
    parent = deepcopy(objects["vvn-osteoporose-fractuurpreventie-2024-document"])
    rec["parent_object_id"] = parent["object_id"]
    monkeypatch.setattr(ko, "derive_ko_state", lambda *a, **k: pytest.fail("published projection read live state"))
    projected, blocked = build_projection([published_envelope(parent), published_envelope(rec)])
    assert blocked == []
    record = next(row for row in projected if row["metadata"]["object_id"] == rec["object_id"])
    assert parent["object_id"] in record["metadata"]["context_object_ids"]
    assert ko.has_recorded_approval(published_envelope(rec)["knowledge_object"])
    for bad in [None, {}, "approved"]:
        assert not ko.has_recorded_approval({"governance": bad})
