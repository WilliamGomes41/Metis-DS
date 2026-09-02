"""Acceptance tests for Protocol v2.16 Review page researcher bar.

One door Beoordeel, Koppen/Inhoud stacks, compact source-text rows,
DOEN/OVERWEEG/NIET DOEN stamps on recommendation, no tiny objects,
new extract of unpublished Continentie. Tests are the specification.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.answerability_gate_v1 import evaluate_answerability
from src.integrity_kernel import sha256_bytes
from src.object_taxonomy_v1 import (
    extract_object_type,
    is_advice_weight,
    is_list_number_only,
    is_strength_stamp,
    is_tiny_confirmable_text,
    published_object_type,
    recommendation_strength_sentence,
    stamp_value,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import (
    ConsoleError,
    OperationsConsole,
    review_lane,
    review_row_status,
    review_row_title,
    review_stacks,
)


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
CSS = ROOT / "assets/brand/console.css"
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


def _client(console: OperationsConsole, username: str = "reviewer.bert") -> TestClient:
    client = TestClient(create_console_app(console))
    passwords = {
        "reviewer.bert": "bert-secret",
        "researcher.anne": "anne-secret",
        "publisher.carla": "carla-secret",
    }
    client.post("/login", data={"username": username, "password": passwords[username]})
    return client


def _non_document(objects: list[dict]) -> list[dict]:
    return [obj for obj in objects if obj.get("object_type") != "document"]


def _text_of(obj: dict) -> str:
    return ((obj.get("content") or {}).get("clean_text") or "").strip()


class _VisibleTextParser(HTMLParser):
    """Visible page text without script/style payloads (avoids tag-filter regexes)."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    return " ".join(parser.parts)


def _index_link_titles(html: str) -> list[str]:
    titles = []
    for match in re.finditer(
        r'<a[^>]*href="/review\?document=[^"]+(?:&|&amp;)object=[^"]+"[^>]*>\s*(.*?)\s*</a>',
        html,
        flags=re.S,
    ):
        titles.append(_visible_text(match.group(1)).strip())
    return titles


def _stamp_html() -> bytes:
    return (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Richtlijn Continentie</h1>"
        "<h2>DOEN</h2>"
        "<p>Bespreek het onderwerp met de zorgvrager.</p>"
        "<h2>OVERWEEG</h2>"
        "<p>Gebruik gedurende minimaal drie dagen een dagboek.</p>"
        "<h2>NIET DOEN</h2>"
        "<p>Verwijs niet naar een onbevoegde behandelaar.</p>"
        "<h2>Overweeg verwijzing naar de huisarts</h2>"
        "<p>Dit is gewone toelichtende tekst.</p>"
        "</body></html>"
    ).encode("utf-8")


def _tiny_html() -> bytes:
    return (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Richtlijn Continentie</h1>"
        "<p>1.</p>"
        "<h2>DOEN</h2>"
        "<p>Hoelang de cliënt dit dagboek moet bijhouden hangt af van zijn specifieke</p>"
        "<p>problemen.</p>"
        "<p>Gemaakt op 31-08-2026 19:52:55</p>"
        "<p>Bespreek het onderwerp met de zorgvrager.</p>"
        "</body></html>"
    ).encode("utf-8")


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
# 1. One door Beoordeel
# ---------------------------------------------------------------------------


def test_beoordeel_is_the_single_door_openen_and_reviewen_are_gone(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    html = _client(console).get("/review").text
    assert re.search(r">\s*Beoordeel\s*<", html)
    assert f'/review?document={receipt["snapshot_id"]}' in html
    assert 'class="btn-primary"' in html
    assert re.search(
        rf'<a[^>]*class="[^"]*btn-primary[^"]*"[^>]*href="/review\?document={re.escape(receipt["snapshot_id"])}"',
        html,
    ) or re.search(
        rf'<a[^>]*href="/review\?document={re.escape(receipt["snapshot_id"])}"[^>]*class="[^"]*btn-primary',
        html,
    )
    assert not re.search(r">\s*Openen\s*<", html)
    assert not re.search(r">\s*Reviewen\s*<", html)
    assert "Openen" not in html
    assert "Reviewen" not in html
    assert html.lower().count("beoordeel") >= 1
    assert "envelope" not in html.lower()
    assert "Documentenhiërarchie" in html
    source = (ROOT / "src/operations_console_app.py").read_text(encoding="utf-8")
    assert ">Openen<" not in source
    assert ">Reviewen<" not in source
    assert "Beoordeel" in source


def test_first_review_screen_names_document_task_and_why(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    _ingest(console, accounts, title="Continentie fixture")
    html = _client(console).get("/review").text
    assert "Continentie fixture" in html
    assert "richtlijn" in html.lower()
    assert "continentie" in html.lower()
    assert "Beoordeel" in html
    assert "Dit wordt wat een EPD MAG zeggen." not in html
    assert "wat een EPD MAG zeggen" not in html
    first = _client(console).get("/review").text
    assert first.count('href="/review?document=') >= 1


# ---------------------------------------------------------------------------
# 2. Two named stacks with counts
# ---------------------------------------------------------------------------


def test_koppen_and_inhoud_stacks_show_counts(tmp_path: Path) -> None:
    html_src = (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Richtlijn Continentie</h1>"
        "<h2>Inleiding</h2>"
        "<p>Continentie is een klinisch onderwerp in de ouderenzorg.</p>"
        "<p>Dit is gewone toelichtende tekst zonder kopmarkering.</p>"
        "</body></html>"
    ).encode("utf-8")
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=html_src, filename="stacks.html", title="Stacks")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    koppen, inhoud = review_stacks(objects)
    assert koppen
    assert inhoud
    assert all(review_lane(obj) == "fast" for obj in koppen)
    assert all(review_lane(obj) == "slow" for obj in inhoud)
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    assert re.search(rf"Koppen[^<]*\({len(koppen)}\)", html)
    assert re.search(rf"Inhoud[^<]*\({len(inhoud)}\)", html)
    assert "Koppen" in html
    assert "Inhoud" in html
    assert "review-lane-fast" in html
    assert "review-lane-slow" in html
    assert "/review/headings/batch-confirm" in html
    lower = html.lower()
    for forbidden in ("zwaar/licht", "snel/langzaam", "speed-toggle", "envelope"):
        assert forbidden not in lower
    assert "Documentenhiërarchie" in html


# ---------------------------------------------------------------------------
# 3. Compact one-line rows
# ---------------------------------------------------------------------------


def test_compact_rows_are_source_text_plus_status_not_three_column(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    css = CSS.read_text(encoding="utf-8")
    titles = _index_link_titles(html)
    assert titles
    for title in titles:
        assert title.lower() not in TYPE_NAMES
        assert title != "unclassified"
        assert title != "Nog niet geclassificeerd"
        assert not title.startswith("console-")
        assert not title.startswith("snap-")
    for obj in objects:
        snippet = _text_of(obj)
        assert any(snippet[:40] in title or title[:40] in snippet for title in titles)
        assert review_row_title(obj) == snippet or review_row_title(obj).startswith(snippet[:40])
        assert review_row_title(obj) != obj["object_id"]
        assert review_row_status(obj) in {"wacht", "geclassificeerd", "bevestigd"}
    assert "review-row-status" in html
    assert re.search(r'class="review-row"', html)
    row_css = re.search(r"\.review-row\s*\{[^}]+\}", css)
    assert row_css
    assert "grid-template-columns" not in row_css.group(0)
    assert "display: grid" not in row_css.group(0)
    assert "display:grid" not in row_css.group(0).replace(" ", "")
    assert "flex" in row_css.group(0)
    assert ".object-index .object-id" not in css or "display: none" in css
    assert not re.search(
        r'<p class="meta">[^<]*(Nog niet geclassificeerd|Kop|Definitie)',
        html,
    )


def test_row_title_is_not_type_name_or_kernel_id() -> None:
    heading = {
        "object_id": "console-x-html-f0001",
        "object_type": "heading",
        "content": {"clean_text": "Aanbevelingen"},
        "governance": {"validation_status": "needs_review"},
    }
    empty = {
        "object_id": "console-x-html-f9999",
        "object_type": "unclassified",
        "content": {"clean_text": "unclassified"},
        "governance": {},
    }
    assert review_row_title(heading) == "Aanbevelingen"
    assert review_row_title(heading) != heading["object_id"]
    assert review_row_title(empty) != "unclassified"
    assert review_row_title(empty) != empty["object_id"]
    assert review_row_title(empty).lower() not in TYPE_NAMES


# ---------------------------------------------------------------------------
# 4. Stamps bind to recommendation only
# ---------------------------------------------------------------------------


def test_stamps_bind_to_recommendation_not_objects_or_koppen(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_stamp_html(), filename="stamps.html", title="Stempels")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    texts = {_text_of(obj): obj for obj in objects}
    assert "DOEN" not in texts
    assert "OVERWEEG" not in texts
    assert "NIET DOEN" not in texts
    assert all(not is_strength_stamp(_text_of(obj)) for obj in objects)
    koppen, inhoud = review_stacks(objects)
    assert all(not is_strength_stamp(_text_of(obj)) for obj in koppen)
    bespreek = texts["Bespreek het onderwerp met de zorgvrager."]
    dagboek = texts["Gebruik gedurende minimaal drie dagen een dagboek."]
    verwijs = texts["Verwijs niet naar een onbevoegde behandelaar."]
    assert bespreek.get("proposed_recommendation_strength") == "doen"
    assert dagboek.get("proposed_recommendation_strength") == "overweeg"
    assert verwijs.get("proposed_recommendation_strength") == "niet_doen"
    assert bespreek["object_type"] != "heading"
    advice_heading = next(obj for obj in objects if "Overweeg verwijzing" in _text_of(obj))
    assert advice_heading["object_type"] == "heading"
    assert advice_heading.get("proposed_recommendation_strength") in {None, ""}
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    assert "DOEN" not in _index_link_titles(html) or all(
        title not in {"DOEN", "OVERWEEG", "NIET DOEN"} for title in _index_link_titles(html)
    )
    assert all(title not in {"DOEN", "OVERWEEG", "NIET DOEN"} for title in _index_link_titles(html))
    slow = re.search(r'class="review-lane-slow".*?</section>', html, flags=re.S)
    assert slow
    card = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={bespreek['object_id']}"
    ).text
    assert "Sterkte van de aanbeveling: DOEN — dit moet de zorgverlener doen." in card
    assert "GRADE" not in card
    visible = _visible_text(card)
    assert not re.search(r"\b(weak|conditional)\b", visible, flags=re.I)
    assert "GRADE" not in visible
    assert stamp_value("DOEN") == "doen"
    assert stamp_value("NIET DOEN") == "niet_doen"
    assert recommendation_strength_sentence("doen") == (
        "Sterkte van de aanbeveling: DOEN — dit moet de zorgverlener doen."
    )


def test_human_confirms_strength_on_recommendation_not_heading(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_stamp_html(), filename="stamps.html", title="Stempels")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    rec = next(obj for obj in objects if _text_of(obj).startswith("Bespreek"))
    heading = next(obj for obj in objects if obj["object_type"] == "heading")
    confirmed = console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
        decision="approve",
        confirmed_object_type="recommendation",
        recommendation_strength="doen",
    )
    row = next(obj for obj in confirmed if obj["object_id"] == rec["object_id"])
    assert row["confirmed_object_type"] == "recommendation"
    assert row.get("confirmed_recommendation_strength") == "doen"
    with pytest.raises(ConsoleError, match="recommendation_strength_requires_recommendation"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=heading["object_id"],
            decision="approve",
            confirmed_object_type="heading",
            recommendation_strength="doen",
        )


# ---------------------------------------------------------------------------
# 5. Extract MUST NOT heading-propose stamps
# ---------------------------------------------------------------------------


def test_extract_does_not_propose_heading_for_stamps_even_if_tagged(tmp_path: Path) -> None:
    assert is_strength_stamp("DOEN") is True
    assert is_strength_stamp("OVERWEEG") is True
    assert is_strength_stamp("NIET DOEN") is True
    assert is_strength_stamp("Overweeg verwijzing naar de huisarts") is False
    fragment = {
        "clean_text": "DOEN",
        "raw_text": "DOEN",
        "heading": "DOEN",
        "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:4-4;h2:1"},
    }
    object_type, proposed = extract_object_type(fragment)
    assert object_type != "heading"
    assert proposed != "heading"
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_stamp_html(), filename="stamps.html", title="Stempels")
    headings = [
        _text_of(obj)
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if obj["object_type"] == "heading"
    ]
    assert "DOEN" not in headings
    assert "OVERWEEG" not in headings
    assert "NIET DOEN" not in headings
    assert "Overweeg verwijzing naar de huisarts" in headings


# ---------------------------------------------------------------------------
# 6. Extract MUST NOT emit tiny objects
# ---------------------------------------------------------------------------


def test_extract_does_not_emit_list_number_stamp_or_truncated_objects(tmp_path: Path) -> None:
    assert is_list_number_only("1.") is True
    assert is_list_number_only("1") is True
    assert is_tiny_confirmable_text("1.") is True
    assert is_tiny_confirmable_text("DOEN") is True
    assert is_tiny_confirmable_text("problemen.") is True
    assert is_tiny_confirmable_text("Gemaakt op 31-08-2026 19:52:55") is True
    assert is_tiny_confirmable_text("Bespreek het onderwerp met de zorgvrager.") is False
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_tiny_html(), filename="tiny.html", title="Tiny")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    texts = [_text_of(obj) for obj in objects]
    assert "1." not in texts
    assert "1" not in texts
    assert "DOEN" not in texts
    assert "problemen." not in texts
    assert "Gemaakt op 31-08-2026 19:52:55" not in texts
    merged = next(obj for obj in objects if "dagboek" in _text_of(obj))
    assert "specifieke problemen" in _text_of(merged)
    assert "Hoelang de cliënt" in _text_of(merged)
    assert any("Bespreek het onderwerp" in text for text in texts)
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    titles = _index_link_titles(html)
    assert "1." not in titles
    assert "problemen." not in titles
    assert all(title not in {"DOEN", "1.", "problemen."} for title in titles)


# ---------------------------------------------------------------------------
# 7. New extract of unpublished Continentie; do not hide fragments
# ---------------------------------------------------------------------------


def test_unpublished_continentie_new_extract_keeps_source_hash(tmp_path: Path) -> None:
    freeze = HTML_FIXTURE.read_bytes()
    expected = sha256_bytes(freeze)
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    assert receipt["sha256"] == expected
    assert receipt["state"] == "captured_not_published"
    again = console.reextract_unpublished(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert again["sha256"] == expected
    assert again["sha256"] == receipt["sha256"]
    objects = _non_document(console.snapshot_objects(again["snapshot_id"]))
    assert objects
    assert all(not is_tiny_confirmable_text(_text_of(obj)) for obj in objects)
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    for obj in objects:
        assert _text_of(obj)[:40] in html or obj["object_id"] in html


def test_ui_must_not_hide_stored_fragments_without_extract(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=_tiny_html(), filename="tiny.html", title="Tiny")
    freeze_hash = receipt["sha256"]
    assert freeze_hash == sha256_bytes(_tiny_html())
    planted_text = "1."
    rows = console._load_objects(receipt["snapshot_id"])
    seed = next(row for row in rows if row.get("object_type") != "document")
    planted = {
        **seed,
        "object_id": f"{seed['object_id']}-planted-tiny",
        "object_type": "unclassified",
        "proposed_object_type": None,
        "confirmed_object_type": None,
        "content": {
            **(seed.get("content") or {}),
            "raw_text": planted_text,
            "clean_text": planted_text,
        },
        "governance": {
            **(seed.get("governance") or {}),
            "publication_status": "unpublished",
            "validation_status": "needs_review",
        },
    }
    rows.append(planted)
    console._save_objects(receipt["snapshot_id"], rows)
    stored = [_text_of(obj) for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))]
    assert planted_text in stored
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    assert planted_text in html
    assert planted["object_id"] in html
    again = console.reextract_unpublished(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert again["sha256"] == freeze_hash
    after = [_text_of(obj) for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))]
    assert planted_text not in after
    html_after = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    titles = _index_link_titles(html_after)
    assert planted_text not in titles


def test_reextract_refuses_published_objects(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rows = console._load_objects(receipt["snapshot_id"])
    rows[0]["governance"]["publication_status"] = "published"
    console._save_objects(receipt["snapshot_id"], rows)
    with pytest.raises(ConsoleError, match="published_objects_must_not_be_rewritten"):
        console.reextract_unpublished(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
        )


# ---------------------------------------------------------------------------
# 8. Serving fail-closed; G2 still blocks publish
# ---------------------------------------------------------------------------


def test_serving_still_fail_closed_only_confirmed_recommendation_mag() -> None:
    heading = _record(
        object_id="h1",
        object_type="heading",
        text="Aanbevelingen",
        confirmed="heading",
    )
    stamp_only = _record(
        object_id="s1",
        object_type="unclassified",
        text="DOEN",
        proposed="heading",
    )
    unclassified = _record(
        object_id="u1",
        object_type="unclassified",
        text="Bespreek het onderwerp met de zorgvrager.",
        proposed="recommendation",
    )
    confirmed_rec = _record(
        object_id="r1",
        object_type="recommendation",
        text="Bespreek het onderwerp met de zorgvrager.",
        confirmed="recommendation",
    )
    for blocked in (heading, stamp_only, unclassified):
        result = _eval("Wat adviseert deze richtlijn de zorgvrager?", [blocked])
        assert result["answerability"] != "supported"
        assert result["behavior"] == "abstain"
    supported = _eval("Wat adviseert deze richtlijn de zorgvrager?", [confirmed_rec])
    assert supported["answerability"] == "supported"
    assert is_advice_weight("action_advice", "heading") is False
    assert is_advice_weight("action_advice", "recommendation") is True
    assert published_object_type(heading) == "heading"
    assert published_object_type(unclassified) == "unclassified"


def test_publish_remains_g2_blocked(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    published = console.publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert published["g2"] == "BLOCKED"
    assert published["status"] == "BLOCKED"
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert considered["publish_allowed"] is False
    assert considered["g2"] == "BLOCKED"
    html = _client(console, "publisher.carla").get("/publish").text
    assert "geblokkeerd" in html.lower() or "BLOCKED" in html
    assert "G2" in html or "geblokkeerd" in html.lower()
