"""Console review completeness and honest serving (v2.13 already approved).

Wire existing kernel functions. Do not invent relation types or object types.
Unconfirmed relations MUST NOT bind. published_object_type serves only a
confirmed closed type. Product API GET knowledge fail-closed without locator
or with unclassified/historical type.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.object_taxonomy_v1 import published_object_type
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.product_api_v1 import ProductPaths, create_product_app
from src.product_security_v1 import TenantPolicy, TenantRegistry, hash_api_key
from src.published_projection_v1 import atomic_replace_projection
from src.four_eyes_v1 import requires_four_eyes
from src.serving_relations_v1 import binding_relations
from src.usage_ledger_v1 import UsageLedger


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


def _ingest_html(console: OperationsConsole, accounts: dict, data: bytes | None = None, **kwargs) -> dict:
    defaults = dict(
        actor_id=accounts["researcher"]["account_id"],
        filename="continentie.html",
        data=data if data is not None else HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Continentie fixture",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/continentie",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )
    defaults.update(kwargs)
    return console.ingest(**defaults)


def _record(
    *,
    object_id: str,
    object_type: str,
    text: str,
    confirmed: str | None = None,
    proposed: str | None = None,
    locator: dict | None = None,
    include_proposed_key: bool = True,
    published: bool = True,
) -> dict:
    loc = locator if locator is not None else {
        "locator_type": "web_line_range",
        "locator_value": "lines:4-4;p:1",
    }
    md = {
        "object_id": object_id,
        "object_version": "1.0",
        "document_id": "doc-1",
        "object_type": object_type,
        "source_locator": loc,
        "content_hash": "a" * 64,
        "topic": ["continentie", "class:richtlijn"],
    }
    if include_proposed_key:
        md["proposed_object_type"] = proposed
    if confirmed is not None:
        md["confirmed_object_type"] = confirmed
    if published:
        md["published_at"] = "2026-08-28T00:00:00Z"
        md["release_id"] = "proj-1"
        md["release_version"] = "1"
        md["source_title"] = "Fixture"
        md["source_version"] = "1.0"
    return {
        "metadata": md,
        "retrieval_id": f"{object_id}@1.0",
        "retrieval_text": text,
        "structured_logic": None,
        "projection_hash": "b" * 64,
        "confirmed_object_type": confirmed,
    }


def _product_client(tmp_path: Path, records_path: Path):
    key = "fixture-client-secret-key"
    registry = TenantRegistry(
        [
            TenantPolicy.from_dict(
                {
                    "tenant_id": "test-tenant",
                    "name": "Test Tenant",
                    "enabled": True,
                    "api_key_sha256": hash_api_key(key),
                    "scopes": ["retrieve", "knowledge:read"],
                    "allowed_document_ids": ["*"],
                    "allowed_topics": ["*"],
                    "requests_per_minute": 100,
                    "max_top_k": 5,
                }
            )
        ]
    )
    defaults = ProductPaths.defaults(ROOT)
    paths = ProductPaths(
        real_records=records_path,
        fixture_records=records_path,
        real_published=tmp_path / "published.jsonl",
        lexical_config=defaults.lexical_config,
        vector_config=defaults.vector_config,
        hybrid_config=defaults.hybrid_config,
        tenant_config=tmp_path / "unused.json",
        usage_db=tmp_path / "usage.sqlite",
    )
    app = create_product_app(
        "fixture",
        paths=paths,
        tenant_registry=registry,
        usage_ledger=UsageLedger(paths.usage_db),
        allow_fixture=True,
    )
    return TestClient(app), {"Authorization": f"Bearer {key}"}


def _strip_locator(console: OperationsConsole, snapshot_id: str, object_id: str) -> dict:
    rows = console._load_objects(snapshot_id)
    target = None
    for row in rows:
        if row["object_id"] != object_id:
            continue
        target = row
        provenance = row.setdefault("provenance", {})
        for frag in provenance.get("source_fragments") or []:
            frag.pop("source_locator", None)
        row.pop("source_locator", None)
    assert target is not None
    console._save_objects(snapshot_id, rows)
    return target


def _fused_html() -> bytes:
    return (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Voorbeeldrichtlijn</h1>"
        "<p>Bij een cliënt van 70 jaar of ouder. Verwijs naar de huisarts.</p>"
        "</body></html>"
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# 1. Relation confirm on the review card
# ---------------------------------------------------------------------------


def test_review_card_posts_relation_checkboxes_to_confirm_relations(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts, data=_fused_html(), filename="rel.html")
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    ]
    rec = next(obj for obj in objects if "Verwijs" in ((obj.get("content") or {}).get("clean_text") or ""))
    cond = next(obj for obj in objects if "70 jaar" in ((obj.get("content") or {}).get("clean_text") or ""))
    proposed = [
        row
        for row in (rec.get("relations") or [])
        if row.get("relation_type") == "applies_if" and row.get("target_object_id") == cond["object_id"]
    ]
    assert proposed
    assert binding_relations(rec) == []

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    html = client.get(f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}").text
    assert "nursing_tip" not in html
    assert "conditioned_by" not in html
    assert "Relatie bevestigen" not in html
    assert 'name="eindoordeel"' in html

    posted = client.post(
        "/review/relations",
        data={
            "snapshot_id": receipt["snapshot_id"],
            "object_id": rec["object_id"],
            "relation": [f"applies_if:{cond['object_id']}"],
        },
        follow_redirects=False,
    )
    assert posted.status_code in {303, 200}

    refreshed = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == rec["object_id"]
    )
    bound = binding_relations(refreshed)
    assert any(
        row["relation_type"] == "applies_if" and row["target_object_id"] == cond["object_id"]
        for row in bound
    )


def test_unconfirmed_relation_checkboxes_do_not_bind(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts, data=_fused_html(), filename="rel.html")
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    ]
    rec = next(obj for obj in objects if "Verwijs" in ((obj.get("content") or {}).get("clean_text") or ""))
    cond = next(obj for obj in objects if "70 jaar" in ((obj.get("content") or {}).get("clean_text") or ""))
    assert any(
        row.get("relation_type") == "applies_if" and row.get("target_object_id") == cond["object_id"]
        for row in (rec.get("relations") or [])
    )

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    client.post(
        "/review/relations",
        data={"snapshot_id": receipt["snapshot_id"], "object_id": rec["object_id"]},
        follow_redirects=False,
    )
    refreshed = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == rec["object_id"]
    )
    assert binding_relations(refreshed) == []
    assert refreshed.get("confirmed_relations") in (None, [])


# ---------------------------------------------------------------------------
# 2. Stop accidental heading confirm
# ---------------------------------------------------------------------------


def test_type_select_does_not_silently_submit_heading(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    heading = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] == "heading" and not obj.get("confirmed_object_type")
    )
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    html = client.get(f"/review?document={receipt['snapshot_id']}&object={heading['object_id']}").text
    assert 'disabled' in html
    assert "Metis stelt voor:" in html
    assert "Dit klopt" in html
    assert "Type wijzigen" in html
    type_block = html[html.find(f'id="type-{heading["object_id"]}"') : html.find(f'id="type-{heading["object_id"]}"') + 800]
    heading_option = next(
        line for line in type_block.split(">") if 'value="heading"' in line
    )
    assert "selected" in heading_option
    assert 'data-submit-review' in html


def test_approve_without_explicit_closed_type_fails(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    heading = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] == "heading" and not obj.get("confirmed_object_type")
    )
    with pytest.raises(ConsoleError, match="unknown_object_type|object_type_not_confirmed"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=heading["object_id"],
            decision="approve",
        )
    still = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == heading["object_id"]
    )
    assert still.get("confirmed_object_type") in (None, "")
    assert still["object_type"] == "heading"

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    posted = client.post(
        "/review",
        data={
            "snapshot_id": receipt["snapshot_id"],
            "object_id": heading["object_id"],
            "decision": "approve",
            "eindoordeel": "goedkeuren",
            "suitability": "ja",
            "confirmed_object_type": "",
        },
    )
    assert posted.status_code in {400, 403}
    still = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == heading["object_id"]
    )
    assert still.get("confirmed_object_type") in (None, "")


# ---------------------------------------------------------------------------
# 3. Bronpassage required before type confirm
# ---------------------------------------------------------------------------


def test_type_and_approve_disabled_when_open_source_passage_fails(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    _strip_locator(console, receipt["snapshot_id"], target["object_id"])
    with pytest.raises(ConsoleError):
        console.open_source_passage(snapshot_id=receipt["snapshot_id"], object_id=target["object_id"])

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    html = client.get(f"/review?document={receipt['snapshot_id']}&object={target['object_id']}").text
    type_block = html[html.find(f'id="type-{target["object_id"]}"') : html.find(f'id="decision-{target["object_id"]}"') + 800]
    assert "disabled" in type_block
    approve_line = next(line for line in html.split("<") if 'value="goedkeuren"' in line)
    assert "disabled" in approve_line
    assert 'value="goedkeuren_na_correctie"' in html
    assert 'value="afwijzen"' in html

    with pytest.raises(ConsoleError, match="open_original|source_locator"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=target["object_id"],
            decision="approve",
            confirmed_object_type="explanation",
        )
    with pytest.raises(ConsoleError, match="open_original|source_locator"):
        console.confirm_object_type(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=target["object_id"],
            confirmed_object_type="explanation",
        )


def test_type_confirm_succeeds_after_open_original(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] == "unclassified"
    )
    opened = console.open_source_passage(
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
    )
    assert opened["locator_type"] in {"web_line_range", "page_bbox"}
    assert opened["reserialized"] is False
    assert opened.get("passage")

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    html = client.get(f"/review?document={receipt['snapshot_id']}&object={target['object_id']}").text
    type_block = html[html.find(f'id="type-{target["object_id"]}"') : html.find(f'id="decision-{target["object_id"]}"')]
    assert "disabled" not in type_block or "Metis stelt voor" in html
    posted = client.post(
        "/review",
        data={
            "snapshot_id": receipt["snapshot_id"],
            "object_id": target["object_id"],
            "decision": "approve",
            "confirmed_object_type": "explanation",
            "suitability": "ja",
            "eindoordeel": "goedkeuren",
        },
        follow_redirects=False,
    )
    assert posted.status_code in {303, 200}
    refreshed = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == target["object_id"]
    )
    assert refreshed["confirmed_object_type"] == "explanation"


# ---------------------------------------------------------------------------
# 4. published_object_type leak closed
# ---------------------------------------------------------------------------


def test_published_object_type_serves_only_confirmed_closed_types() -> None:
    confirmed = _record(
        object_id="ok",
        object_type="recommendation",
        confirmed="recommendation",
        text="Verwijs naar de huisarts.",
    )
    assert published_object_type(confirmed) == "recommendation"

    published_shortcut = _record(
        object_id="leak-published",
        object_type="recommendation",
        confirmed=None,
        proposed="recommendation",
        text="Verwijs naar de huisarts.",
    )
    assert published_shortcut["metadata"].get("published_at")
    assert published_object_type(published_shortcut) == "unclassified"

    missing_keys = {
        "object_id": "leak-keys",
        "object_type": "recommendation",
        "content": {"clean_text": "Verwijs naar de huisarts."},
    }
    assert "confirmed_object_type" not in missing_keys
    assert "proposed_object_type" not in missing_keys
    assert published_object_type(missing_keys) == "unclassified"

    historical = _record(
        object_id="hist",
        object_type="score_rule",
        confirmed="score_rule",
        text="Leeftijd ≥ 60 jaar -> 1 punt",
    )
    assert published_object_type(historical) == "unclassified"

    unconfirmed = _record(
        object_id="u1",
        object_type="unclassified",
        confirmed=None,
        proposed="recommendation",
        text="Bespreek het onderwerp.",
    )
    assert published_object_type(unconfirmed) == "unclassified"

    invented = _record(
        object_id="inv",
        object_type="nursing_tip",
        confirmed="nursing_tip",
        text="Tip.",
    )
    assert published_object_type(invented) == "unclassified"
    body = (ROOT / "src/object_taxonomy_v1.py").read_text(encoding="utf-8")
    fn = body.split("def published_object_type", 1)[1].split("\ndef ", 1)[0]
    code = fn.split('"""', 2)[-1]
    assert "published_at" not in code
    assert 'if "confirmed_object_type" not in md' not in code


# ---------------------------------------------------------------------------
# 5. GET /v1/knowledge/{id} locator/type gate
# ---------------------------------------------------------------------------


def test_knowledge_get_abstains_without_locator_or_unclassified_or_historical(tmp_path: Path) -> None:
    ok = _record(
        object_id="ok-1",
        object_type="recommendation",
        confirmed="recommendation",
        text="Bespreek het onderwerp met de zorgvrager. Geadviseerd wordt een dagboek.",
    )
    missing = _record(
        object_id="no-loc",
        object_type="recommendation",
        confirmed="recommendation",
        text="Bespreek het onderwerp met de zorgvrager. Geadviseerd wordt een dagboek.",
        locator=None,
    )
    missing["metadata"]["source_locator"] = None
    unclassified = _record(
        object_id="u1",
        object_type="unclassified",
        confirmed=None,
        proposed="recommendation",
        text="Bespreek het onderwerp met de zorgvrager.",
    )
    historical = _record(
        object_id="score-1",
        object_type="score_rule",
        confirmed="score_rule",
        text="Leeftijd ≥ 60 jaar -> 1 punt",
    )
    path = tmp_path / "projection.jsonl"
    atomic_replace_projection(path, [ok, missing, unclassified, historical])
    client, headers = _product_client(tmp_path, path)

    served = client.get("/v1/knowledge/ok-1", headers=headers)
    assert served.status_code == 200
    served_body = served.json()
    assert served_body.get("status") != "abstain"
    assert served_body.get("knowledge_object_id") == "ok-1"
    assert served_body.get("content")

    def _blocked(object_id: str) -> tuple[int, dict]:
        response = client.get(f"/v1/knowledge/{object_id}", headers=headers)
        body = response.json()
        detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
        payload = detail or body
        assert response.status_code in {200, 404}
        if response.status_code == 200:
            assert payload.get("status") == "abstain" or payload.get("answerability") == "insufficient_evidence"
            assert not payload.get("content")
        assert payload.get("content") in (None, "", [])
        return response.status_code, payload

    no_loc_status, no_loc = _blocked("no-loc")
    assert no_loc_status in {200, 404}
    assert no_loc.get("reason") == "source_locator_missing" or "locator" in json.dumps(no_loc).lower()
    unclass_status, unclass = _blocked("u1")
    assert unclass_status in {200, 404}
    assert unclass.get("reason") in {"unclassified_object", "unconfirmed_proposal"} or "unclass" in json.dumps(unclass).lower()
    hist_status, hist = _blocked("score-1")
    assert hist_status == 404 or hist.get("reason") in {"historical_type_not_served", "unclassified_object"}


def test_four_eyes_copy_visible_when_required(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    html = (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Voorbeeldrichtlijn</h1>"
        "<p>Tenzij samen met de cliënt hiervan wordt afgezien.</p>"
        "</body></html>"
    ).encode("utf-8")
    receipt = _ingest_html(console, accounts, data=html, filename="exc.html")
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        confirmed_object_type="exception",
    )
    refreshed = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == target["object_id"]
    )
    assert requires_four_eyes(refreshed, confirmed_type="exception") is True
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    page = client.get(f"/review?document={receipt['snapshot_id']}&object={target['object_id']}").text
    assert "tweede reviewer nodig" in page
    assert "envelope" not in page.lower()


def test_accounts_can_change_roles_on_existing_user(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "publisher.carla", "password": "carla-secret"})
    page = client.get("/accounts").text
    assert "Rollen wijzigen" in page or "rollen wijzigen" in page.lower()
    posted = client.post(
        "/accounts/roles",
        data={
            "account_id": accounts["researcher"]["account_id"],
            "roles": ["researcher", "reviewer", "publisher"],
        },
        follow_redirects=False,
    )
    assert posted.status_code in {303, 200}
    changed = console._public_account(console._account(accounts["researcher"]["account_id"]))
    assert set(changed["roles"]) == {"researcher", "reviewer", "publisher"}
