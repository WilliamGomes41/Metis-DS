"""Protocol v2.26 first wave: Klasse wijzigen / controlled reclassification.

Narrow wave only. Selective invalidation, published-candidate fork, and
full previous_review schema are out of scope. publish() stays G2-BLOCKED.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.klasse_wijzigen_v1 import (
    DOCUMENT_CLASS_CHANGED_EVENT,
    class_change_consequence,
    is_cross_model_class_change,
    review_model_for_klasse,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.review_ledger import read_events


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def _accounts(console: OperationsConsole) -> dict[str, dict]:
    researcher = console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher", "reviewer"),
        display_name="Anne Onderzoeker",
    )
    reviewer = console.create_account(
        username="reviewer.bert",
        password="bert-secret",
        roles=("reviewer",),
        display_name="Bert Reviewer",
    )
    publisher = console.create_account(
        username="publisher.carla",
        password="carla-secret",
        roles=("publisher",),
        display_name="Carla Publisher",
    )
    return {"researcher": researcher, "reviewer": reviewer, "publisher": publisher}


def _boom_freeze_bytes() -> bytes:
    payload = {
        "kind": "beslisboom-freeze",
        "paths": [{"id": "path-screening", "text": "Screening op valrisico"}],
        "nodes": [
            {
                "id": "node-vraag",
                "text": "Is er een verhoogd valrisico?",
                "scorelist": False,
            }
        ],
        "outcomes": [
            {
                "id": "out-verwijs",
                "text": "Verwijs naar de valpoli.",
                "applies_if": ["node-vraag"],
            }
        ],
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _ingest_boom(console: OperationsConsole, accounts: dict[str, dict], **overrides) -> dict:
    kwargs = {
        "actor_id": accounts["researcher"]["account_id"],
        "filename": "valrisico-boom.json",
        "data": _boom_freeze_bytes(),
        "content_type": "application/json",
        "ingest_kind": "new",
        "title": "Valrisico boom",
        "version": "1.0",
        "date": "2025-04-01",
        "live_url": "",
        "class_": "beslisboom",
        "family": "valrisico",
        "named_reviewers": [accounts["reviewer"]["account_id"]],
    }
    kwargs.update(overrides)
    return console.ingest(**kwargs)


def _ingest_richtlijn(console: OperationsConsole, accounts: dict[str, dict], **overrides) -> dict:
    kwargs = {
        "actor_id": accounts["researcher"]["account_id"],
        "filename": "continentie.html",
        "data": HTML_FIXTURE.read_bytes(),
        "content_type": "text/html",
        "ingest_kind": "new",
        "title": "Continentie fixture",
        "version": "1.0",
        "date": "2025-04-01",
        "live_url": "https://example.test/continentie",
        "class_": "richtlijn",
        "family": "continentie",
        "named_reviewers": [accounts["reviewer"]["account_id"]],
    }
    kwargs.update(overrides)
    return console.ingest(**kwargs)


def _html_client(tmp_path: Path) -> tuple[TestClient, OperationsConsole, dict]:
    console = _console(tmp_path)
    accounts = _accounts(console)
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    return client, console, accounts


def _source_identity(receipt: dict) -> dict[str, object]:
    return {
        "sha256": receipt["sha256"],
        "title": receipt["title"],
        "version": receipt["version"],
        "locator": receipt["locator"],
        "source_id": receipt["source_id"],
        "live_url": receipt.get("live_url"),
        "immutable_storage_locator": receipt.get("immutable_storage_locator"),
        "binary_path": receipt["binary_path"],
        "date": receipt["date"],
    }


def test_review_model_matrix_same_versus_cross() -> None:
    for klasse in ("richtlijn", "handreiking", "artikel", "transcript", "podcast"):
        assert review_model_for_klasse(klasse) == "richtlijn"
        assert is_cross_model_class_change(klasse, "beslisboom") is True
        assert is_cross_model_class_change("beslisboom", klasse) is True
    assert review_model_for_klasse("beslisboom") == "boom"
    assert is_cross_model_class_change("transcript", "artikel") is False
    assert is_cross_model_class_change("artikel", "handreiking") is False
    assert is_cross_model_class_change("handreiking", "richtlijn") is False
    assert is_cross_model_class_change("richtlijn", "artikel") is False
    assert is_cross_model_class_change("richtlijn", "beslisboom") is True
    assert is_cross_model_class_change("beslisboom", "richtlijn") is True


def test_console_action_renamed_klasse_wijzigen_not_promoveren(tmp_path: Path) -> None:
    client, console, accounts = _html_client(tmp_path)
    _ingest_richtlijn(console, accounts)
    html = client.get("/tree").text
    assert "Documentenhiërarchie" in html
    assert re.search(r"<button\b[^>]*>\s*Klasse wijzigen\s*</button>", html)
    assert not re.search(r"<button\b[^>]*>\s*Promoveren\s*</button>", html, flags=re.I)
    assert "Klasse wijzigen" in html
    assert "envelope" not in html.lower()


def test_cross_model_direct_change_blocked_keeps_prior_objects(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    richtlijn = _ingest_richtlijn(console, accounts)
    boom = _ingest_boom(console, accounts)
    before_richtlijn = console.snapshot_objects(richtlijn["snapshot_id"])
    before_boom = console.snapshot_objects(boom["snapshot_id"])
    before_ids = {row["object_id"] for row in before_richtlijn}

    with pytest.raises(ConsoleError, match="cross_model_direct_change_blocked"):
        console.promote_class(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=richtlijn["snapshot_id"],
            new_class="beslisboom",
        )
    with pytest.raises(ConsoleError, match="cross_model_direct_change_blocked"):
        console.promote_class(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=boom["snapshot_id"],
            new_class="richtlijn",
        )

    after_richtlijn = console.list_envelopes()
    live_richtlijn = next(row for row in after_richtlijn if row["snapshot_id"] == richtlijn["snapshot_id"])
    live_boom = next(row for row in after_richtlijn if row["snapshot_id"] == boom["snapshot_id"])
    assert live_richtlijn["class"] == "richtlijn"
    assert live_boom["class"] == "beslisboom"
    assert {row["object_id"] for row in console.snapshot_objects(richtlijn["snapshot_id"])} == before_ids
    assert [row["object_id"] for row in console.snapshot_objects(boom["snapshot_id"])] == [
        row["object_id"] for row in before_boom
    ]


def test_cross_model_requires_reextract_new_graph_prior_objects_audit_history(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    boom = _ingest_boom(console, accounts)
    prior = console.snapshot_objects(boom["snapshot_id"])
    prior_ids = [row["object_id"] for row in prior]
    prior_types = {row.get("object_type") or row.get("proposed_object_type") for row in prior}
    freeze_before = Path(boom["binary_path"]).read_bytes()
    identity = _source_identity(boom)

    changed = console.promote_class(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=boom["snapshot_id"],
        new_class="richtlijn",
        reextract=True,
    )
    assert changed["class"] == "richtlijn"
    live = console.snapshot_objects(boom["snapshot_id"])
    live_ids = [row["object_id"] for row in live]
    assert live_ids
    assert live_ids != prior_ids
    assert not ({"path", "node", "outcome"} & {row.get("object_type") for row in live if row.get("object_type") != "document"})
    assert all(obj["governance"]["validation_status"] == "needs_review" for obj in live)
    assert changed["clinical_rereview_required"] is True

    history = console.prior_object_audit_history(boom["snapshot_id"])
    assert history
    archived = history[-1]
    assert archived["from_class"] == "beslisboom"
    assert archived["to_class"] == "richtlijn"
    assert [row["object_id"] for row in archived["objects"]] == prior_ids
    assert {"path", "node", "outcome"} & prior_types

    assert Path(changed["binary_path"]).read_bytes() == freeze_before
    assert _source_identity(changed) == identity


def test_cross_model_html_to_boom_reextract_required_does_not_relabel(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_richtlijn(console, accounts)
    prior_ids = [row["object_id"] for row in console.snapshot_objects(receipt["snapshot_id"])]
    with pytest.raises(ConsoleError, match="cross_model_direct_change_blocked"):
        console.promote_class(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            new_class="beslisboom",
        )
    with pytest.raises(ConsoleError, match="invalid_boom_freeze|cross_model_reextract_required"):
        console.promote_class(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            new_class="beslisboom",
            reextract=True,
        )
    live = next(row for row in console.list_envelopes() if row["snapshot_id"] == receipt["snapshot_id"])
    assert live["class"] == "richtlijn"
    assert [row["object_id"] for row in console.snapshot_objects(receipt["snapshot_id"])] == prior_ids


def test_same_model_uses_full_rereview_not_selective(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_richtlijn(console, accounts, class_="transcript", title="Transcript fixture")
    objects = console.snapshot_objects(receipt["snapshot_id"])
    assert objects
    for row in objects:
        row["governance"]["validation_status"] = "validated"
        row["governance"]["validated_by"] = "reviewer.bert"
        row["governance"]["validation_date"] = "2026-09-01"
        row["governance"]["review_snapshot_hash"] = "hash-before"
    console._save_objects(receipt["snapshot_id"], objects)
    prior_ids = [row["object_id"] for row in objects]

    changed = console.promote_class(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        new_class="artikel",
    )
    assert changed["class"] == "artikel"
    assert changed["clinical_rereview_required"] is True
    after = console.snapshot_objects(receipt["snapshot_id"])
    assert [row["object_id"] for row in after] == prior_ids
    assert all(obj["governance"]["validation_status"] == "needs_review" for obj in after)
    assert all(obj["governance"]["validated_by"] is None for obj in after)
    assert all(obj["governance"]["review_snapshot_hash"] is None for obj in after)
    assert "previous_review" not in changed
    assert "selective_invalidation" not in changed
    consequence = class_change_consequence("transcript", "artikel")
    assert consequence["model"] == "same_model"
    assert consequence["objects"] == "kept"
    assert consequence["review"] == "full_re_review"


def test_preconfirm_consequence_shown_on_documentenhierarchie(tmp_path: Path) -> None:
    client, console, accounts = _html_client(tmp_path)
    _ingest_richtlijn(console, accounts)
    html = client.get("/tree").text
    lower = html.lower()
    assert "bron blijft ongewijzigd" in lower or "bron ongewijzigd" in lower
    assert "sha-256" in lower
    assert "titel" in lower
    assert "versie" in lower
    assert "same-model" in lower
    assert "cross-model" in lower
    assert "volle herreview" in lower
    assert "re-extract" in lower
    assert "objecten blijven" in lower or "objecten blijven" in html.lower()
    assert "envelope" not in lower
    assert re.search(r'name=["\']confirm["\']', html, flags=re.I)


def test_class_change_recorded_as_audit_event(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_richtlijn(console, accounts, class_="transcript", title="Audit klasse")
    console.promote_class(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        new_class="artikel",
    )
    events = [
        row
        for row in read_events(console._ledger_path)
        if row.get("event_type") == DOCUMENT_CLASS_CHANGED_EVENT
    ]
    assert events
    event = events[-1]
    assert event["event_type"] == "document_class_changed"
    assert event["actor"] == "reviewer.bert"
    assert event["occurred_at"]
    details = event["details"]
    assert details["snapshot_id"] == receipt["snapshot_id"]
    assert details["sha256"] == receipt["sha256"]
    assert details["from_class"] == "transcript"
    assert details["to_class"] == "artikel"
    assert details["title"] == "Audit klasse"
    assert "Metis" not in event["actor"]
    assert "Implementation engineer" not in event["actor"]
    assert "Auditor" not in event["actor"]


def test_source_sha_title_version_provenance_unchanged(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_richtlijn(console, accounts, class_="handreiking", title="Herkomst fixture", version="2.1")
    freeze_before = Path(receipt["binary_path"]).read_bytes()
    identity = _source_identity(receipt)
    changed = console.promote_class(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        new_class="richtlijn",
    )
    assert _source_identity(changed) == identity
    assert Path(changed["binary_path"]).read_bytes() == freeze_before
    assert changed["class"] == "richtlijn"
    assert changed["title"] == "Herkomst fixture"
    assert changed["version"] == "2.1"


def test_g2_still_blocks_publish_after_klasse_wijzigen(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_richtlijn(console, accounts, class_="artikel")
    console.promote_class(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        new_class="handreiking",
    )
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert considered["publish_allowed"] is False
    assert considered["g2"] == "BLOCKED"
    published = console.publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert published["status"] == "BLOCKED"
    assert published["g2"] == "BLOCKED"
    assert published["cutover"] is False
