"""Acceptance tests for the owner-authorized A+B+C implementation wave.

Protocol v2.12 (live): unclassified default, question×type answerability,
object-tuple review binding, atomic published projection.

Owner-approved v2.11 lock (not live baseline; implement in code): reject
live URL-HTML, accept uploaded freeze HTML, PDF URL with immediate exact-byte
hash, fail-closed supported without source_locator.

Protocol v2.10 (live, console follow-up): Documentenhiërarchie, waiting-task
badges, Accounts room with closed roles.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.answerability_gate_v1 import evaluate_answerability
from src.extract_html_v1 import extract as extract_html
from src.integrity_kernel import compute_canonical_object_hash, sha256_bytes
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.product_api_v1 import ProductPaths, create_product_app
from src.product_security_v1 import TenantPolicy, TenantRegistry, hash_api_key
from src.published_projection_v1 import PublishedProjection, atomic_replace_projection
from src.usage_ledger_v1 import UsageLedger


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
CLOSED_TYPES = (
    "heading",
    "definition",
    "explanation",
    "condition",
    "exception",
    "recommendation",
)
FORBIDDEN_IDENTITIES = (
    "AI",
    "Grok Bot",
    "Metis",
    "Implementation engineer",
    "Auditor",
)


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


def _ingest_html(console: OperationsConsole, accounts: dict, **kwargs) -> dict:
    defaults = dict(
        actor_id=accounts["researcher"]["account_id"],
        filename="continentie.html",
        data=HTML_FIXTURE.read_bytes(),
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


def _tiny_pdf(tmp_path: Path, text: str = "Richtlijn test PDF") -> bytes:
    import fitz

    path = tmp_path / "generated.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path.read_bytes()


def _non_document(objects: list[dict]) -> dict:
    return next(obj for obj in objects if obj["object_type"] != "document")


def _unclassified(objects: list[dict]) -> dict:
    return next(obj for obj in objects if obj["object_type"] == "unclassified")


def _heading(objects: list[dict]) -> dict:
    return next(obj for obj in objects if obj["object_type"] == "heading")


def _record(
    *,
    object_id: str,
    object_type: str,
    text: str,
    confirmed: str | None = None,
    proposed: str | None = None,
    locator: dict | None = None,
    source_class: str = "richtlijn",
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
        "proposed_object_type": proposed,
        "confirmed_object_type": confirmed,
        "source_class": source_class,
        "source_locator": loc,
        "content_hash": "a" * 64,
        "topic": ["continentie", f"class:{source_class}"],
    }
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
    }


def _eval(query: str, records: list[dict]) -> dict:
    raw = {
        "behavior": "retrieve",
        "results": [
            {
                "object_id": r["metadata"]["object_id"],
                "object_version": r["metadata"]["object_version"],
            }
            for r in records
        ],
    }
    by_id = {r["metadata"]["object_id"]: r for r in records}
    return evaluate_answerability(query, raw, by_id)


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


# ---------------------------------------------------------------------------
# A. v2.12 kernel
# ---------------------------------------------------------------------------


def test_a_non_heading_extract_defaults_unclassified_heading_may_be_heading(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    types = {obj["object_type"] for obj in objects}
    assert "unclassified" in types
    assert "heading" in types
    assert "recommendation" not in {
        obj["object_type"] for obj in objects if obj["object_type"] != "document"
    }
    paragraphs = [obj for obj in objects if obj["object_type"] == "unclassified"]
    headings = [obj for obj in objects if obj["object_type"] == "heading"]
    assert paragraphs
    assert headings
    assert all(obj.get("confirmed_object_type") in {None, ""} for obj in paragraphs)
    assert any(
        (obj.get("content") or {}).get("clean_text", "").startswith("Bespreek")
        for obj in paragraphs
    )
    assert any("Voorbeeldrichtlijn" in ((obj.get("content") or {}).get("clean_text") or "") for obj in headings)


def test_a_html_extract_structure_marks_headings_without_meaning() -> None:
    fragments = extract_html(
        HTML_FIXTURE,
        document_id="doc-html",
        source_id="src-html",
    )
    heading_frags = [row for row in fragments if ";h" in (row.get("source_locator") or {}).get("locator_value", "")]
    body_frags = [row for row in fragments if ";p:" in (row.get("source_locator") or {}).get("locator_value", "")]
    assert heading_frags
    assert body_frags


def test_a_unconfirmed_proposal_is_not_published_type(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    target = _unclassified(console.snapshot_objects(receipt["snapshot_id"]))
    assert target["object_type"] == "unclassified"
    proposed = target.get("proposed_object_type")
    if proposed:
        assert proposed in CLOSED_TYPES
        assert proposed != target["object_type"]
    assert not target.get("confirmed_object_type")
    assert target["object_type"] != "recommendation" or target.get("confirmed_object_type") == "recommendation"


def test_a_closed_type_set_rejects_invented_types(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    target = _unclassified(console.snapshot_objects(receipt["snapshot_id"]))
    with pytest.raises(ConsoleError, match="unknown_object_type"):
        console.confirm_object_type(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=target["object_id"],
            confirmed_object_type="nursing_tip",
        )
    with pytest.raises(ConsoleError, match="unknown_object_type"):
        console.confirm_object_type(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=target["object_id"],
            confirmed_object_type="unclassified",
        )


def test_a_unclassified_and_unconfirmed_are_not_supported() -> None:
    unclassified = _record(
        object_id="u1",
        object_type="unclassified",
        text="Bespreek het onderwerp met de zorgvrager.",
        confirmed=None,
        proposed="recommendation",
    )
    heading = _record(
        object_id="h1",
        object_type="heading",
        text="Aanbevelingen",
        confirmed="heading",
        locator={"locator_type": "web_line_range", "locator_value": "lines:3-3;h3:1"},
    )
    result = _eval("Wat adviseert deze richtlijn de zorgvrager?", [unclassified, heading])
    assert result["answerability"] != "supported"
    assert result["behavior"] == "abstain"
    assert result["results"] == []


def test_a_only_recommendation_is_action_advice_other_types_fit_without_advice_weight() -> None:
    rec = _record(
        object_id="r1",
        object_type="recommendation",
        confirmed="recommendation",
        text="Bespreek het onderwerp met de zorgvrager. Geadviseerd wordt een dagboek te gebruiken.",
    )
    definition = _record(
        object_id="d1",
        object_type="definition",
        confirmed="definition",
        text="Continentie is het vermogen urine of ontlasting op te houden.",
    )
    explanation = _record(
        object_id="e1",
        object_type="explanation",
        confirmed="explanation",
        text="Een dagboek helpt omdat het patroon van continentie zichtbaar wordt.",
    )
    condition = _record(
        object_id="c1",
        object_type="condition",
        confirmed="condition",
        text="Bij een cliënt met een alarmsignaal geldt deze voorwaarde.",
    )

    advice = _eval("Wat adviseert deze richtlijn de zorgvrager over een dagboek?", [rec, definition])
    assert advice["answerability"] == "supported"
    advice_ids = {row["object_id"] for row in advice["results"]}
    assert "r1" in advice_ids
    assert "d1" not in advice_ids
    assert advice.get("advice_weight") is True or any(
        row.get("advice_weight") is True for row in advice["results"]
    )
    assert all(
        row.get("advice_weight") is not True
        for row in advice["results"]
        if row["object_id"] != "r1"
    )
    assert {"V", "VN"}.issubset(set(advice.get("labels") or []))

    defined = _eval("Wat is continentie?", [definition, rec])
    assert defined["answerability"] == "supported"
    def_ids = {row["object_id"] for row in defined["results"]}
    assert "d1" in def_ids
    assert defined.get("advice_weight") is not True
    assert all(row.get("advice_weight") is not True for row in defined["results"])

    explained = _eval("Waarom helpt een dagboek bij continentie?", [explanation, rec])
    assert explained["answerability"] == "supported"
    assert "e1" in {row["object_id"] for row in explained["results"]}
    assert all(row.get("advice_weight") is not True for row in explained["results"])

    bounded_rec = dict(rec)
    bounded_rec["metadata"] = dict(rec["metadata"])
    bounded_rec["metadata"]["context_object_ids"] = ["c1"]
    bounded = _eval(
        "Wat adviseert deze richtlijn bij een alarmsignaal?",
        [bounded_rec, condition],
    )
    assert bounded["answerability"] == "supported"
    for row in bounded["results"]:
        if row["object_id"] == "c1":
            assert row.get("advice_weight") is not True


def test_a_heading_must_not_answer_as_advice_definition_or_explanation() -> None:
    heading = _record(
        object_id="h1",
        object_type="heading",
        confirmed="heading",
        text="Aanbevelingen over continentie en dagboek",
        locator={"locator_type": "web_line_range", "locator_value": "lines:3-3;h3:1"},
    )
    for query in (
        "Wat adviseert deze richtlijn over continentie?",
        "Wat is continentie?",
        "Waarom is continentie belangrijk?",
    ):
        result = _eval(query, [heading])
        assert result["answerability"] != "supported"
        assert result["results"] == []


def test_a_matching_type_on_lighter_class_must_not_fill_heavier_class() -> None:
    light = _record(
        object_id="pod-def",
        object_type="definition",
        confirmed="definition",
        text="Continentie is het vermogen urine of ontlasting op te houden.",
        source_class="podcast",
    )
    heavy_gap = _record(
        object_id="rl-other",
        object_type="recommendation",
        confirmed="recommendation",
        text="Bespreek schaamte met de zorgvrager.",
        source_class="richtlijn",
    )
    result = _eval("Wat is continentie?", [light, heavy_gap])
    ids = {row["object_id"] for row in result.get("results") or []}
    assert "pod-def" not in ids


def test_a_review_tuple_required_envelope_tick_insufficient(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    envelope = console._envelope(receipt["snapshot_id"])
    envelope["review_passes"][accounts["reviewer"]["account_id"]] = {
        "passed": True,
        "at": "2026-08-28T00:00:00Z",
        "object_id": "ignored",
    }
    console._save_envelopes()
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert considered["publish_allowed"] is False
    assert considered["g2"] == "BLOCKED"
    assert considered.get("tuple_authorization") is not True
    assert "object_tuple_required" in considered["blockers"] or considered["independence_satisfied"] is False

    target = _unclassified(console.snapshot_objects(receipt["snapshot_id"]))
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        confirmed_object_type="recommendation",
    )
    refreshed = next(
        obj for obj in console.snapshot_objects(receipt["snapshot_id"]) if obj["object_id"] == target["object_id"]
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="recommendation",
    )
    bindings = console.object_review_bindings(receipt["snapshot_id"])
    assert bindings
    row = next(item for item in bindings if item["object_id"] == target["object_id"])
    assert row["object_version"] == refreshed["object_version"]
    assert row["canonical_object_hash"] == compute_canonical_object_hash(
        next(obj for obj in console.snapshot_objects(receipt["snapshot_id"]) if obj["object_id"] == target["object_id"])
    )
    assert row["confirmed_object_type"] == "recommendation"
    assert row["reviewer"]
    assert row["decision"] == "approve"


def test_a_hash_version_or_type_change_invalidates_authorization(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    target = _unclassified(console.snapshot_objects(receipt["snapshot_id"]))
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        confirmed_object_type="recommendation",
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="recommendation",
    )
    assert console.object_review_bindings(receipt["snapshot_id"])

    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        confirmed_object_type="explanation",
    )
    bindings = console.object_review_bindings(receipt["snapshot_id"])
    assert not any(
        item["object_id"] == target["object_id"] and item.get("valid") is True
        for item in bindings
    )

    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="revise",
        comment="Nieuwe versie nodig.",
        confirmed_object_type="explanation",
    )
    revised = console.correct_object(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        patch={
            "reason": "reviewer correction",
            "operations": [
                {"op": "set", "path": "content.clean_text", "value": "Gecorrigeerde passage."}
            ],
        },
    )
    assert revised["object_version"] != target["object_version"]
    assert not revised.get("confirmed_object_type")
    bindings_after = console.object_review_bindings(receipt["snapshot_id"])
    assert not any(
        item["object_id"] == target["object_id"]
        and item.get("object_version") == revised["object_version"]
        and item.get("valid") is True
        for item in bindings_after
    )


def test_a_publish_stays_g2_blocked_even_with_tuple(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    target = _unclassified(console.snapshot_objects(receipt["snapshot_id"]))
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        confirmed_object_type="recommendation",
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="recommendation",
    )
    result = console.publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert result["status"] == "BLOCKED"
    assert result["g2"] == "BLOCKED"
    assert result.get("cutover") is False
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert considered["publish_allowed"] is False
    assert "blocked_pending_immutable_locator" in considered["blockers"]


def test_a_withdraw_atomically_removes_from_projection_no_live_governance_reconstruct(tmp_path: Path) -> None:
    rec = _record(
        object_id="keep-1",
        object_type="recommendation",
        confirmed="recommendation",
        text="Bespreek het onderwerp met de zorgvrager. Geadviseerd wordt een dagboek.",
    )
    gone = _record(
        object_id="gone-1",
        object_type="recommendation",
        confirmed="recommendation",
        text="Verwijs bij een alarmsignaal naar de bevoegde behandelaar.",
    )
    path = tmp_path / "projection.jsonl"
    atomic_replace_projection(path, [rec, gone])
    projection = PublishedProjection(path)
    projection.withdraw(["gone-1"])
    remaining = {row["metadata"]["object_id"] for row in projection.records()}
    assert remaining == {"keep-1"}
    assert "gone-1" not in remaining

    client, headers = _product_client(tmp_path, path)
    data = client.post(
        "/v1/retrieve",
        headers=headers,
        json={"query": "Wat adviseert deze richtlijn bij een alarmsignaal?"},
    ).json()
    ids = {row["knowledge_object_id"] for row in data.get("results") or []}
    assert "gone-1" not in ids
    if data.get("answerability") == "supported":
        assert "keep-1" in ids or data["results"]

    live_only = _record(
        object_id="live-gov",
        object_type="recommendation",
        confirmed="recommendation",
        text="Verwijs bij een alarmsignaal naar de bevoegde behandelaar.",
        published=False,
    )
    live_only["metadata"]["review_passes"] = True
    live_path = tmp_path / "empty-projection.jsonl"
    atomic_replace_projection(live_path, [])
    client2, headers2 = _product_client(tmp_path, live_path)
    reconstructed = client2.post(
        "/v1/retrieve",
        headers=headers2,
        json={"query": "Wat adviseert deze richtlijn bij een alarmsignaal?"},
    ).json()
    assert reconstructed["answerability"] != "supported"
    assert reconstructed["results"] == []
    assert reconstructed.get("status") == "abstain"


# ---------------------------------------------------------------------------
# B. v2.11 ingest lock in code
# ---------------------------------------------------------------------------


def test_b_live_url_html_ingest_rejected(tmp_path: Path) -> None:
    payload = HTML_FIXTURE.read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/continentie.html"
        console = _console(tmp_path)
        accounts = _accounts(console)
        with pytest.raises(ConsoleError, match="live_url_html_not_allowed"):
            console.ingest(
                actor_id=accounts["researcher"]["account_id"],
                url=url,
                ingest_kind="new",
                title="URL HTML",
                version="1.0",
                date="2025-04-01",
                live_url=url,
                class_="richtlijn",
                family="continentie",
                named_reviewers=[accounts["reviewer"]["account_id"]],
            )
    finally:
        server.shutdown()
        server.server_close()


def test_b_uploaded_html_freeze_accepted_exact_bytes(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    data = HTML_FIXTURE.read_bytes()
    receipt = _ingest_html(console, accounts, data=data)
    assert receipt["content_kind"] == "html"
    assert receipt["state"] == "captured_not_published"
    assert receipt["sha256"] == sha256_bytes(data)
    stored = Path(receipt["binary_path"]).read_bytes()
    assert stored == data
    objects = console.snapshot_objects(receipt["snapshot_id"])
    body = _unclassified(objects)
    locators = (body.get("provenance") or {}).get("source_fragments") or []
    assert locators
    assert locators[0]["source_locator"]["locator_type"] == "web_line_range"
    assert locators[0]["source_locator"]["locator_value"]


def test_b_pdf_url_accepted_only_with_immediate_exact_byte_hash(tmp_path: Path) -> None:
    payload = _tiny_pdf(tmp_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/guideline.pdf"
        console = _console(tmp_path)
        accounts = _accounts(console)
        receipt = console.ingest(
            actor_id=accounts["researcher"]["account_id"],
            url=url,
            ingest_kind="new",
            title="PDF via URL",
            version="1.0",
            date="2025-04-01",
            live_url=url,
            class_="richtlijn",
            family="continentie",
            named_reviewers=[accounts["reviewer"]["account_id"]],
        )
    finally:
        server.shutdown()
        server.server_close()

    assert receipt["content_kind"] == "pdf"
    assert receipt["sha256"] == sha256_bytes(payload)
    assert Path(receipt["binary_path"]).read_bytes() == payload
    body = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    locators = (body.get("provenance") or {}).get("source_fragments") or []
    assert locators
    assert locators[0]["source_locator"]["locator_type"] == "page_bbox"


def test_b_missing_or_empty_source_locator_is_not_supported(tmp_path: Path) -> None:
    missing = _record(
        object_id="no-loc",
        object_type="recommendation",
        confirmed="recommendation",
        text="Bespreek het onderwerp met de zorgvrager. Geadviseerd wordt een dagboek.",
        locator=None,
    )
    missing["metadata"]["source_locator"] = None
    empty = _record(
        object_id="empty-loc",
        object_type="recommendation",
        confirmed="recommendation",
        text="Bespreek het onderwerp met de zorgvrager. Geadviseerd wordt een dagboek.",
        locator={"locator_type": "web_line_range", "locator_value": ""},
    )
    for record in (missing, empty):
        result = _eval("Wat adviseert deze richtlijn de zorgvrager?", [record])
        assert result["answerability"] != "supported"
        assert result["behavior"] == "abstain"
        assert result["results"] == []
        assert result.get("reason") in {
            "source_locator_missing",
            "insufficient_evidence",
            "unpublished_or_unlocatable",
        }
        sentence = result.get("abstain_sentence") or ""
        assert sentence
        assert "llm" not in sentence.lower()

    path = tmp_path / "noloc.jsonl"
    atomic_replace_projection(path, [missing])
    client, headers = _product_client(tmp_path, path)
    data = client.post(
        "/v1/retrieve",
        headers=headers,
        json={"query": "Wat adviseert deze richtlijn de zorgvrager?"},
    ).json()
    assert data["answerability"] != "supported"
    assert data["results"] == []
    assert data.get("status") == "abstain"


# ---------------------------------------------------------------------------
# C. v2.10 console UX
# ---------------------------------------------------------------------------


def test_c_nav_heading_is_documentenhierarchie_not_familieboom(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    html = client.get("/tree").text
    assert "Documentenhiërarchie" in html
    assert "Documentenhierarchie" not in html
    assert "Familieboom" not in html
    nav = client.get("/ingest").text
    assert "Documentenhiërarchie" in nav
    assert "Documentenhierarchie" not in nav
    assert "Familieboom" not in nav


def test_c_badges_match_kernel_queues_and_hide_at_zero(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    empty = console.waiting_task_counts(accounts["reviewer"]["account_id"])
    assert empty["review"] == 0
    assert empty["publish"] == 0
    assert empty["ingest"] == 0
    assert empty["accounts"] == 0

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    html = client.get("/review").text
    assert 'class="badge"' not in html or "wachtende" not in html.lower()

    _ingest_html(console, accounts)
    review_counts = console.waiting_task_counts(accounts["reviewer"]["account_id"])
    assert review_counts["review"] >= 1
    publish_counts = console.waiting_task_counts(accounts["publisher"]["account_id"])
    assert publish_counts["publish"] >= 1
    account_counts = console.waiting_task_counts(accounts["publisher"]["account_id"])
    assert account_counts["accounts"] == 0

    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    review_html = client.get("/review").text
    assert 'class="badge"' in review_html
    assert str(review_counts["review"]) in review_html
    client.post("/login", data={"username": "publisher.carla", "password": "carla-secret"})
    publish_html = client.get("/publish").text
    assert str(publish_counts["publish"]) in publish_html
    assert "g2" not in publish_html.lower() or "geen g2" in publish_html.lower() or "niet" in publish_html.lower()
    accounts_html = client.get("/accounts").text
    assert "Accounts" in accounts_html
    nav = accounts_html[accounts_html.find("rooms") : accounts_html.find("</nav>")]
    assert "Accounts" in nav
    assert not (
        'href="/accounts"' in nav and 'class="badge"' in nav[nav.find("Accounts") : nav.find("Accounts") + 80]
    )


def test_c_publisher_creates_users_and_assigns_closed_roles_others_cannot(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    created = console.create_managed_account(
        actor_id=accounts["publisher"]["account_id"],
        username="researcher.dirk",
        display_name="Dirk Onderzoeker",
        password="dirk-secret",
        roles=("researcher",),
    )
    assert created["username"] == "researcher.dirk"
    assert created["roles"] == ["researcher"]
    assigned = console.assign_roles(
        actor_id=accounts["publisher"]["account_id"],
        account_id=created["account_id"],
        roles=("researcher", "reviewer"),
    )
    assert set(assigned["roles"]) == {"researcher", "reviewer"}
    with pytest.raises(ConsoleError, match="unknown_role"):
        console.assign_roles(
            actor_id=accounts["publisher"]["account_id"],
            account_id=created["account_id"],
            roles=("admin",),
        )
    with pytest.raises(ConsoleError, match="publisher_role_required"):
        console.create_managed_account(
            actor_id=accounts["researcher"]["account_id"],
            username="rogue",
            display_name="Rogue",
            password="secret",
            roles=("researcher",),
        )
    with pytest.raises(ConsoleError, match="publisher_role_required"):
        console.assign_roles(
            actor_id=accounts["reviewer"]["account_id"],
            account_id=created["account_id"],
            roles=("publisher",),
        )

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "publisher.carla", "password": "carla-secret"})
    page = client.get("/accounts").text
    assert "Accounts" in page
    assert "gebruikersnaam" in page.lower()
    assert "wachtwoord" in page.lower()
    created_html = client.post(
        "/accounts",
        data={
            "username": "researcher.eva",
            "display_name": "Eva Onderzoeker",
            "password": "eva-secret",
            "roles": "researcher",
        },
        follow_redirects=True,
    )
    assert created_html.status_code == 200
    assert "eva" in created_html.text.lower()

    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    forbidden = client.post(
        "/accounts",
        data={
            "username": "should.fail",
            "display_name": "Fail",
            "password": "secret",
            "roles": "researcher",
        },
    )
    assert forbidden.status_code in {400, 403}


def test_c_forbidden_identities_rejected_as_required_reviewers(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    for name in FORBIDDEN_IDENTITIES:
        with pytest.raises(ConsoleError, match="forbidden_reviewer_identity"):
            console.create_managed_account(
                actor_id=accounts["publisher"]["account_id"],
                username=name,
                display_name=name,
                password="secret",
                roles=("reviewer",),
            )


def test_c_no_envelope_or_snapshot_as_researcher_ui_terms(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    _ingest_html(console, accounts)
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "publisher.carla", "password": "carla-secret"})
    for path in ("/ingest", "/tree", "/review", "/publish", "/accounts"):
        html = client.get(path).text.lower()
        assert "envelope" not in html
        assert "snapshot-id" not in html
        assert "snapshot id" not in html
    source = (ROOT / "src/operations_console_app.py").read_text(encoding="utf-8")
    assert '"Familieboom"' not in source
    assert "Documentenhiërarchie" in source
    assert "Documentenhierarchie" not in source
