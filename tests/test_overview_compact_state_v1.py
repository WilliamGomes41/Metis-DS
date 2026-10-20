"""Recovery step 1 (H1: D-PERF-1, D-PERF-2): overviews MOETEN uit compacte opgeslagen staat renderen.

Regels:
- GET /publish en GET /source-selection zonder ``document`` MOETEN NOOIT de
  volledige gereedheidscontrole, ``incomplete(objects=...)``, ``stored_extraction``
  of de bronreconstructie-helper ``_read_source_blocks`` per document aanroepen.
- Zonder actueel bewijs MOET de kaart "volledigheid nog niet gecontroleerd" tonen
  en NOOIT "voltooid" of "publicatiegereed".
- De volledige controle MOET alleen voor het geselecteerde document draaien, en
  POST /publish MOET de volledige poort ongewijzigd opnieuw uitvoeren.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

import pytest

import src.knowledge_materialisation_v1 as materialisation
import src.publication_readiness_v1 as readiness
import src.recoverable_formation_v1 as formation
import src.source_preparation_context_v1 as preparation
from tests import test_vsa_publish_readiness_ui_v1 as publish_fixture

pytestmark = [pytest.mark.release_control_opslag]

UNCHECKED = "volledigheid nog niet gecontroleerd"
N_DOCUMENTS = 3


def _documents(tmp_path: Path, count: int=N_DOCUMENTS, *, production_console):
    console, accounts, receipt, source = publish_fixture._console_with_document(tmp_path, production_console=production_console)
    receipts = [receipt]
    for index in range(1, count):
        receipts.append(console.ingest(
            actor_id=accounts["researcher"]["account_id"],
            filename=f"continentie-{index}.html",
            data=publish_fixture.HTML_FIXTURE.read_bytes(),
            content_type="text/html",
            ingest_kind="new",
            title=f"Continentie fixture {index}",
            version="1.0",
            date="2025-04-01",
            live_url=f"https://example.test/continentie-{index}",
            class_="richtlijn",
            family=f"continentie-{index}",
            named_reviewers=[accounts["researcher"]["account_id"], accounts["reviewer"]["account_id"]],
        ))
    for row in receipts:
        assert console.snapshot_objects(row["snapshot_id"]), "fixture MOET objecten hebben"
    return console, accounts, receipts, source


@pytest.fixture
def helper_calls(monkeypatch: pytest.MonkeyPatch) -> Counter:
    calls: Counter = Counter()

    def counted(name, original):
        def wrapper(*args, **kwargs):
            calls[name] += 1
            if name == "incomplete" and kwargs.get("objects") is not None:
                calls["incomplete_deep"] += 1
            return original(*args, **kwargs)
        return wrapper

    monkeypatch.setattr(materialisation, "_read_source_blocks",
                        counted("read_source_blocks", materialisation._read_source_blocks))
    monkeypatch.setattr(readiness.PublicationReadinessMixin, "publication_readiness",
                        counted("publication_readiness", readiness.PublicationReadinessMixin.publication_readiness))
    monkeypatch.setattr(preparation, "stored_extraction",
                        counted("stored_extraction", preparation.stored_extraction))
    monkeypatch.setattr(formation, "incomplete", counted("incomplete", formation.incomplete))
    from src.operations_console_v1 import OperationsConsole
    monkeypatch.setattr(OperationsConsole, "snapshot_objects",
                        counted("snapshot_objects_deepcopy", OperationsConsole.snapshot_objects))
    return calls


def _mark_formation_incomplete(console, snapshot_ids):
    for sid in snapshot_ids:
        envelope = console._envelope(sid)
        envelope.setdefault("semantic_replay", {}).setdefault("provider_evidence", {})["formation_incomplete"] = True
        console._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)


# --- /publish -----------------------------------------------------------------

def test_publish_overview_makes_zero_helper_calls_for_n_documents(tmp_path, helper_calls, *, production_app, production_console):
    console, _accounts, receipts, _source = _documents(tmp_path, production_console=production_console)
    client = publish_fixture._client(console, production_app=production_app)
    publish_fixture._login(client, "publisher.carla")
    helper_calls.clear()

    page = client.get("/publish")

    assert page.status_code == 200
    for row in receipts:
        assert str(row["snapshot_id"]) in page.text
    assert helper_calls["read_source_blocks"] == 0
    assert helper_calls["publication_readiness"] == 0
    assert helper_calls["incomplete_deep"] == 0


def test_publish_overview_never_shows_unchecked_document_as_ready(tmp_path, helper_calls, *, production_app, production_console):
    console, accounts, receipts, _source = _documents(tmp_path, count=1, production_console=production_console)
    publish_fixture._complete_review(console, accounts, receipts[0])
    client = publish_fixture._client(console, production_app=production_app)
    publish_fixture._login(client, "publisher.carla")

    page = client.get("/publish")

    assert page.status_code == 200
    assert UNCHECKED in page.text
    assert 'data-publication-state="unchecked"' in page.text
    assert 'data-publication-state="ready"' not in page.text
    assert "data-publish-form" not in page.text
    assert "Klaar voor publicatie" not in page.text
    assert "publicatiegereed" not in page.text.lower()
    assert "voltooid" not in page.text.lower()
    assert f'/publish?document={receipts[0]["snapshot_id"]}' in page.text


def test_publish_selected_document_runs_full_check_for_that_document_only(tmp_path, helper_calls, *, production_app, production_console):
    console, accounts, receipts, _source = _documents(tmp_path, production_console=production_console)
    publish_fixture._complete_review(console, accounts, receipts[0])
    client = publish_fixture._client(console, production_app=production_app)
    publish_fixture._login(client, "publisher.carla")
    helper_calls.clear()

    page = client.get("/publish", params={"document": receipts[0]["snapshot_id"]})

    assert page.status_code == 200
    assert helper_calls["publication_readiness"] == 1
    assert 'data-publication-state="ready"' in page.text
    assert page.text.count("data-publish-form") == 1
    assert page.text.count('data-publication-state="unchecked"') == N_DOCUMENTS - 1


def test_invalid_publish_is_still_refused_at_post(tmp_path, helper_calls, *, production_app, production_console):
    console, accounts, receipts, source = _documents(tmp_path, count=1, production_console=production_console)
    publish_fixture._complete_review(console, accounts, receipts[0])
    client = publish_fixture._client(console, production_app=production_app)
    publish_fixture._login(client, "publisher.carla")
    source.blobs[str(receipts[0]["immutable_storage_locator"])] = b"gewijzigd na overzicht"
    helper_calls.clear()

    blocked = client.post("/publish", data={"snapshot_id": receipts[0]["snapshot_id"], "publish_confirmed": "yes"})

    assert blocked.status_code == 400
    assert 'data-error-code="g2_source_checksum_mismatch"' in blocked.text
    assert console.snapshot_is_published(receipts[0]["snapshot_id"]) is False
    # De POST-poort MOET de volledige controle draaien.
    assert helper_calls["publication_readiness"] >= 1


# --- Bronselectie ----------------------------------------------------------------

def test_source_selection_overview_makes_zero_helper_calls_for_n_documents(tmp_path, helper_calls, *, production_app, production_console):
    console, _accounts, receipts, _source = _documents(tmp_path, production_console=production_console)
    _mark_formation_incomplete(console, [r["snapshot_id"] for r in receipts])
    client = publish_fixture._client(console, production_app=production_app)
    publish_fixture._login(client, "researcher.anne")
    helper_calls.clear()

    page = client.get("/source-selection")

    assert page.status_code == 200
    assert helper_calls["read_source_blocks"] == 0
    assert helper_calls["stored_extraction"] == 0
    assert helper_calls["incomplete_deep"] == 0
    # D-PERF-4: het overzicht MAG NIET de volledige objectlijst kopiëren.
    assert helper_calls["snapshot_objects_deepcopy"] == 0


def test_source_selection_never_shows_unchecked_formation_as_complete(tmp_path, helper_calls, *, production_app, production_console):
    console, _accounts, receipts, _source = _documents(tmp_path, production_console=production_console)
    _mark_formation_incomplete(console, [r["snapshot_id"] for r in receipts])
    client = publish_fixture._client(console, production_app=production_app)
    publish_fixture._login(client, "researcher.anne")

    page = client.get("/source-selection")

    assert page.status_code == 200
    assert "Status: voltooid" not in page.text
    assert page.text.count(f"Status: {UNCHECKED}") == N_DOCUMENTS


def test_source_selection_selected_document_runs_full_check_only_for_it(tmp_path, helper_calls, *, production_app, production_console):
    console, _accounts, receipts, _source = _documents(tmp_path, production_console=production_console)
    _mark_formation_incomplete(console, [r["snapshot_id"] for r in receipts])
    client = publish_fixture._client(console, production_app=production_app)
    publish_fixture._login(client, "researcher.anne")
    helper_calls.clear()

    page = client.get("/source-selection", params={"document": receipts[0]["snapshot_id"]})

    assert page.status_code == 200
    assert helper_calls["stored_extraction"] == 1
    assert helper_calls["incomplete_deep"] == 1
    assert page.text.count(f"Status: {UNCHECKED}") == N_DOCUMENTS - 1
    assert "Status: voltooid" not in page.text


# --- timing/telling op representatieve fixture ------------------------------------

def test_overview_cost_is_independent_of_document_count(tmp_path, helper_calls, *, production_app, production_console):
    console, _accounts, receipts, _source = _documents(tmp_path, count=6, production_console=production_console)
    _mark_formation_incomplete(console, [r["snapshot_id"] for r in receipts[::2]])
    publisher = publish_fixture._client(console, production_app=production_app)
    publish_fixture._login(publisher, "publisher.carla")
    researcher = publish_fixture._client(console, production_app=production_app)
    publish_fixture._login(researcher, "researcher.anne")
    helper_calls.clear()

    started = time.perf_counter()
    assert publisher.get("/publish").status_code == 200
    assert researcher.get("/source-selection").status_code == 200
    elapsed = time.perf_counter() - started

    print("OVERVIEW_COST", dict(helper_calls), "documents", len(receipts), "seconds", round(elapsed, 3))
    assert helper_calls["read_source_blocks"] == 0
    assert helper_calls["publication_readiness"] == 0
    assert helper_calls["stored_extraction"] == 0
    assert helper_calls["incomplete_deep"] == 0
    assert helper_calls["snapshot_objects_deepcopy"] == 0
    assert elapsed < 10


def test_stale_selected_check_is_recomputed_on_every_request(tmp_path, helper_calls, *, production_app, production_console):
    """Opslag stale/concurrent: een eerder gereed resultaat MAG NIET blijven hangen."""
    console, accounts, receipts, source = _documents(tmp_path, count=1, production_console=production_console)
    publish_fixture._complete_review(console, accounts, receipts[0])
    client = publish_fixture._client(console, production_app=production_app)
    publish_fixture._login(client, "publisher.carla")
    sid = receipts[0]["snapshot_id"]
    assert 'data-publication-state="ready"' in client.get("/publish", params={"document": sid}).text
    source.blobs.pop(str(receipts[0]["immutable_storage_locator"]))

    stale = client.get("/publish", params={"document": sid})
    overview = client.get("/publish")

    assert 'data-publication-state="ready"' not in stale.text
    assert "data-publish-form" not in stale.text
    assert 'data-publication-state="unchecked"' in overview.text
