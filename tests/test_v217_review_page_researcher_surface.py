"""Acceptance tests for Protocol v2.17 Review page researcher surface.

No slogans, no HELP_ONCE via-negativa on researcher pages, empty Onderwerp,
readable bronpassage, no kennisplatform chrome objects, stamp UI only on
recommendation, adjacent relation checkboxes, whole-freeze rule, unpublished
Continentie re-extract. Tests hit the real functions.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.answerability_gate_v1 import evaluate_answerability
from src.extract_html_v1 import extract as extract_html
from src.extract_html_v1 import is_kennisplatform_chrome_element
from src.integrity_kernel import sha256_bytes
from src.object_taxonomy_v1 import (
    is_advice_weight,
    is_kennisplatform_chrome_text,
    published_object_type,
    recommendation_strength_ui_applies,
)
from src.open_original_v1 import (
    passage_from_html_freeze,
    researcher_visible_prose,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import (
    ConsoleError,
    OperationsConsole,
    remaining_unclassified,
    review_stacks,
    safe_store_filename,
)


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
CSS = ROOT / "assets/brand/console.css"
APP_SOURCE = ROOT / "src/operations_console_app.py"
SLOGAN = "Dit wordt wat een EPD MAG zeggen."
SLOGAN_LEAD = "Wat jij bevestigt, wordt wat een EPD MAG zeggen."
HELP_VIA_NEGATIVA = (
    "Interne operations console voor richtlijnonderzoekers",
    "Chat is geen kamer",
    "Niet ontworpen voor verpleegkundigen",
    "geen parallel ingestpad",
)
CHROME_LABELS = ("Tools", "Home", "Richtlijnen", "Meedenken")
DOELGROEP_SENTENCE = (
    "De richtlijn is bedoeld voor verzorgenden, verpleegkundigen en "
    "verpleegkundig specialisten werkzaam in de wijkzorg die zorg verlenen "
    "aan de kwetsbare thuiswonende oudere cliënt, met fecale- en/of "
    "urine-incontinentie."
)
DOELGROEP_TAG_SOUP = (
    '</h3><div class="brxe-faadvp brxe-text"><p>'
    + DOELGROEP_SENTENCE
    + "</p>"
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


def _chrome_freeze() -> bytes:
    return f"""<!doctype html><html lang="nl"><body>
<nav class="bricks-nav-menu">
<ul>
<li class="menu-item menu-item-type-post_type menu-item-object-page menu-item-17509 bricks-menu-item" data-static="true" data-toggle="click"><a href="https://kennisplatform.venvn.nl/tools/">Tools</a></li>
<li class="menu-item"><a href="https://kennisplatform.venvn.nl/">Home</a></li>
<li class="menu-item"><a href="https://kennisplatform.venvn.nl/richtlijnen/">Richtlijnen</a></li>
<li class="menu-item"><a href="https://kennisplatform.venvn.nl/meedenken/">Meedenken</a></li>
</ul>
</nav>
<footer><h2>Kennisinstituut V&amp;VN</h2><p>Veelgestelde vragen</p></footer>
<main>
<h1>Richtlijn Continentie</h1>
<h2>Inleiding</h2>
<p>Deze richtlijn gaat over continentiezorg in de wijkverpleging.</p>
<h2>Doel</h2>
<p>Het doel is eenduidige afspraken in de wijkzorg.</p>
<h2>Doelgroep</h2>
{DOELGROEP_TAG_SOUP}
<h2>Aanleiding</h2>
<p>Er was behoefte aan eenduidige afspraken over incontinentiezorg.</p>
<h2>Verantwoording</h2>
<p>De werkgroep heeft de literatuur beoordeeld voor deze richtlijn.</p>
</main>
</body></html>
""".encode("utf-8")


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
# 1. Researcher copy without slogans; no HELP_ONCE via-negativa
# ---------------------------------------------------------------------------


def test_slogan_sentence_absent_from_researcher_pages(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    client = _client(console, "researcher.anne")
    pages = [
        client.get("/ingest").text,
        client.get("/tree").text,
        client.get("/review").text,
        client.get(f"/review?document={receipt['snapshot_id']}").text,
    ]
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    target = objects[0]
    pages.append(
        client.get(
            f"/review?document={receipt['snapshot_id']}&object={target['object_id']}"
        ).text
    )
    source = APP_SOURCE.read_text(encoding="utf-8")
    assert SLOGAN not in source
    assert SLOGAN_LEAD not in source
    for html in pages:
        visible = _visible_text(html)
        assert SLOGAN not in html
        assert SLOGAN_LEAD not in html
        assert SLOGAN not in visible
        assert "wat een EPD MAG zeggen" not in html
        assert "wat een EPD MAG zeggen" not in visible
        assert "envelope" not in html.lower()
        assert "Documentenhiërarchie" in html
    review = client.get(f"/review?document={receipt['snapshot_id']}").text
    assert "Beoordeel Koppen als structuur en Inhoud als kennisobjecten." in review


def test_help_once_via_negativa_absent_from_researcher_pages(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    _ingest(console, accounts)
    client = _client(console, "researcher.anne")
    for path in ("/ingest", "/tree", "/review"):
        html = client.get(path).text
        assert "Over deze console" not in html
        for phrase in HELP_VIA_NEGATIVA:
            assert phrase not in html
            assert phrase.lower() not in _visible_text(html).lower()


# ---------------------------------------------------------------------------
# 2. Fresh ingest Onderwerp is empty
# ---------------------------------------------------------------------------


def test_fresh_ingest_onderwerp_is_empty_not_continentie(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console, "researcher.anne").get("/ingest").text
    assert 'id="family"' in html
    assert "Onderwerp" in html
    assert 'value="continentie"' not in html
    family = re.search(r'<input[^>]*id="family"[^>]*>', html)
    assert family
    assert "continentie" not in family.group(0).lower()
    assert "value=" not in family.group(0) or re.search(
        r'value="\s*"', family.group(0)
    )
    assert 'id="class_"' in html
    assert "richtlijn" in html
    source = APP_SOURCE.read_text(encoding="utf-8")
    assert 'value="continentie"' not in source


# ---------------------------------------------------------------------------
# 3. Bronpassage is readable prose; doelgroep tag-soup fails if tags leak
# ---------------------------------------------------------------------------


def test_researcher_visible_prose_strips_doelgroep_tag_soup() -> None:
    prose = researcher_visible_prose(DOELGROEP_TAG_SOUP)
    assert prose == DOELGROEP_SENTENCE
    assert "<" not in prose
    assert ">" not in prose
    assert "brxe-faadvp" not in prose
    assert "brxe-text" not in prose
    assert "class=" not in prose
    assert "</h3>" not in prose
    assert "<div" not in prose
    assert "<p>" not in prose


def test_bronpassage_for_objects_is_readable_text_not_tag_soup(tmp_path: Path) -> None:
    freeze = _chrome_freeze()
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=freeze, filename="chrome.html", title="Chrome")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    doelgroep = next(obj for obj in objects if DOELGROEP_SENTENCE in _text_of(obj))
    opened = console.open_source_passage(
        snapshot_id=receipt["snapshot_id"],
        object_id=doelgroep["object_id"],
    )
    raw = opened["passage"]
    assert opened["reserialized"] is False
    assert "brxe-faadvp" in raw or "<p>" in raw or "</h3>" in raw
    prose = researcher_visible_prose(raw)
    assert prose == DOELGROEP_SENTENCE or DOELGROEP_SENTENCE in prose
    assert "brxe-faadvp" not in prose
    assert "class=" not in prose
    html = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={doelgroep['object_id']}"
    ).text
    visible = _visible_text(html)
    assert DOELGROEP_SENTENCE in visible
    assert "brxe-faadvp" not in html
    assert "brxe-text" not in visible
    assert "&lt;div" not in html
    assert "&lt;/h3&gt;" not in html
    assert "&lt;p&gt;" not in html
    bronpassage = _client(console).get(
        f"/review/bronpassage?document={receipt['snapshot_id']}&object={doelgroep['object_id']}"
    ).text
    assert "brxe-faadvp" not in bronpassage
    assert DOELGROEP_SENTENCE in _visible_text(bronpassage)


def test_passage_from_html_freeze_stays_exact_bytes() -> None:
    freeze = (
        "<html><body>\n"
        f"{DOELGROEP_TAG_SOUP}\n"
        "</body></html>"
    ).encode("utf-8")
    raw = passage_from_html_freeze(freeze, "lines:2-2;p:1")
    assert "brxe-faadvp" in raw
    assert researcher_visible_prose(raw) == DOELGROEP_SENTENCE


# ---------------------------------------------------------------------------
# 4. Extract MUST NOT emit kennisplatform chrome
# ---------------------------------------------------------------------------


def test_extract_does_not_emit_kennisplatform_chrome_as_objects_or_koppen(
    tmp_path: Path,
) -> None:
    freeze = _chrome_freeze()
    html_path = tmp_path / "chrome.html"
    html_path.write_bytes(freeze)
    fragments = extract_html(
        html_path, document_id="doc-chrome", source_id="src-chrome"
    )
    fragment_texts = [row["clean_text"] for row in fragments]
    for label in CHROME_LABELS:
        assert label not in fragment_texts
    assert "Kennisinstituut V&VN" not in fragment_texts
    assert "Veelgestelde vragen" not in fragment_texts
    assert "Inleiding" in fragment_texts
    assert "Doel" in fragment_texts
    assert "Doelgroep" in fragment_texts
    assert "Aanleiding" in fragment_texts
    assert "Verantwoording" in fragment_texts
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=freeze, filename="chrome.html", title="Chrome")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    texts = [_text_of(obj) for obj in objects]
    for label in CHROME_LABELS:
        assert label not in texts
        assert all(label.casefold() != text.casefold() for text in texts)
    koppen, inhoud = review_stacks(objects)
    koppen_texts = [_text_of(obj) for obj in koppen]
    for label in CHROME_LABELS:
        assert label not in koppen_texts
    assert "Inleiding" in koppen_texts
    assert "Verantwoording" in koppen_texts
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    titles = _visible_text(html)
    for label in CHROME_LABELS:
        assert f">{label}<" not in html
    assert "Inleiding" in titles
    assert is_kennisplatform_chrome_text("Tools") is True
    assert is_kennisplatform_chrome_text("Home") is True
    assert is_kennisplatform_chrome_text("Inleiding") is False
    assert is_kennisplatform_chrome_element(
        "li",
        {
            "menu-item",
            "menu-item-type-post_type",
            "bricks-menu-item",
        },
    )
    assert is_kennisplatform_chrome_element("nav", {"bricks-nav-menu"})
    assert is_kennisplatform_chrome_element("nav", {"site-nav"})
    assert not is_kennisplatform_chrome_element("nav", set())
    assert not is_kennisplatform_chrome_element("h2", set())
    assert not is_kennisplatform_chrome_element("p", {"brxe-text"})


def test_one_word_chrome_tools_card_must_not_exist(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_chrome_freeze(), filename="chrome.html", title="Chrome"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    tools = [obj for obj in objects if _text_of(obj).casefold() == "tools"]
    assert tools == []
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    assert ">Tools<" not in html
    assert "kennisplatform.venvn.nl/tools" not in html


# ---------------------------------------------------------------------------
# 5. Recommendation-strength picker only on type recommendation
# ---------------------------------------------------------------------------


def test_recommendation_strength_picker_absent_unless_type_is_recommendation(
    tmp_path: Path,
) -> None:
    freeze = _chrome_freeze()
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=freeze, filename="chrome.html", title="Chrome")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    heading = next(obj for obj in objects if obj["object_type"] == "heading")
    body = next(
        obj
        for obj in objects
        if obj["object_type"] != "heading" and "Bespreek" not in _text_of(obj)
    )
    heading_page = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={heading['object_id']}"
    ).text
    body_page = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={body['object_id']}"
    ).text
    assert recommendation_strength_ui_applies(heading) is False
    if (body.get("proposed_object_type") or body.get("object_type")) != "recommendation":
        assert recommendation_strength_ui_applies(body) is False
        assert "Sterkte van de aanbeveling" not in heading_page
        assert "data-stamp-block" not in heading_page
        assert "Sterkte van de aanbeveling" not in body_page
        assert "data-stamp-block" not in body_page
    planted = {
        **body,
        "object_id": f"{body['object_id']}-tools-fail",
        "object_type": "unclassified",
        "proposed_object_type": None,
        "confirmed_object_type": None,
        "content": {**(body.get("content") or {}), "clean_text": "Tools", "raw_text": "Tools"},
    }
    assert recommendation_strength_ui_applies(planted) is False
    rows = console._load_objects(receipt["snapshot_id"])
    rows.append(planted)
    console._save_objects(receipt["snapshot_id"], rows)
    tools_card = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={planted['object_id']}"
    ).text
    assert "Sterkte van de aanbeveling" not in tools_card
    assert "data-stamp-block" not in tools_card
    assert "DOEN" not in _visible_text(tools_card) or "name=\"recommendation_strength\"" not in tools_card
    rec = {
        "object_type": "unclassified",
        "proposed_object_type": "recommendation",
        "confirmed_object_type": None,
    }
    assert recommendation_strength_ui_applies(rec) is True
    heading_type = {
        "object_type": "heading",
        "proposed_object_type": "heading",
        "confirmed_object_type": None,
    }
    assert recommendation_strength_ui_applies(heading_type) is False


# ---------------------------------------------------------------------------
# 6. Relation checkbox label adjacent, not stretched
# ---------------------------------------------------------------------------


def test_relation_checkbox_label_is_adjacent_not_stretched(tmp_path: Path) -> None:
    freeze = _chrome_freeze()
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=freeze, filename="chrome.html", title="Chrome")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    child = next(
        obj
        for obj in objects
        if any(
            rel.get("relation_type") == "child"
            for rel in (obj.get("relations") or [])
        )
    )
    html = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={child['object_id']}"
    ).text
    assert "Dit kennisobject is" in html
    assert "onderliggend" in html
    assert "Inleiding" in html
    assert 'class="check"' in html
    css = CSS.read_text(encoding="utf-8")
    relation_block = re.search(
        r"\.relations\s+\.check\s*\{[^}]+\}",
        css,
    )
    assert relation_block, "relation checkbox must have a compact rule"
    block = relation_block.group(0)
    assert "space-between" not in block
    assert "justify-content: space-between" not in css.split(".relations")[1].split(".help")[0]
    input_rule = re.search(
        r"\.relations\s+\.check\s+input\[type=\"checkbox\"\]\s*\{[^}]+\}",
        css,
    )
    assert input_rule
    assert "width: auto" in input_rule.group(0)
    assert re.search(
        r'input\[type="checkbox"\][^{]*\{[^}]*width:\s*auto',
        css,
        flags=re.S,
    )
    assert "justify-between" not in APP_SOURCE.read_text(encoding="utf-8")
    label = re.search(
        r'<label class="check">\s*<input type="checkbox"[^>]*>\s*<span>Inleiding</span>\s*</label>',
        html,
    )
    assert label, "Inleiding must sit in the same label as its checkbox"


# ---------------------------------------------------------------------------
# 7. Whole freeze, not a closed heading list
# ---------------------------------------------------------------------------


def test_whole_freeze_rule_is_not_a_closed_heading_list(tmp_path: Path) -> None:
    freeze = _chrome_freeze()
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=freeze, filename="chrome.html", title="Chrome")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    by_text = {_text_of(obj): obj for obj in objects}
    for title in ("Inleiding", "Doel", "Doelgroep", "Aanleiding", "Verantwoording"):
        assert title in by_text
        obj = by_text[title]
        page = _client(console).get(
            f"/review?document={receipt['snapshot_id']}&object={obj['object_id']}"
        ).text
        assert "brxe-faadvp" not in page
        assert "&lt;div" not in page
        if obj["object_type"] != "recommendation" and obj.get("proposed_object_type") != "recommendation":
            assert "data-stamp-block" not in page
    verantwoording = by_text["Verantwoording"]
    opened = console.open_source_passage(
        snapshot_id=receipt["snapshot_id"],
        object_id=verantwoording["object_id"],
    )
    prose = researcher_visible_prose(opened["passage"])
    assert "<" not in prose
    assert "Verantwoording" in prose or prose == "Verantwoording"
    source = APP_SOURCE.read_text(encoding="utf-8")
    assert not re.search(
        r"CLOSED_HEADING_SECTIONS\s*=\s*\{[^}]*inleiding[^}]*doelgroep",
        source,
        flags=re.I,
    )


# ---------------------------------------------------------------------------
# 8. Unpublished Continentie re-extract; hiding fragments forbidden
# ---------------------------------------------------------------------------


def test_unpublished_continentie_reextract_on_same_sha256_allowed(tmp_path: Path) -> None:
    freeze = HTML_FIXTURE.read_bytes()
    expected = sha256_bytes(freeze)
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    assert receipt["sha256"] == expected
    again = console.reextract_unpublished(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert again["sha256"] == expected
    chrome = _ingest(
        console,
        accounts,
        data=_chrome_freeze(),
        filename="chrome.html",
        title="Chrome later",
        family="continentie-chrome",
    )
    replaced = console.reextract_unpublished(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=chrome["snapshot_id"],
    )
    assert replaced["sha256"] == chrome["sha256"]
    texts = [
        _text_of(obj)
        for obj in _non_document(console.snapshot_objects(chrome["snapshot_id"]))
    ]
    assert "Tools" not in texts


def test_hiding_fragments_without_extract_is_forbidden(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_chrome_freeze(), filename="chrome.html", title="Chrome"
    )
    planted_text = "Tools"
    rows = console._load_objects(receipt["snapshot_id"])
    seed = next(row for row in rows if row.get("object_type") != "document")
    planted = {
        **seed,
        "object_id": f"{seed['object_id']}-planted-chrome",
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
    leftover = remaining_unclassified(
        _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    )
    assert any(obj["object_id"] == planted["object_id"] for obj in leftover)
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    assert f"Resterend unclassified: {len(leftover)}" in html
    card = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={planted['object_id']}"
    ).text
    assert planted_text in card
    again = console.reextract_unpublished(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert again["sha256"] == receipt["sha256"]
    after = [
        _text_of(obj)
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    ]
    assert planted_text not in after


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
# 9. Serving fail-closed; G2 still blocks publish
# ---------------------------------------------------------------------------


def test_serving_still_fail_closed_only_confirmed_recommendation_mag() -> None:
    heading = _record(
        object_id="h1",
        object_type="heading",
        text="Inleiding",
        confirmed="heading",
    )
    chrome = _record(
        object_id="t1",
        object_type="unclassified",
        text="Tools",
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
    for blocked in (heading, chrome, unclassified):
        result = _eval("Wat adviseert deze richtlijn de zorgvrager?", [blocked])
        assert result["answerability"] != "supported"
        assert result["behavior"] == "abstain"
    supported = _eval("Wat adviseert deze richtlijn de zorgvrager?", [confirmed_rec])
    assert supported["answerability"] == "supported"
    assert is_advice_weight("action_advice", "heading") is False
    assert is_advice_weight("action_advice", "recommendation") is True
    assert published_object_type(heading) == "heading"
    assert published_object_type(chrome) == "unclassified"


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


# ---------------------------------------------------------------------------
# 10. Freeze store paths remain confined (CodeQL / commit 2cc34c1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    [
        "../escape.html",
        "..\\escape.html",
        "foo/../../etc/passwd",
        "foo/bar.html",
        "..",
        ".",
        "/tmp/escape.html",
        "continentie/../escape.html",
    ],
)
def test_v217_ingest_filename_cannot_escape_source_store(
    tmp_path: Path, filename: str
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    store = (tmp_path / "sources" / "private").resolve()
    with pytest.raises(ConsoleError, match="invalid_store_path"):
        _ingest(console, accounts, filename=filename)
    assert list(tmp_path.rglob("escape.html")) == []
    assert list(tmp_path.rglob("passwd")) == []
    for path in store.rglob("*") if store.exists() else []:
        if path.is_file():
            path.resolve().relative_to(store)


def test_v217_safe_filename_still_accepts_plain_basenames() -> None:
    assert safe_store_filename("continentie.html") == "continentie.html"
    assert safe_store_filename("richtlijn-v2.html") == "richtlijn-v2.html"
