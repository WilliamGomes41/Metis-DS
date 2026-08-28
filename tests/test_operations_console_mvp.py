"""Acceptance tests for the Protocol v2.6/v2.8 internal operations console MVP.

Tests are the specification. They prove ingest, family tree, reviewer selection,
the review return-loop, local G0 identity, and fail-closed publication.
"""
from __future__ import annotations

import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.integrity_kernel import compute_canonical_object_hash, sha256_bytes, sha256_file
from src.operations_console_v1 import CLASS_ORDER, ConsoleError, OperationsConsole
from src.product_api_v1 import ProductPaths, create_product_app
from src.product_security_v1 import TenantPolicy, TenantRegistry, hash_api_key
from src.usage_ledger_v1 import UsageLedger


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
STORY_FIXTURE = ROOT / "data/fixtures/story_html_boom_player_fixture.html"
TENANTS = ROOT / "config/tenants.v1.json"


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
    engineer = console.create_account(
        username="engineer.dev",
        password="dev-secret",
        roles=(),
        display_name="Engineer",
    )
    return {
        "researcher": researcher,
        "reviewer": reviewer,
        "publisher": publisher,
        "engineer": engineer,
    }


def _ingest_html(console: OperationsConsole, accounts: dict, *, family: str = "continentie", class_: str = "richtlijn", title: str = "Continentie fixture", version: str = "1.0", extra: bytes | None = None) -> dict:
    data = extra if extra is not None else HTML_FIXTURE.read_bytes()
    return console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="continentie.html",
        data=data,
        content_type="text/html",
        ingest_kind="new",
        title=title,
        version=version,
        date="2025-04-01",
        live_url="https://example.test/continentie",
        class_=class_,
        family=family,
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )


def _tiny_pdf(tmp_path: Path, text: str = "Richtlijn test PDF") -> bytes:
    import fitz

    path = tmp_path / "generated.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path.read_bytes()


def _docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
        zf.writestr("word/document.xml", "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body><w:p><w:r><w:t>Word</w:t></w:r></w:p></w:body></w:document>")
    return buf.getvalue()


def test_html_and_pdf_ingest_accepted_word_and_story_html_rejected(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    html_receipt = _ingest_html(console, accounts)
    assert html_receipt["state"] == "captured_not_published"
    assert html_receipt["content_kind"] == "html"
    assert len(html_receipt["sha256"]) == 64

    pdf_receipt = console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="guideline.pdf",
        data=_tiny_pdf(tmp_path),
        content_type="application/pdf",
        ingest_kind="new",
        title="PDF fixture",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/pdf",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[accounts["reviewer"]["account_id"]],
    )
    assert pdf_receipt["content_kind"] == "pdf"
    assert pdf_receipt["state"] == "captured_not_published"

    with pytest.raises(ConsoleError, match="word_not_first_wave"):
        console.ingest(
            actor_id=accounts["researcher"]["account_id"],
            filename="living.docx",
            data=_docx_bytes(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ingest_kind="new",
            title="Word",
            version="1.0",
            date="2025-04-01",
            live_url="https://example.test/word",
            class_="richtlijn",
            family="continentie",
            named_reviewers=[accounts["reviewer"]["account_id"]],
        )

    with pytest.raises(ConsoleError, match="story_html_boom_player_out_of_first_wave"):
        console.ingest(
            actor_id=accounts["researcher"]["account_id"],
            filename="story.html",
            data=STORY_FIXTURE.read_bytes(),
            content_type="text/html",
            ingest_kind="new",
            title="Boom",
            version="1.0",
            date="2025-04-01",
            live_url="https://example.test/story",
            class_="richtlijn",
            family="continentie",
            named_reviewers=[accounts["reviewer"]["account_id"]],
        )


def test_url_ingest_snapshots_exact_bytes_immediately_with_receipt(tmp_path: Path) -> None:
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
        receipt = console.ingest(
            actor_id=accounts["researcher"]["account_id"],
            url=url,
            ingest_kind="new",
            title="URL snapshot",
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

    assert receipt["sha256"] == sha256_bytes(payload)
    assert receipt["locator"].startswith("g0-local:")
    assert receipt["state"] == "captured_not_published"
    assert receipt["immutable_storage_locator"] is None
    stored = Path(receipt["binary_path"]).read_bytes()
    assert stored == payload
    assert "sources/private" in receipt["binary_path"].replace("\\", "/")


def test_family_set_at_ingest_move_does_not_rehash_or_require_rereview(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts, family="continentie")
    sha_before = receipt["sha256"]
    objects_before = console.snapshot_objects(receipt["snapshot_id"])
    hashes_before = {row["object_id"]: compute_canonical_object_hash(row) for row in objects_before}

    moved = console.move_family(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        new_family="decubitus",
    )
    assert moved["family"] == "decubitus"
    assert moved["sha256"] == sha_before
    assert moved["clinical_rereview_required"] is False
    objects_after = console.snapshot_objects(receipt["snapshot_id"])
    hashes_after = {row["object_id"]: compute_canonical_object_hash(row) for row in objects_after}
    assert hashes_after == hashes_before

    tree = console.family_tree()
    assert "decubitus" in tree["families"]
    assert tree["families"]["decubitus"]["children"][0]["class"] == "richtlijn"
    assert tree["stable"] is True


def test_adding_a_branch_does_not_redraw_the_tree_and_siblings_are_not_parented(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    richtlijn = _ingest_html(console, accounts, family="continentie", class_="richtlijn", title="Richtlijn")
    podcast = console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="podcast-transcript.html",
        data=HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Podcast schaamte",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/podcast",
        class_="transcript",
        family="continentie",
        named_reviewers=[accounts["reviewer"]["account_id"]],
    )
    tree = console.family_tree()
    family = tree["families"]["continentie"]
    classes = sorted(child["class"] for child in family["children"])
    assert classes == ["richtlijn", "transcript"]
    assert family["children"][0]["parent"] == "continentie"
    assert family["children"][1]["parent"] == "continentie"
    assert richtlijn["snapshot_id"] != podcast["snapshot_id"]
    assert richtlijn["sha256"]  # each file keeps its own hash
    assert podcast["sha256"]
    # A richtlijn is not the parent of a podcast; they are siblings under the family hook.
    assert all(child["parent"] != richtlijn["snapshot_id"] for child in family["children"])


def test_class_promotion_requires_review(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts, class_="transcript")
    promoted = console.promote_class(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        new_class="richtlijn",
    )
    assert promoted["class"] == "richtlijn"
    assert promoted["sha256"] == receipt["sha256"]
    assert promoted["clinical_rereview_required"] is True
    objects = console.snapshot_objects(receipt["snapshot_id"])
    assert objects
    assert all(obj["governance"]["validation_status"] == "needs_review" for obj in objects)
    consider = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert consider["independence_satisfied"] is False


def test_uploader_cannot_be_the_sole_required_reviewer(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    with pytest.raises(ConsoleError, match="uploader_cannot_be_sole_required_reviewer"):
        console.ingest(
            actor_id=accounts["researcher"]["account_id"],
            filename="continentie.html",
            data=HTML_FIXTURE.read_bytes(),
            content_type="text/html",
            ingest_kind="new",
            title="Solo",
            version="1.0",
            date="2025-04-01",
            live_url="https://example.test/solo",
            class_="richtlijn",
            family="continentie",
            named_reviewers=[accounts["researcher"]["account_id"]],
        )

    receipt = _ingest_html(console, accounts)
    uploader = accounts["researcher"]["account_id"]
    objects = console.snapshot_objects(receipt["snapshot_id"])
    target = next(obj for obj in objects if obj["object_type"] != "document")
    console.review_object(
        actor_id=uploader,
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
    )
    consider = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert consider["independence_satisfied"] is False
    assert "second_named_reviewer_required" in consider["blockers"]

    other = accounts["reviewer"]["account_id"]
    refreshed = console.snapshot_objects(receipt["snapshot_id"])
    target = next(obj for obj in refreshed if obj["object_id"] == target["object_id"])
    console.review_object(
        actor_id=other,
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
    )
    consider_after = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert consider_after["independence_satisfied"] is True
    assert consider_after["publish_allowed"] is False
    assert "blocked_pending_immutable_locator" in consider_after["blockers"]


def test_reject_and_correction_create_new_object_version_not_silent_mutation(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    original = next(obj for obj in objects if obj["object_type"] != "document")
    original_hash = compute_canonical_object_hash(original)
    original_version = original["object_version"]
    original_json = json.dumps(original, sort_keys=True)

    rejected = console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=original["object_id"],
        decision="reject",
        comment="Onjuiste weergave van de bron.",
    )
    blocked = next(obj for obj in rejected if obj["object_id"] == original["object_id"] and obj["object_version"] == original_version)
    assert blocked["governance"]["validation_status"] == "rejected"
    assert json.dumps(original, sort_keys=True) == original_json

    other = next(obj for obj in console.snapshot_objects(receipt["snapshot_id"]) if obj["object_id"] != original["object_id"] and obj["object_type"] != "document")
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=other["object_id"],
        decision="revise",
        comment="Corrigeer de formulering.",
        proposed_correction="Bespreek het onderwerp expliciet met de zorgvrager.",
    )
    revised = console.correct_object(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=other["object_id"],
        patch={
            "reason": "reviewer correction",
            "operations": [{"op": "set", "path": "content.clean_text", "value": "Bespreek het onderwerp expliciet met de zorgvrager."}],
        },
    )
    assert revised["object_version"] != other["object_version"]
    assert revised["governance"]["validation_status"] == "needs_review"
    assert revised["governance"]["publication_status"] == "unpublished"
    still_old = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"], include_blocked=True)
        if obj["object_id"] == other["object_id"] and obj["object_version"] == other["object_version"]
    )
    assert still_old["content"]["clean_text"] == other["content"]["clean_text"]
    assert compute_canonical_object_hash(still_old) == compute_canonical_object_hash(other)
    with pytest.raises(ConsoleError, match="cannot_silently_mutate"):
        console.silently_edit_object(receipt["snapshot_id"], original["object_id"], {"content": {"clean_text": "mutated"}})
    assert compute_canonical_object_hash(original) == original_hash


def test_no_shared_login_and_role_authorization(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    with pytest.raises(ConsoleError, match="username_already_exists"):
        console.create_account(username="researcher.anne", password="other", roles=("reviewer",))
    with pytest.raises(ConsoleError, match="public_signup_forbidden"):
        console.public_signup(username="public.user", password="x", roles=("researcher",))

    researcher_session = console.authenticate("researcher.anne", "anne-secret")
    reviewer_session = console.authenticate("reviewer.bert", "bert-secret")
    publisher_session = console.authenticate("publisher.carla", "carla-secret")
    engineer_session = console.authenticate("engineer.dev", "dev-secret")
    assert researcher_session["account_id"] != reviewer_session["account_id"]
    assert "researcher" in researcher_session["roles"]
    assert "reviewer" in reviewer_session["roles"]
    assert "publisher" in publisher_session["roles"]

    with pytest.raises(ConsoleError, match="researcher_role_required"):
        console.ingest(
            actor_id=accounts["engineer"]["account_id"],
            filename="continentie.html",
            data=HTML_FIXTURE.read_bytes(),
            content_type="text/html",
            ingest_kind="new",
            title="Engineer path",
            version="1.0",
            date="2025-04-01",
            live_url="https://example.test/eng",
            class_="richtlijn",
            family="continentie",
            named_reviewers=[accounts["reviewer"]["account_id"]],
        )
    with pytest.raises(ConsoleError, match="researcher_role_required"):
        console.ingest(
            actor_id=accounts["reviewer"]["account_id"],
            filename="continentie.html",
            data=HTML_FIXTURE.read_bytes(),
            content_type="text/html",
            ingest_kind="new",
            title="Reviewer ingest",
            version="1.0",
            date="2025-04-01",
            live_url="https://example.test/rev",
            class_="richtlijn",
            family="continentie",
            named_reviewers=[accounts["reviewer"]["account_id"]],
        )
    receipt = _ingest_html(console, accounts)
    with pytest.raises(ConsoleError, match="reviewer_role_required"):
        console.review_object(
            actor_id=accounts["publisher"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=console.snapshot_objects(receipt["snapshot_id"])[0]["object_id"],
            decision="approve",
        )
    with pytest.raises(ConsoleError, match="publisher_role_required"):
        console.publish(actor_id=accounts["researcher"]["account_id"], snapshot_id=receipt["snapshot_id"])
    with pytest.raises(ConsoleError, match="forbidden_reviewer_identity"):
        console.ingest(
            actor_id=accounts["researcher"]["account_id"],
            filename="continentie.html",
            data=HTML_FIXTURE.read_bytes() + b"\n<!-- distinct -->\n",
            content_type="text/html",
            ingest_kind="new",
            title="Metis named",
            version="1.0",
            date="2025-04-01",
            live_url="https://example.test/metis",
            class_="richtlijn",
            family="continentie",
            named_reviewers=["Metis"],
        )
    assert engineer_session["roles"] == []


def test_publication_blocked_without_immutable_locator(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    assert receipt["immutable_storage_locator"] is None
    result = console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"])
    assert result["status"] == "BLOCKED"
    assert result["state"] == "captured_not_published"
    assert "blocked_pending_immutable_locator" in result["blockers"]
    assert result.get("g2") != "PASS"


def test_new_version_creates_snapshot_and_object_diff_without_faking_cutover(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    first = _ingest_html(console, accounts, version="1.0")
    updated_html = HTML_FIXTURE.read_text(encoding="utf-8").replace(
        "Bespreek het onderwerp met de zorgvrager.",
        "Bespreek het onderwerp altijd met de zorgvrager.",
    )
    second = console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="continentie-v2.html",
        data=updated_html.encode("utf-8"),
        content_type="text/html",
        ingest_kind="new_version",
        title="Continentie fixture",
        version="2.0",
        date="2026-01-01",
        live_url="https://example.test/continentie",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[accounts["reviewer"]["account_id"]],
        replaces_snapshot_id=first["snapshot_id"],
    )
    assert second["snapshot_id"] != first["snapshot_id"]
    assert second["sha256"] != first["sha256"]
    assert second["object_diff"]
    assert second["object_diff"]["changed"] or second["object_diff"]["added"]
    live = console.live_snapshot(family="continentie", class_="richtlijn")
    assert live["snapshot_id"] == first["snapshot_id"]
    cutover = console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=second["snapshot_id"])
    assert cutover["status"] == "BLOCKED"
    still_live = console.live_snapshot(family="continentie", class_="richtlijn")
    assert still_live["snapshot_id"] == first["snapshot_id"]


def test_heavier_class_must_not_be_filled_by_lighter_class(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    _ingest_html(console, accounts, class_="richtlijn", title="Richtlijn")
    console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="podcast.html",
        data=HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Podcast",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/podcast",
        class_="podcast",
        family="continentie",
        named_reviewers=[accounts["reviewer"]["account_id"]],
    )
    selected = console.select_for_question(family="continentie", asked_class="richtlijn")
    assert selected
    assert all(item["class"] == "richtlijn" for item in selected)
    assert all(item["class"] != "podcast" for item in selected)
    labelled = console.select_for_question(family="continentie", asked_class="podcast")
    assert labelled
    assert all(item["class"] == "podcast" for item in labelled)
    assert CLASS_ORDER["richtlijn"] > CLASS_ORDER["podcast"]


def test_source_binaries_not_committed_and_tenants_remain_empty() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "sources/private/" in gitignore
    assert "*.pdf" in gitignore
    tenants = json.loads(TENANTS.read_text(encoding="utf-8"))
    assert tenants["tenants"] == []
    tracked_hint = ROOT / "sources" / "private"
    if tracked_hint.exists():
        assert not any(tracked_hint.rglob("*")), "canonical source binaries must not live in Git"
    assert HTML_FIXTURE.is_relative_to(ROOT / "data/fixtures")
    assert b"Continentie bij (kwetsbare) ouderen" not in HTML_FIXTURE.read_bytes()


def test_product_api_still_object_level_retrieve_and_unpublished_abstain(tmp_path: Path) -> None:
    key = "fixture-client-secret-key"
    registry = TenantRegistry(
        [
            TenantPolicy.from_dict(
                {
                    "tenant_id": "test-tenant",
                    "name": "Test Tenant",
                    "enabled": True,
                    "api_key_sha256": hash_api_key(key),
                    "scopes": ["retrieve"],
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
        real_records=defaults.real_records,
        fixture_records=defaults.fixture_records,
        real_published=defaults.real_published,
        lexical_config=defaults.lexical_config,
        vector_config=defaults.vector_config,
        hybrid_config=defaults.hybrid_config,
        tenant_config=tmp_path / "unused.json",
        usage_db=tmp_path / "usage.sqlite",
    )
    real = TestClient(
        create_product_app(
            "real",
            paths=paths,
            tenant_registry=registry,
            usage_ledger=UsageLedger(paths.usage_db),
        )
    )
    data = real.post(
        "/v1/retrieve",
        headers={"Authorization": f"Bearer {key}"},
        json={"query": "continentie"},
    ).json()
    assert data["status"] == "abstain"
    assert data["results"] == []
    fixture = TestClient(
        create_product_app(
            "fixture",
            paths=paths,
            tenant_registry=registry,
            usage_ledger=UsageLedger(paths.usage_db),
            allow_fixture=True,
        )
    )
    supported = fixture.post(
        "/v1/retrieve",
        headers={"Authorization": f"Bearer {key}"},
        json={"query": "Welke score geldt vanaf 60 jaar bij fractuurrisico?"},
    ).json()
    assert supported["status"] == "retrieve"
    assert supported["results"][0]["knowledge_object_id"]
    assert "prose" not in supported
    assert "llm" not in json.dumps(supported).lower()


def test_console_is_not_nurse_care_chat_or_public_website(tmp_path: Path) -> None:
    from src.operations_console_app import create_console_app

    console = _console(tmp_path)
    _accounts(console)
    app = create_console_app(console)
    client = TestClient(app)
    page = client.get("/").text.lower()
    for forbidden in (
        "chatbot",
        "chatkamer",
        "zorgapp",
        "epd/ecd",
        "verpleegkundig beslissingsboom",
        "nurse decision",
        "publieke website",
        "sign up",
        "public signup",
    ):
        assert forbidden not in page
    assert "interne operations console" in page
    assert client.get("/v1/retrieve").status_code == 404
    login = client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"}, follow_redirects=False)
    assert login.status_code in {200, 302, 303}
    ingest_page = client.get("/ingest").text.lower()
    assert "chat is geen kamer" in ingest_page
    assert "interne operations console" in ingest_page
    assert "ingest" in ingest_page
    assert "review" in ingest_page


def test_continentie_researcher_path_is_the_console_mailbox(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts, family="continentie")
    path = console.researcher_path()
    assert path["surface"] == "operations_console"
    assert path["room"] == "ingest"
    assert path["first_envelope_family"] == "continentie"
    assert path["engineer_only_parallel_path"] is False
    assert receipt["family"] == "continentie"
    from src.operations_console_app import create_console_app

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    ingest_page = client.get("/ingest").text.lower()
    assert "continentie" in ingest_page
    assert "mailbox" in ingest_page or "ingest" in ingest_page
    assert "onderzoekerspad" in ingest_page
    assert "parallel ingestpad voor engineers" in ingest_page
