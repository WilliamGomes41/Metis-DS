"""A10: installed repair routes, replaceable cache, durable restart and rollback.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs

PostgreSQL is native. Azure Blob SDK transport is a disk-backed synthetic fixture;
the production AzureBlobSourceStore verification and locator parser are real.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from src.g2_source_store import AzureBlobSourceStore
from src.integrity_kernel import stable_hash, stamp_canonical_hashes
from src.operations_console_v1 import ConsoleError
from src.review_ledger import read_events
from src.review_policy_v1 import CONTRACT as REVIEW_POLICY_CONTRACT
from src.source_preparation_context_v1 import KEY
from src.workflow_store_configuration import POSTGRES_STORE_SETTINGS
from tests.semantic_fixture_support import bind_fixture_selections, install_fixture_history
from tests.complete_workflow_support import complete_postgres as workflow_postgres  # noqa: F401


TEXT = "De verpleegkundige bespreekt passende ondersteuning. De keuze wordt samen geevalueerd."
HTML = f"<html><body><h1>Zorg</h1><p>{TEXT}</p><p>Een tweede bronpassage blijft behouden.</p></body></html>".encode()


class DiskBlobTransport:
    """Only substitute network I/O; keep immutable adapter checks in production code."""
    def __init__(self, root):
        self.root = Path(root)

    def get_blob_client(self, *, container, blob):
        path = self.root / container / blob
        class Blob:
            def upload_blob(self, data, **kwargs):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)

            def download_blob(self):
                class Download:
                    def readall(self):
                        return path.read_bytes()
                return Download()
        return Blob()


def installed(root, cache, backend, patch):
    """Use the real composition root; only inject isolated infrastructure factories."""
    from src import console_asgi as composition
    patch.delenv("WEBSITE_SITE_NAME", raising=False)
    patch.setenv("CONSOLE_DATA_ROOT", str(root))
    patch.setenv("CONSOLE_RUNTIME", str(root / "runtime"))
    patch.setenv("CONSOLE_SOURCE_STORE", str(cache))
    patch.setattr(composition, "_postgres_credential", lambda: None)
    patch.setattr(composition, "_canonical_store", lambda **kw: None)
    patch.setattr(composition, "bootstrap_accounts", lambda console: None)
    patch.setattr(composition, "bind_pre_review_semantic_processing", bind_fixture_selections)
    source = AzureBlobSourceStore(blob_service_client=DiskBlobTransport(root / "immutable"))
    patch.setattr(composition, "_immutable_source_store", lambda: source)
    stores = [None] * 4
    for name in POSTGRES_STORE_SETTINGS:
        patch.delenv(name, raising=False)
    if backend == "postgres":
        from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig, PostgresCanonicalPublicationStore
        from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
        from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
        from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
        from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
        config = PostgresCanonicalConfig(dsn=os.environ["METIS_TEST_POSTGRES_DSN"])
        stores = [PostgresWorkflowIdentityStore(config), PostgresConcurrentWorkflowDocumentStore(config),
                  PostgresWorkflowReviewStore(config), PostgresWorkflowRemainingStore(config)]
        # #718: only a complete PostgreSQL configuration selects native authority.
        for name in POSTGRES_STORE_SETTINGS:
            patch.setenv(name, "postgres")
        canonical = PostgresCanonicalPublicationStore(config)
        patch.setattr(composition, "_canonical_store", lambda canonical=canonical, **kw: canonical)
    for name, store in zip(("_workflow_identity_store", "_workflow_document_store",
                            "_workflow_review_store", "_workflow_remaining_store"), stores):
        patch.setattr(composition, name, lambda store=store, **kw: store)
    app = composition.build_app()
    return app, app.state.operations_kernel


@pytest.fixture(params=["local", "postgres"])
def backend(request):
    if request.param == "postgres":
        request.getfixturevalue("workflow_postgres")
    return request.param


def state(console, sid):
    reviews = getattr(console, "workflow_review_store", None)
    bindings = reviews.read_bindings() if reviews else console._load_map(console._bindings_path)
    return deepcopy({"objects": console._load_objects(sid, remember=False),
        "envelope": console._envelope(sid), "bindings": bindings,
        "revision": console.objects_revision(sid), "events": read_events(console._ledger_path)})


def seed(root, backend, route, patch):
    patch.setenv("METIS_PDF_EXTRACTOR", "legacy-comparison")
    app, console = installed(root, root / "cache-old", backend, patch)
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    bind_fixture_selections(console)
    data, filename, kind = HTML, "source.html", "text/html"
    if "pdf" in route:
        import fitz
        with fitz.open() as document:
            page = document.new_page()
            page.insert_textbox(fitz.Rect(72, 72, 500, 200), TEXT)
            page.insert_text((72, 250), "Een tweede bronpassage blijft behouden.")
            data = document.tobytes()
        filename, kind = "source.pdf", "application/pdf"
        if route == "decision-pdf":
            from tests.test_decision_unit_construction import pdf_data
            data = pdf_data()
        if route.startswith("docling"):
            from src.docling_contract_v1 import translate
            from src.integrity_kernel import sha256_file
            from tests.test_docling_contract_v1 import result
            def accepted_extraction(kind, path, *, document_id, source_id, **kwargs):
                payload = result()
                payload["source_sha256"] = sha256_file(path)
                payload["document"]["pages"]["1"]["size"] = {"width": 595, "height": 842}
                item = payload["document"]["texts"][0]
                item.update(text=TEXT, orig=TEXT)
                item["prov"][0].update(charspan=[0, len(TEXT)],
                    bbox={"l": 72, "r": 500, "t": 72, "b": 200, "coord_origin": "TOPLEFT"})
                return translate(payload, document_id=document_id, source_id=source_id,
                                 source_sha256=payload["source_sha256"])
            patch.setattr(console, "_extract", accepted_extraction)
    if route == "decision-boom":
        from tests.test_v225_beslisboom_path import _boom_freeze_bytes
        data, filename, kind = _boom_freeze_bytes(), "source.json", "application/json"
    receipt = console.ingest(actor_id=author["account_id"], filename=filename, data=data,
        content_type=kind, ingest_kind="new", title="A10 synthetic", version="1.0",
        date="2026-10-12", live_url="", class_="beslisboom" if route.startswith("decision") else "richtlijn", family="fixture",
        named_reviewers=[reviewer["account_id"]],
        review_policy=({"contract": REVIEW_POLICY_CONTRACT, "revision": 1,
                        "primary": reviewer["account_id"], "assignments": []} if route == "decision-pdf" else None))
    sid = receipt["snapshot_id"]
    rows = console._load_objects(sid, remember=False)
    target = next(row for row in console.snapshot_objects(sid)
                  if ((row.get("metadata") or {}).get("semantic_passage", {}).get("selection_origin") == "proposal_selected"
                      if not route.startswith("decision") else row["object_type"] not in {"document", "heading"}))
    if not route.startswith("decision"):
        assert KEY in console._envelope(sid)
    if route.startswith("legacy"):
        # Model supported persisted pre-selection records; never use a fake catalog.
        for row in rows:
            row.get("metadata", {}).pop("semantic_passage", None)
            stamp_canonical_hashes(row)
        install_fixture_history(console, sid, rows)
    if route in {"legacy-html", "legacy-pdf", "docling-historical-pdf"}:
        envelope = deepcopy(console._envelope(sid))
        envelope.pop(KEY)
        replace_envelope(console, sid, envelope)
    target = console._current_object(sid, target["object_id"])
    return app, console, reviewer, sid, target, data


def replace_envelope(console, sid, envelope):
    """Deliberate historical/corruption setup in isolated storage, not a product writer."""
    store = getattr(console, "workflow_document_store", None)
    if store:
        with store._connect() as connection:
            connection.execute("UPDATE workflow.documents SET envelope_payload=%s::jsonb WHERE snapshot_id=%s",
                               (json.dumps(envelope), sid))
        console.refresh_workflow_documents()
    else:
        console._envelopes[sid] = deepcopy(envelope)
        console._save_envelopes()


def client_for(app):
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/login", data={"username": "reviewer", "password": "fixture-only"},
                       follow_redirects=False).status_code == 303
    return client


def selected(units, target):
    own = {ref["raw_object_id"] for ref in target["provenance"]["source_fragments"]}
    return [row["unit_id"] for row in units if row["fragment_id"] in own]


def resolve(client, console, sid, target, unit_ids, revision=None):
    return client.post("/review/resolve", data={"snapshot_id": sid, "object_id": target["object_id"],
        "snapshot_revision": revision or console.objects_revision(sid), "suitability": "mist_context",
        "comment": "Gebruik deze geverifieerde bronselectie.", "repair_kind": "source_units",
        "source_unit_ids": unit_ids}, follow_redirects=False)


def forbid_formation(console, patch, retained):
    def forbidden(*args, **kwargs):
        raise AssertionError("A10 reader invoked formation/model work")
    patch.setattr(console, "_fragments_and_spec", forbidden)
    patch.setattr(console, "_source_processing_strategy", forbidden)
    import src.knowledge_materialisation_v1 as materialisation
    patch.setattr(materialisation, "materialise_knowledge_candidates", forbidden)
    if retained:
        patch.setattr(console, "_extract", forbidden)


@pytest.mark.parametrize("route", ["selected-html", "legacy-retained-html", "legacy-html",
                                  "selected-pdf", "legacy-pdf", "docling-retained-pdf",
                                  "docling-historical-pdf", "decision-pdf", "decision-boom"])
@pytest.mark.parametrize("first", ["original", "repair-screen"])
def test_cache_move_real_routes_and_new_revision(backend, tmp_path, monkeypatch, route, first):
    _, initial, reviewer, sid, target, data = seed(tmp_path, backend, route, monkeypatch)
    units = initial.source_units(snapshot_id=sid, object_id=target["object_id"])
    catalog = initial.source_fragment_catalog(snapshot_id=sid, object_id=target["object_id"])
    before = state(initial, sid)
    old = Path(initial._envelope(sid)["binary_path"])
    shutil.rmtree(tmp_path / "cache-old")
    app, console = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    assert not old.exists()
    with monkeypatch.context() as patch:
        forbid_formation(console, patch, route not in {"legacy-html", "legacy-pdf", "decision-pdf", "decision-boom"})
        client = client_for(app)
        if first == "original":
            response = client.get("/review/bronpassage", params={"document": sid, "object": target["object_id"]})
            assert response.status_code == 200, response.text
        else:
            response = client.post("/review", data={"snapshot_id": sid, "object_id": target["object_id"],
                "snapshot_revision": before["revision"], "suitability": "mist_context",
                "eindoordeel": "goedkeuren_na_correctie", "comment": "Bronselectie aanpassen.",
                "documentpositie_action": "dit_klopt", "type_action": "dit_klopt"})
            assert response.status_code == 200, response.text
            assert 'action="/review/resolve"' in response.text
        assert console.source_units(snapshot_id=sid, object_id=target["object_id"]) == units
        assert console.source_fragment_catalog(snapshot_id=sid, object_id=target["object_id"]) == catalog
        assert console.open_source_passage(snapshot_id=sid, object_id=target["object_id"], include_document=True)["freeze_bytes"] == data
        assert state(console, sid) == before
        assert not old.exists()
    ids = selected(units, target)
    assert ids
    if not route.startswith("decision"):
        assert len(ids) >= 2
        ids = ids[:1]
    response = resolve(client, console, sid, target, ids)
    assert response.status_code == 303, response.text
    _, fresh = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    revised = fresh._current_object(sid, target["object_id"])
    assert revised["object_version"] != target["object_version"]
    assert revised["governance"]["validation_status"] == "needs_review"
    expected_text = (target["content"]["clean_text"] if route == "decision-pdf"
                     else " ".join(row["text"] for row in units if row["unit_id"] in ids))
    assert revised["content"]["clean_text"] == expected_text
    if not route.startswith("decision"):
        assert revised["content"]["clean_text"] != target["content"]["clean_text"]
    assert revised["provenance"]["source_fragments"] == target["provenance"]["source_fragments"]
    assert fresh._envelope(sid)["sha256"] == before["envelope"]["sha256"]
    audit = [event for event in read_events(fresh._ledger_path)
             if event["event_type"] == "review_audit_evidence" and event["details"].get("decision") == "repair_source_units"]
    assert audit and audit[-1]["object_version"] == revised["object_version"]
    assert audit[-1]["details"]["source_hash"] == before["envelope"]["sha256"]
    assert [row["unit_id"] for row in audit[-1]["details"]["repair_spec"]["source_units"]] == ids
    assert any(event["event_type"] == "revision_created" and event["object_version"] == revised["object_version"]
               for event in read_events(fresh._ledger_path))
    winner = state(fresh, sid)
    stale = resolve(client, fresh, sid, target, ids, before["revision"])
    assert stale.status_code == 400
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        fresh.submit_review_resolution(actor_id=reviewer["account_id"],
            snapshot_id=sid, object_id=target["object_id"], expected_revision=before["revision"],
            suitability="mist_context", comment="Verouderde bronselectie.", repair_kind="source_units", source_unit_ids=ids)
    assert state(fresh, sid) == winner


@pytest.mark.parametrize("fault", ["missing-bytes", "corrupt-bytes", "missing-ref", "changed-ref", "changed-locator", "changed-mapping"])
def test_invalid_authority_blocks_without_partial_state(backend, tmp_path, monkeypatch, fault):
    _, console, _, sid, target, _ = seed(tmp_path, backend, "selected-html", monkeypatch)
    units = console.source_units(snapshot_id=sid, object_id=target["object_id"])
    if fault.endswith("bytes"):
        blob = next((tmp_path / "immutable").rglob("source.html"))
        if fault == "missing-bytes":
            blob.unlink()
        else:
            blob.write_bytes(b"wrong immutable bytes")
    else:
        rows = console._load_objects(sid, remember=False)
        row = next(row for row in rows if row["object_id"] == target["object_id"] and row["object_version"] == target["object_version"])
        ref = row["provenance"]["source_fragments"][0]
        if fault == "changed-locator":
            ref["source_locator"]["locator_value"] = "lines:1-1"
        elif fault == "changed-mapping":
            row["metadata"]["semantic_passage"]["source_mapping"][0]["raw_end"] -= 1
        else:
            ref["raw_object_id" if fault == "missing-ref" else "raw_content_hash"] = "missing" if fault == "missing-ref" else "0" * 64
        stamp_canonical_hashes(row)
        install_fixture_history(console, sid, rows)
    before = state(console, sid)
    shutil.rmtree(tmp_path / "cache-old")
    app, fresh = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    response = resolve(client_for(app), fresh, sid, target, selected(units, target))
    assert response.status_code >= 400, response.text
    with pytest.raises(ConsoleError, match={"missing-bytes": "immutable_source_recovery_failed",
        "corrupt-bytes": "immutable_source_recovery_failed", "missing-ref": "repair_source_fragment_missing",
        "changed-ref": "repair_source_fragment_changed", "changed-locator": "repair_source_fragment_changed",
        "changed-mapping": "materialisation_source_mapping_invalid"}[fault]):
        fresh.source_units(snapshot_id=sid, object_id=target["object_id"])
    _, final = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    assert state(final, sid) == before
    assert not Path(before["envelope"]["binary_path"]).exists()
    if fault.endswith("bytes"):
        assert not (tmp_path / "cache-new").exists() or not list((tmp_path / "cache-new").rglob("source.html"))


def test_late_audit_failure_rolls_back_revision_and_review(backend, tmp_path, monkeypatch):
    _, initial, _, sid, target, _ = seed(tmp_path, backend, "selected-html", monkeypatch)
    units = initial.source_units(snapshot_id=sid, object_id=target["object_id"])
    before = state(initial, sid)
    shutil.rmtree(tmp_path / "cache-old")
    app, console = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    def failed(**kwargs):
        # The new revision has been staged at this real repair boundary.
        assert console._current_object(sid, target["object_id"])["object_version"] != target["object_version"]
        raise OSError("synthetic_late_repair_audit_failure")
    monkeypatch.setattr(console, "_append_audit_evidence", failed)
    assert resolve(client_for(app), console, sid, target, selected(units, target)).status_code == 500
    _, fresh = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    assert state(fresh, sid) == before


def test_new_process_reads_same_units_after_cache_move(backend, tmp_path, monkeypatch):
    _, console, _, sid, target, _ = seed(tmp_path, backend, "selected-html", monkeypatch)
    expected = console.source_units(snapshot_id=sid, object_id=target["object_id"])
    before = state(console, sid)
    shutil.rmtree(tmp_path / "cache-old")
    code = """
import json,sys,pytest
from pathlib import Path
from tests.test_a10_source_cache_repair import installed,forbid_formation,state
root,sid,oid,backend=Path(sys.argv[1]),*sys.argv[2:]
with pytest.MonkeyPatch.context() as patch:
    app,console=installed(root,root/'cache-new',backend,patch)
    forbid_formation(console,patch,True)
    print(json.dumps({'units':console.source_units(snapshot_id=sid,object_id=oid),'state':state(console,sid)}))
"""
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path), sid, target["object_id"], backend],
                            capture_output=True, text=True, check=True, timeout=30)
    observed = json.loads(result.stdout)
    assert observed == {"units": expected, "state": before}
    assert not Path(before["envelope"]["binary_path"]).exists()


def test_mapping_change_during_preparation_preserves_winner(backend, tmp_path, monkeypatch):
    _, initial, _, sid, target, _ = seed(tmp_path, backend, "selected-html", monkeypatch)
    units = initial.source_units(snapshot_id=sid, object_id=target["object_id"])
    shutil.rmtree(tmp_path / "cache-old")
    app, console = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    original = console.source_units
    reads, winner = [], []
    def change_after_read(**kwargs):
        result = original(**kwargs)
        reads.append(1)
        if len(reads) == 2:  # closure evidence first, command preparation second
            envelope = deepcopy(console._envelope(sid))
            record = envelope[KEY]
            ref_id = target["provenance"]["source_fragments"][0]["raw_object_id"]
            fragment = next(row for row in record["fragments"] if row["fragment_id"] == ref_id)
            fragment["source_locator"]["locator_value"] = "lines:1-1"
            record["fragments_hash"] = stable_hash(record["fragments"])
            record["record_hash"] = stable_hash({key: value for key, value in record.items() if key != "record_hash"})
            replace_envelope(console, sid, envelope)
            winner.append(state(console, sid))
        return result
    monkeypatch.setattr(console, "source_units", change_after_read)
    assert resolve(client_for(app), console, sid, target, selected(units, target)).status_code >= 400
    assert winner
    _, fresh = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    assert state(fresh, sid) == winner[0]


@pytest.mark.parametrize("table,deferred", [("document_objects", False), ("review_events", True)])
def test_native_sql_failure_is_atomic_after_cache_move(workflow_postgres, tmp_path, monkeypatch, table, deferred):
    import psycopg
    from psycopg import sql
    _, initial, _, sid, target, _ = seed(tmp_path, "postgres", "selected-html", monkeypatch)
    units = initial.source_units(snapshot_id=sid, object_id=target["object_id"])
    before = state(initial, sid)
    shutil.rmtree(tmp_path / "cache-old")
    app, console = installed(tmp_path, tmp_path / "cache-new", "postgres", monkeypatch)
    failures = []
    submit = console.submit_review_resolution
    def observe(**kwargs):
        try:
            return submit(**kwargs)
        except Exception as exc:
            while exc.__cause__ is not None:
                exc = exc.__cause__
            failures.append(exc)
            raise
    monkeypatch.setattr(console, "submit_review_resolution", observe)
    with psycopg.connect(workflow_postgres.dsn, autocommit=True) as connection:
        condition = (sql.SQL("NEW.payload->>'object_version' <> {}").format(sql.Literal(target["object_version"]))
                     if table == "document_objects" else sql.SQL("NEW.event_type = 'review_audit_evidence'"))
        body = sql.SQL("BEGIN IF NEW.object_id = {} AND {} THEN RAISE EXCEPTION 'a10_native_write_failure'; END IF; RETURN NEW; END;").format(
            sql.Literal(target["object_id"]), condition)
        connection.execute(sql.SQL("CREATE FUNCTION workflow.a10_failure() RETURNS trigger LANGUAGE plpgsql AS {}").format(sql.Literal(body.as_string(connection))))
        trigger = ("CREATE CONSTRAINT TRIGGER a10_failure AFTER INSERT ON workflow.{} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.a10_failure()"
                   if deferred else "CREATE TRIGGER a10_failure AFTER INSERT ON workflow.{} FOR EACH ROW EXECUTE FUNCTION workflow.a10_failure()")
        connection.execute(sql.SQL(trigger).format(sql.Identifier(table)))
    response = resolve(client_for(app), console, sid, target, selected(units, target))
    assert response.status_code >= 400
    assert failures and isinstance(failures[-1], psycopg.errors.RaiseException)
    assert "a10_native_write_failure" in str(failures[-1])
    _, fresh = installed(tmp_path, tmp_path / "cache-new", "postgres", monkeypatch)
    assert state(fresh, sid) == before


@pytest.mark.parametrize("actor", ["author", "not-named"])
def test_repair_reuses_authorization_without_domain_write(backend, tmp_path, monkeypatch, actor):
    _, initial, _, sid, target, _ = seed(tmp_path, backend, "selected-html", monkeypatch)
    units = initial.source_units(snapshot_id=sid, object_id=target["object_id"])
    initial.create_account(username="not-named", password="fixture-only", roles=("reviewer",))
    before = state(initial, sid)
    shutil.rmtree(tmp_path / "cache-old")
    app, console = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/login", data={"username": actor, "password": "fixture-only"},
                       follow_redirects=False).status_code == 303
    with monkeypatch.context() as patch:
        forbid_formation(console, patch, True)
        assert resolve(client, console, sid, target, selected(units, target)).status_code >= 400
    _, fresh = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    assert state(fresh, sid) == before


@pytest.mark.parametrize("route", ["legacy-html", "legacy-pdf"])
@pytest.mark.parametrize("fault", [None, "locator", "page", "bbox"])
def test_historical_merge_verifies_every_target_after_cache_move(backend, tmp_path, monkeypatch, route, fault):
    _, initial, _, sid, primary, _ = seed(tmp_path, backend, route, monkeypatch)
    targets = [row for row in initial.snapshot_objects(sid)
               if row["object_id"] != primary["object_id"]
               and row["object_type"] not in {"document", "heading"}
               and row.get("proposed_object_type") != "heading"
               and row["provenance"]["source_fragments"]]
    assert targets
    other = targets[0]
    assert not (other.get("metadata") or {}).get("semantic_passage")
    if fault:
        history = initial._load_objects(sid, remember=False)
        row = next(row for row in history if row["object_id"] == other["object_id"]
                   and row["object_version"] == other["object_version"])
        ref = row["provenance"]["source_fragments"][0]
        if fault == "locator":
            ref["source_locator"]["locator_value"] = ("lines:1-1" if route == "legacy-html"
                else "page:1;bbox:0.000000,0.000000,1.000000,1.000000")
        elif fault == "page":
            ref["page"] = 999
        else:
            ref["bbox"] = [0, 0, 1, 1]
        stamp_canonical_hashes(row)
        install_fixture_history(initial, sid, history)
    before = state(initial, sid)
    shutil.rmtree(tmp_path / "cache-old")
    app, console = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    client = client_for(app)
    response = client.post("/review/resolve", data={"snapshot_id": sid,
        "object_id": primary["object_id"], "snapshot_revision": before["revision"],
        "suitability": "samenvoegen", "comment": "Voeg de twee geverifieerde passages samen.",
        "repair_kind": "merge_objects", "merge_object_ids": [other["object_id"]]}, follow_redirects=False)
    _, fresh = installed(tmp_path, tmp_path / "cache-new", backend, monkeypatch)
    assert not Path(before["envelope"]["binary_path"]).exists()
    if fault:
        assert response.status_code == 400, response.text
        assert state(fresh, sid) == before  # includes revision, supersession, bindings and audit
    else:
        assert response.status_code == 303, response.text
        repaired = fresh._current_object(sid, primary["object_id"])
        absorbed = fresh._current_object(sid, other["object_id"])
        assert repaired["object_version"] != primary["object_version"]
        assert repaired["governance"]["validation_status"] == "needs_review"
        assert absorbed["governance"]["validation_status"] == "superseded"
        assert absorbed["governance"]["superseded_by"] == primary["object_id"]
        assert repaired["content"]["clean_text"] == " ".join(
            " ".join(row["content"]["clean_text"].split()) for row in [primary, other])
        assert any(event["event_type"] == "review_audit_evidence"
                   and event["details"].get("decision") == "repair_merge_objects"
                   for event in read_events(fresh._ledger_path))
