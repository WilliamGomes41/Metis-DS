"""Acceptance tests for Protocol v2.15 implementation on the existing kernel.

Ingest source date/version, heading proposal, review-list snippets, and
type-routed review lanes. Tests are the specification. PROTOCOL.md and
docs/PROTOCOL_V2_* are not edited here.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.answerability_gate_v1 import evaluate_answerability
from src.four_eyes_v1 import requires_four_eyes
from src.integrity_kernel import compute_canonical_object_hash
from src.object_taxonomy_v1 import is_advice_weight, published_object_type
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"

# Locked hashes of the already-extracted Continentie factory fixture (main).
# New heading-proposal MUST NOT rewrite these objects.
CONTINENTIE_FIXTURE_HASHES = {
    "Continentie fixture": "1e49d3535085b5b080f466a4039c6ebfa89a1f9dc9887daac5bc2f7b86305418",
    "Voorbeeldrichtlijn bron 2": "26f8080b91a0897106a61e51304c6f41c09f99e8f5823f6b6efc7ea59a83087e",
    "Samenvatting": "ab2de26ba4aed4280e247b752cff528ba9a056ac1735f792f0932cf5f93c9faf",
    "Aanbevelingen": "b5438fb85fa84dc2515b175d8232a6b795e15e2e05ceb8be8cc11d377dbd3360",
    "Bespreek het onderwerp met de zorgvrager.": "6ced42da8c9831e117a5ea87728f7918e4c9661bd3f22a7a621fa9b342d7c21a",
    "Gebruik gedurende minimaal drie dagen een dagboek.": "98a79958782b8207350750c0f171ac9752b184bbf231ee9fe8fa8cb8934cecd4",
    "Doorverwijzen": "68945e9512e8f37edafcb4ab555bc361905968e0f575ea5161fa2b1ab0700c43",
    "Verwijs bij een alarmsignaal naar de bevoegde behandelaar.": "1b780fcd300d73911a35469d0e72f9474317b666a355729f3ceddd403325bbf3",
}

TYPE_NAMES = {
    "unclassified",
    "heading",
    "definition",
    "explanation",
    "condition",
    "exception",
    "recommendation",
    "document",
}


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


def _ingest(
    console: OperationsConsole,
    accounts: dict,
    *,
    data: bytes | None = None,
    filename: str = "continentie.html",
    **kwargs,
) -> dict:
    defaults = dict(
        actor_id=accounts["researcher"]["account_id"],
        filename=filename,
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


def _toc_html() -> bytes:
    return (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Richtlijn Continentie</h1>"
        "<nav><h2>Inhoudsopgave</h2>"
        "<ul>"
        "<li>1. Inleiding</li>"
        "<li>2. Diagnostiek</li>"
        "<li>3. Aanbevelingen</li>"
        "</ul></nav>"
        "<p>Continentie is een klinisch onderwerp in de ouderenzorg.</p>"
        "<p>Dit is gewone toelichtende tekst zonder kopmarkering.</p>"
        "</body></html>"
    ).encode("utf-8")


def _client(console: OperationsConsole, username: str = "reviewer.bert") -> TestClient:
    client = TestClient(create_console_app(console))
    password = "bert-secret" if username == "reviewer.bert" else "anne-secret"
    client.post("/login", data={"username": username, "password": password})
    return client


def _non_document(objects: list[dict]) -> list[dict]:
    return [obj for obj in objects if obj.get("object_type") != "document"]


def _text_of(obj: dict) -> str:
    return ((obj.get("content") or {}).get("clean_text") or "").strip()


def _index_link_titles(html: str) -> list[str]:
    titles = []
    for match in re.finditer(
        r'<a href="/review\?document=[^"]+&amp;object=[^"]+">\s*(.*?)\s*</a>',
        html,
        flags=re.S,
    ):
        titles.append(re.sub(r"<[^>]+>", "", match.group(1)).strip())
    return titles


def _record(
    *,
    object_id: str,
    object_type: str,
    text: str,
    confirmed: str | None = None,
    proposed: str | None = None,
) -> dict:
    md = {
        "object_id": object_id,
        "object_version": "1.0",
        "document_id": "doc-1",
        "object_type": object_type,
        "proposed_object_type": proposed,
        "confirmed_object_type": confirmed,
        "source_class": "richtlijn",
        "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:4-4;p:1"},
        "content_hash": "a" * 64,
        "topic": ["continentie", "class:richtlijn"],
        "published_at": "2026-08-28T00:00:00Z",
        "release_id": "proj-1",
        "release_version": "1",
        "source_title": "Fixture",
        "source_version": "1.0",
    }
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
                "object_id": row["metadata"]["object_id"],
                "object_version": row["metadata"]["object_version"],
            }
            for row in records
        ],
    }
    by_id = {row["metadata"]["object_id"]: row for row in records}
    return evaluate_answerability(query, raw, by_id)


# ---------------------------------------------------------------------------
# 1. Ingest page 1 — source date
# ---------------------------------------------------------------------------


def test_empty_source_date_is_rejected(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    with pytest.raises(ConsoleError, match="source_date_required"):
        _ingest(console, accounts, date="")
    with pytest.raises(ConsoleError, match="source_date_required"):
        _ingest(console, accounts, date="   ")


def test_source_date_does_not_default_to_today(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    today = date.today().isoformat()
    with pytest.raises(ConsoleError, match="source_date_required"):
        _ingest(console, accounts, date="")
    receipt = _ingest(console, accounts, date="2025-04-01")
    assert receipt["date"] == "2025-04-01"
    assert receipt["date"] != today
    assert receipt.get("acquired_at")
    dumped = json.dumps(receipt)
    if today != "2025-04-01":
        assert f'"date": "{today}"' not in dumped
    client = _client(console, "researcher.anne")
    html = client.get("/ingest").text
    date_tags = [
        tag
        for tag in re.findall(r"<input\b[^>]*>", html, flags=re.I)
        if re.search(r'name=["\']date["\']', tag, flags=re.I)
    ]
    assert date_tags
    for tag in date_tags:
        assert not re.search(r'value=["\'][^"\']+', tag)
        assert today not in tag


def test_source_date_stored_iso_not_dd_mm_yyyy(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, date="01-02-2026")
    assert receipt["date"] == "2026-02-01"
    assert "01-02-2026" not in json.dumps(receipt)
    for obj in console.snapshot_objects(receipt["snapshot_id"]):
        pub = (obj.get("source") or {}).get("publication_date")
        if pub:
            assert pub == "2026-02-01"
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", pub)
    iso = _ingest(console, accounts, title="ISO datum", date="2026-03-15")
    assert iso["date"] == "2026-03-15"
    assert "valid_from" not in iso
    assert "valid_until" not in iso
    for obj in console.snapshot_objects(iso["snapshot_id"]):
        assert obj.get("object_version") != "2026-03-15"
        assert "valid_from" not in obj
        assert "valid_until" not in (obj.get("source") or {})


def test_ingest_form_is_calendar_picker_nl_display(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console, "researcher.anne").get("/ingest").text
    assert 'lang="nl"' in html
    date_tags = [
        tag
        for tag in re.findall(r"<input\b[^>]*>", html, flags=re.I)
        if re.search(r'name=["\']date["\']', tag, flags=re.I)
    ]
    assert date_tags
    assert any(re.search(r'type=["\']date["\']', tag, flags=re.I) for tag in date_tags)
    lower = html.lower()
    assert "colofon" in lower or "publicatiedatum" in lower
    assert "dd-mm-yyyy" in lower or "dd-mm-jjjj" in lower
    assert "envelope" not in lower


# ---------------------------------------------------------------------------
# 2. Ingest page 1 — source version
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["1", "1.0", "2.13", "1.2.3"])
def test_source_version_accepts_dotted_integers(tmp_path: Path, version: str) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title=f"Versie {version}", version=version)
    assert receipt["version"] == version
    assert receipt.get("object_version") != version
    for obj in console.snapshot_objects(receipt["snapshot_id"]):
        assert (obj.get("source") or {}).get("version") == version
        assert obj.get("object_version") == "1.0"
        if version != "1.0":
            assert obj.get("object_version") != version


@pytest.mark.parametrize("version", ["", "v1", "2024", "1.", ".1", "1,2", "1-beta", "1-rc", " 1.0 ", "2.13 "])
def test_source_version_rejects_invalid(tmp_path: Path, version: str) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    with pytest.raises(ConsoleError, match="source_version_required|invalid_source_version"):
        _ingest(console, accounts, version=version)


def test_ingest_form_version_is_not_free_text(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console, "researcher.anne").get("/ingest").text
    version_tags = [
        tag
        for tag in re.findall(r"<input\b[^>]*>", html, flags=re.I)
        if re.search(r'name=["\']version["\']', tag, flags=re.I)
    ]
    assert version_tags
    assert any(re.search(r'pattern=', tag, flags=re.I) for tag in version_tags)


def test_source_date_and_version_are_freeze_metadata_not_publish(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, version="2.13", date="2025-04-01")
    assert receipt["state"] == "captured_not_published"
    published = console.publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert published["g2"] == "BLOCKED"
    assert published["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# 3. Extract MUST propose heading; ordinary text not auto-recommendation
# ---------------------------------------------------------------------------


def test_new_extract_proposes_heading_for_real_headings_and_toc(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_toc_html(), filename="toc.html", title="TOC richtlijn")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    by_text = {_text_of(obj): obj for obj in objects}
    assert "1. Inleiding" in by_text
    assert by_text["1. Inleiding"]["object_type"] == "heading"
    assert by_text["1. Inleiding"].get("proposed_object_type") == "heading"
    assert by_text["1. Inleiding"].get("confirmed_object_type") in {None, ""}
    assert "2. Diagnostiek" in by_text
    assert by_text["2. Diagnostiek"]["object_type"] == "heading"
    assert "Richtlijn Continentie" in by_text
    assert by_text["Richtlijn Continentie"]["object_type"] == "heading"
    assert "Inhoudsopgave" in by_text
    assert by_text["Inhoudsopgave"]["object_type"] == "heading"


def test_ordinary_text_is_not_auto_promoted_to_recommendation(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_toc_html(), filename="toc.html", title="TOC richtlijn")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    ordinary = next(obj for obj in objects if "gewone toelichtende tekst" in _text_of(obj))
    assert ordinary["object_type"] == "unclassified"
    assert ordinary.get("confirmed_object_type") in {None, ""}
    assert ordinary["object_type"] != "recommendation"
    clinical = next(obj for obj in objects if "klinisch onderwerp" in _text_of(obj))
    assert clinical["object_type"] != "recommendation"
    assert clinical.get("confirmed_object_type") in {None, ""}


def test_existing_continentie_fixture_hashes_unchanged(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    found = {_text_of(obj): compute_canonical_object_hash(obj) for obj in objects}
    assert found == CONTINENTIE_FIXTURE_HASHES
    paragraphs = [obj for obj in objects if obj["object_type"] == "unclassified"]
    assert any(_text_of(obj).startswith("Bespreek") for obj in paragraphs)
    assert all(obj["object_type"] != "recommendation" for obj in _non_document(objects))


# ---------------------------------------------------------------------------
# 4. Review list title is a source snippet, not the type name
# ---------------------------------------------------------------------------


def test_review_list_title_is_source_snippet_not_unclassified(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    titles = _index_link_titles(html)
    assert titles
    for title in titles:
        assert title.lower() not in TYPE_NAMES
        assert title != "unclassified"
        assert title != "Nog niet geclassificeerd"
    for obj in objects:
        snippet = _text_of(obj)
        assert any(snippet[:40] in title or title[:40] in snippet for title in titles)
    unclassified = [obj for obj in objects if obj["object_type"] == "unclassified"]
    assert unclassified
    unclassified_titles = [
        title
        for title in titles
        if any(_text_of(obj)[:40] in title for obj in unclassified)
    ]
    assert unclassified_titles
    assert len(set(unclassified_titles)) == len(unclassified_titles)


def test_four_thousand_identical_unclassified_titles_is_a_fail(tmp_path: Path) -> None:
    paragraphs = "".join(f"<p>Passage nummer {index} over continentie in de praktijk.</p>" for index in range(1, 13))
    html_src = f"<!doctype html><html lang=\"nl\"><body><h1>Richtlijn</h1>{paragraphs}</body></html>".encode(
        "utf-8"
    )
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=html_src, filename="many.html", title="Veel passages")
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    titles = _index_link_titles(html)
    assert "unclassified" not in {title.lower() for title in titles}
    passage_titles = [title for title in titles if "Passage nummer" in title]
    assert len(passage_titles) == 12
    assert len(set(passage_titles)) == 12


# ---------------------------------------------------------------------------
# 5. Two-speed review from type, no researcher speed toggle
# ---------------------------------------------------------------------------


def test_review_lanes_from_type_without_speed_toggle(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_toc_html(), filename="toc.html", title="TOC richtlijn")
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    lower = html.lower()
    assert "review-lane-fast" in html
    assert "review-lane-slow" in html
    assert "/review/headings/batch-confirm" in html
    assert "bevestig geselecteerde koppen als structuur" in lower
    for forbidden in ("zwaar", "licht", "snel/langzaam", "snel-langzaam", "speed-toggle"):
        assert forbidden not in lower
    assert "envelope" not in lower
    assert "Documentenhiërarchie" in html


def test_fast_lane_batch_confirms_headings_as_structure(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_toc_html(), filename="toc.html", title="TOC richtlijn")
    headings = [
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if obj["object_type"] == "heading"
    ]
    assert headings
    confirmed = console.batch_confirm_headings(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_ids=[obj["object_id"] for obj in headings],
    )
    assert confirmed
    refreshed = {
        obj["object_id"]: obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
    }
    for obj in headings:
        row = refreshed[obj["object_id"]]
        assert row["confirmed_object_type"] == "heading"
        assert row["object_type"] == "heading"
        assert (row.get("governance") or {}).get("validation_status") == "approved"


def test_slow_lane_stays_one_object_card(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_toc_html(), filename="toc.html", title="TOC richtlijn")
    slow = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if obj["object_type"] != "heading"
    )
    html = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={slow['object_id']}"
    ).text
    assert "review-card-two-column" in html
    assert "confirmed_object_type" in html
    assert "batch-confirm" not in html
    assert html.count('name="decision"') == 1


def test_batch_confirm_rejects_slow_lane_objects(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_toc_html(), filename="toc.html", title="TOC richtlijn")
    slow = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if obj["object_type"] != "heading"
    )
    with pytest.raises(ConsoleError, match="fast_lane_heading_required"):
        console.batch_confirm_headings(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_ids=[slow["object_id"]],
        )


def test_human_can_reclassify_heading_that_is_advice_to_slow(tmp_path: Path) -> None:
    html_src = (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Overweeg verwijzing naar de huisarts</h1>"
        "<p>Dit is gewone toelichtende tekst.</p>"
        "</body></html>"
    ).encode("utf-8")
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=html_src, filename="advice.html", title="Advieskop")
    heading = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if obj["object_type"] == "heading"
    )
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=heading["object_id"],
        confirmed_object_type="recommendation",
    )
    refreshed = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == heading["object_id"]
    )
    assert refreshed["confirmed_object_type"] == "recommendation"
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    assert heading["object_id"] in html
    assert "review-lane-slow" in html


# ---------------------------------------------------------------------------
# 6. Serving law unchanged
# ---------------------------------------------------------------------------


def test_heading_not_served_as_handelingsadvies() -> None:
    heading = _record(
        object_id="h1",
        object_type="heading",
        text="Aanbevelingen",
        confirmed="heading",
    )
    result = _eval("Wat adviseert deze richtlijn de zorgvrager?", [heading])
    assert result["answerability"] != "supported"
    assert result["behavior"] == "abstain"
    assert published_object_type(heading) == "heading"
    assert is_advice_weight("action_advice", "heading") is False


def test_unclassified_not_supported_only_confirmed_recommendation_may_be() -> None:
    unclassified = _record(
        object_id="u1",
        object_type="unclassified",
        text="Bespreek het onderwerp met de zorgvrager.",
        proposed="recommendation",
    )
    proposed_only = _record(
        object_id="p1",
        object_type="unclassified",
        text="Verwijs naar de huisarts.",
        proposed="recommendation",
    )
    confirmed_rec = _record(
        object_id="r1",
        object_type="recommendation",
        text="Bespreek het onderwerp met de zorgvrager. Geadviseerd wordt een gesprek.",
        confirmed="recommendation",
    )
    blocked = _eval("Wat adviseert deze richtlijn de zorgvrager?", [unclassified, proposed_only])
    assert blocked["answerability"] != "supported"
    assert blocked["results"] == []
    supported = _eval("Wat adviseert deze richtlijn de zorgvrager?", [confirmed_rec])
    assert supported["answerability"] == "supported"
    assert is_advice_weight("action_advice", "recommendation") is True
    assert is_advice_weight("action_advice", "unclassified") is False


# ---------------------------------------------------------------------------
# 7. Four-eyes unchanged; fast lane must not bypass
# ---------------------------------------------------------------------------


def test_four_eyes_still_required_for_exception_and_high_risk(tmp_path: Path) -> None:
    html_src = (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Voorbeeldrichtlijn</h1>"
        "<p>Tenzij samen met de cliënt hiervan wordt afgezien.</p>"
        "</body></html>"
    ).encode("utf-8")
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=html_src, filename="exc.html", title="Uitzondering")
    target = next(obj for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"])))
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
    console.review_object(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="exception",
    )
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert considered["publish_allowed"] is False
    assert considered["four_eyes_required"] is True
    assert "four_eyes_required" in considered["blockers"]


def test_fast_lane_heading_accept_does_not_bypass_four_eyes(tmp_path: Path) -> None:
    html_src = (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Uitzonderingen</h1>"
        "<p>Gewone toelichtende tekst.</p>"
        "</body></html>"
    ).encode("utf-8")
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=html_src, filename="risk.html", title="Risicokop")
    heading = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if obj["object_type"] == "heading"
    )
    rows = console._load_objects(receipt["snapshot_id"])
    for row in rows:
        if row["object_id"] == heading["object_id"]:
            row.setdefault("risk", {})["risk_level"] = "high"
            row["risk"]["risk_fields"] = ["exception"]
    console._save_objects(receipt["snapshot_id"], rows)
    console.batch_confirm_headings(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_ids=[heading["object_id"]],
    )
    refreshed = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == heading["object_id"]
    )
    assert refreshed["confirmed_object_type"] == "heading"
    assert requires_four_eyes(refreshed) is True
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert considered["publish_allowed"] is False
    assert considered["four_eyes_required"] is True
    assert "four_eyes_required" in considered["blockers"]


def test_reclassify_heading_onto_exception_still_needs_four_eyes(tmp_path: Path) -> None:
    html_src = (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Tenzij samen met de cliënt hiervan wordt afgezien</h1>"
        "</body></html>"
    ).encode("utf-8")
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=html_src, filename="reclass.html", title="Herclassificatie")
    heading = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if obj["object_type"] == "heading"
    )
    console.batch_confirm_headings(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_ids=[heading["object_id"]],
    )
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=heading["object_id"],
        confirmed_object_type="exception",
    )
    refreshed = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == heading["object_id"]
    )
    assert refreshed["confirmed_object_type"] == "exception"
    assert requires_four_eyes(refreshed, confirmed_type="exception") is True
