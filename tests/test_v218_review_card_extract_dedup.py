"""Acceptance tests for Protocol v2.18 review card once and extract dedup.

Open card shows the freeze sentence once (not h3/title AND body). Extract
MUST NOT split trailing grammatical continuations into new objects. Extract
MUST NOT emit identical clean_text twice from one freeze. Unpublished
Continentie MAY be re-extracted on the same SHA-256; hiding fragments
without that extract is forbidden. v2.17 chrome/slogan/bronpassage-prose
still holds. Tests hit the real functions.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.answerability_gate_v1 import evaluate_answerability
from src.atomic_split_v1 import fusion_is_forbidden, split_meaning_units
from src.extract_html_v1 import extract as extract_html
from src.integrity_kernel import sha256_bytes
from src.object_taxonomy_v1 import (
    is_advice_weight,
    is_continuation_fragment,
    is_kennisplatform_chrome_text,
    published_object_type,
    recommendation_strength_ui_applies,
)
from src.open_original_v1 import researcher_visible_prose
from src.operations_console_app import create_console_app
from src.operations_console_v1 import (
    ConsoleError,
    OperationsConsole,
    remaining_unclassified,
    review_card_sentence,
    review_row_title,
    safe_store_filename,
)


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
APP_SOURCE = ROOT / "src/operations_console_app.py"
SLOGAN = "Dit wordt wat een EPD MAG zeggen."
EVENTUEEL = "Eventueel met hulp van de mantelzorger."
OVERWEEG = (
    "Overweeg om bij ouderen met urine-incontinentie én een cognitieve "
    "beperking het advies te geven om op vaste tijden te gaan plassen."
)
FULL_RECOMMENDATION = f"{OVERWEEG} {EVENTUEEL}"
BIJVOORBEELD = "Bijvoorbeeld een toiletdagboek van drie dagen."
CHROME_LABELS = ("Tools", "Home", "Richtlijnen", "Meedenken")


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
    return re.sub(
        r"\s+",
        " ",
        ((obj.get("content") or {}).get("clean_text") or ""),
    ).strip()


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


def _pair_block(*, two_p: bool = False) -> str:
    if two_p:
        return f"<p>{OVERWEEG}</p>\n<p>{EVENTUEEL}</p>"
    return f"<p>{OVERWEEG} {EVENTUEEL}</p>"


def _snapshot_fail_html() -> bytes:
    """Reproduce snap-ac59cf24f946088e-6538b559: pair three times, plus naloopzinnen."""
    pair_one_p = _pair_block(two_p=False)
    pair_two_p = _pair_block(two_p=True)
    return f"""<!doctype html><html lang="nl"><body>
<nav class="bricks-nav-menu">
<ul>
<li class="menu-item bricks-menu-item"><a href="https://kennisplatform.venvn.nl/tools/">Tools</a></li>
<li class="menu-item"><a href="https://kennisplatform.venvn.nl/">Home</a></li>
</ul>
</nav>
<main>
<h1>Richtlijn Continentie</h1>
<section class="samenvatting">
<h2>1.1 Inleiding</h2>
<p>Deze richtlijn gaat over continentiezorg in de wijkverpleging.</p>
{pair_one_p}
<p>Gebruik een toiletdagboek. {BIJVOORBEELD}</p>
</section>
<section class="module">
<h2>2. Inleiding</h2>
<p>Deze module herhaalt de samenvatting niet als extra kennis wanneer de zin identiek is.</p>
{pair_two_p}
<h2>Uitgangsvraag 3a - Niet-medicamenteuze interventies bij urine-incontinentie</h2>
{pair_one_p}
</section>
</main>
</body></html>
""".encode("utf-8")


def _chrome_freeze() -> bytes:
    return """<!doctype html><html lang="nl"><body>
<nav class="bricks-nav-menu">
<ul>
<li class="menu-item bricks-menu-item"><a href="https://kennisplatform.venvn.nl/tools/">Tools</a></li>
<li class="menu-item"><a href="https://kennisplatform.venvn.nl/">Home</a></li>
<li class="menu-item"><a href="https://kennisplatform.venvn.nl/richtlijnen/">Richtlijnen</a></li>
<li class="menu-item"><a href="https://kennisplatform.venvn.nl/meedenken/">Meedenken</a></li>
</ul>
</nav>
<main>
<h1>Richtlijn Continentie</h1>
<h2>Inleiding</h2>
<p>Deze richtlijn gaat over continentiezorg in de wijkverpleging.</p>
</main>
</body></html>
""".encode("utf-8")


def _object_column(html: str) -> str:
    card = re.search(
        r'<article class="object review-card-two-column".*?</article>',
        html,
        flags=re.S,
    )
    assert card, "open review card must exist"
    block = card.group(0)
    object_idx = block.find("review-card-object")
    passage_idx = block.find("review-card-bronpassage")
    assert object_idx >= 0
    assert passage_idx > object_idx
    return block[object_idx:passage_idx]


def _bronpassage_column(html: str) -> str:
    card = re.search(
        r'<article class="object review-card-two-column".*?</article>',
        html,
        flags=re.S,
    )
    assert card, "open review card must exist"
    block = card.group(0)
    passage_idx = block.find("review-card-bronpassage")
    assert passage_idx >= 0
    return block[passage_idx:]


def _h3_text(column_html: str) -> str:
    match = re.search(r"<h3>(.*?)</h3>", column_html, flags=re.S)
    assert match, "open card must have an h3"
    return _visible_text(match.group(1)).strip()


def _object_text_body(column_html: str) -> str:
    match = re.search(
        r'<div class="object-text">\s*<p>(.*?)</p>\s*</div>',
        column_html,
        flags=re.S,
    )
    if not match:
        return ""
    return _visible_text(match.group(1)).strip()


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
# 1. Review card shows the freeze sentence once (screenshot fail)
# ---------------------------------------------------------------------------


def test_review_card_shows_freeze_sentence_once_not_h3_and_body(tmp_path: Path) -> None:
    freeze = _snapshot_fail_html()
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=freeze, filename="continentie.html", title="Continentie"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    rec = next(obj for obj in objects if OVERWEEG in _text_of(obj))
    html = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}"
    ).text
    left = _object_column(html)
    heading = _h3_text(left)
    body = _object_text_body(left)
    assert EVENTUEEL in heading or EVENTUEEL in _text_of(rec)
    assert heading != ""
    assert body == "" or re.sub(r"\s+", " ", body) != re.sub(r"\s+", " ", heading)
    assert left.count(EVENTUEEL) == 1
    assert left.count(OVERWEEG) == 1
    assert "status" in left
    assert "wacht" in left or "geclassificeerd" in left or "bevestigd" in left
    assert review_card_sentence(rec) == _text_of(rec)
    assert review_row_title(rec) in _text_of(rec) or review_row_title(rec).rstrip("…") in _text_of(rec)


def test_eventueel_clause_screenshot_fail_is_not_a_standalone_card(tmp_path: Path) -> None:
    freeze = _snapshot_fail_html()
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=freeze, filename="continentie.html", title="Continentie"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    lone = [obj for obj in objects if _text_of(obj) == EVENTUEEL]
    assert lone == []
    rec = next(obj for obj in objects if FULL_RECOMMENDATION == _text_of(obj) or (
        OVERWEEG in _text_of(obj) and EVENTUEEL in _text_of(obj)
    ))
    html = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}"
    ).text
    left = _object_column(html)
    right = _bronpassage_column(html)
    assert _h3_text(left) != EVENTUEEL or _object_text_body(left) != EVENTUEEL
    assert _object_text_body(left) != EVENTUEEL or _h3_text(left) != EVENTUEEL
    assert not (
        _h3_text(left) == EVENTUEEL and _object_text_body(left) == EVENTUEEL
    )
    prose = _visible_text(right)
    assert OVERWEEG in prose
    assert EVENTUEEL in prose
    assert "brxe-" not in right
    assert "&lt;p&gt;" not in right
    assert "class=" not in _visible_text(right)


# ---------------------------------------------------------------------------
# 2. Extract MUST NOT split trailing grammatical continuations
# ---------------------------------------------------------------------------


def test_extract_does_not_split_trailing_eventueel_or_bijvoorbeeld(tmp_path: Path) -> None:
    assert is_continuation_fragment(EVENTUEEL) is True
    assert is_continuation_fragment(BIJVOORBEELD) is True
    assert is_continuation_fragment("Zoals bij een vaste plasroutine.") is True
    assert is_continuation_fragment("problemen.") is True
    assert is_continuation_fragment(OVERWEEG) is False
    assert is_continuation_fragment("Verwijs naar de huisarts.") is False
    fused_same_p = f"{OVERWEEG} {EVENTUEEL}"
    units = split_meaning_units(fused_same_p)
    assert units == [fused_same_p]
    example_units = split_meaning_units(
        f"Gebruik een toiletdagboek. {BIJVOORBEELD}"
    )
    assert len(example_units) == 1
    assert BIJVOORBEELD in example_units[0]
    freeze = _snapshot_fail_html()
    html_path = tmp_path / "continentie.html"
    html_path.write_bytes(freeze)
    fragments = extract_html(
        html_path, document_id="doc-continentie", source_id="src-continentie"
    )
    fragment_texts = [row["clean_text"] for row in fragments]
    assert EVENTUEEL in fragment_texts or any(EVENTUEEL in text for text in fragment_texts)
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=freeze, filename="continentie.html", title="Continentie"
    )
    texts = [_text_of(obj) for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))]
    assert EVENTUEEL not in texts
    assert BIJVOORBEELD not in texts
    assert any(OVERWEEG in text and EVENTUEEL in text for text in texts)
    assert any("toiletdagboek" in text and "Bijvoorbeeld" in text for text in texts)
    fused_exception = (
        "Verwijs de cliënt naar de huisarts. "
        "Tenzij samen met de cliënt hiervan wordt afgezien."
    )
    assert fusion_is_forbidden(fused_exception) is True
    assert len(split_meaning_units(fused_exception)) == 2


# ---------------------------------------------------------------------------
# 3. Extract MUST NOT emit identical clean_text twice; distinct headings MAY
# ---------------------------------------------------------------------------


def test_extract_does_not_emit_identical_clean_text_from_one_freeze(tmp_path: Path) -> None:
    freeze = _snapshot_fail_html()
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=freeze, filename="continentie.html", title="Continentie"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    texts = [_text_of(obj) for obj in objects]
    counts: dict[str, int] = {}
    for text in texts:
        counts[text] = counts.get(text, 0) + 1
    duplicates = {text: count for text, count in counts.items() if count > 1}
    assert duplicates == {}
    overweeg_objects = [text for text in texts if OVERWEEG in text and EVENTUEEL in text]
    assert len(overweeg_objects) == 1
    assert "1.1 Inleiding" in texts
    assert "2. Inleiding" in texts
    assert texts.count("1.1 Inleiding") == 1
    assert texts.count("2. Inleiding") == 1


def test_overweeg_recommendation_is_one_object_not_truncated_clause_plus_duplicates(
    tmp_path: Path,
) -> None:
    freeze = _snapshot_fail_html()
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=freeze, filename="continentie.html", title="Continentie"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    texts = [_text_of(obj) for obj in objects]
    assert texts.count(EVENTUEEL) == 0
    assert texts.count(OVERWEEG) == 0
    matches = [text for text in texts if OVERWEEG in text]
    assert len(matches) == 1
    assert EVENTUEEL in matches[0]
    rec = next(obj for obj in objects if OVERWEEG in _text_of(obj))
    html = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}"
    ).text
    left = _object_column(html)
    right = _visible_text(_bronpassage_column(html))
    assert _h3_text(left).count(EVENTUEEL) == 1
    assert _object_text_body(left) == "" or EVENTUEEL not in _object_text_body(left)
    assert OVERWEEG in right and EVENTUEEL in right


# ---------------------------------------------------------------------------
# 4. Unpublished Continentie re-extract; hiding fragments forbidden
# ---------------------------------------------------------------------------


def test_unpublished_continentie_reextract_on_same_sha256_allowed(tmp_path: Path) -> None:
    freeze = _snapshot_fail_html()
    expected = sha256_bytes(freeze)
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=freeze, filename="continentie.html", title="Continentie"
    )
    assert receipt["sha256"] == expected
    again = console.reextract_unpublished(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert again["sha256"] == expected
    after = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    after_ids = {obj["object_id"] for obj in after}
    assert after_ids
    texts = [_text_of(obj) for obj in after]
    assert EVENTUEEL not in texts
    assert any(OVERWEEG in text and EVENTUEEL in text for text in texts)
    assert after_ids
    fixture = HTML_FIXTURE.read_bytes()
    fixture_receipt = _ingest(
        console,
        accounts,
        data=fixture,
        filename="fixture.html",
        title="Fixture",
        family="continentie-fixture",
    )
    replaced = console.reextract_unpublished(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=fixture_receipt["snapshot_id"],
    )
    assert replaced["sha256"] == fixture_receipt["sha256"] == sha256_bytes(fixture)


def test_hiding_fragments_without_extract_is_forbidden(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_snapshot_fail_html(), filename="continentie.html", title="Continentie"
    )
    planted_text = EVENTUEEL
    rows = console._load_objects(receipt["snapshot_id"])
    seed = next(row for row in rows if row.get("object_type") != "document")
    planted = {
        **seed,
        "object_id": f"{seed['object_id']}-planted-eventueel",
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
    assert planted["object_id"] not in {
        obj["object_id"]
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    }


def test_reextract_refuses_published_objects(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_snapshot_fail_html(), filename="continentie.html", title="Continentie"
    )
    rows = console._load_objects(receipt["snapshot_id"])
    rows[0]["governance"]["publication_status"] = "published"
    console._save_objects(receipt["snapshot_id"], rows)
    with pytest.raises(ConsoleError, match="published_objects_must_not_be_rewritten"):
        console.reextract_unpublished(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
        )


# ---------------------------------------------------------------------------
# 5. v2.17 chrome / slogan / bronpassage-prose still holds
# ---------------------------------------------------------------------------


def test_v217_chrome_slogan_bronpassage_prose_still_holds(tmp_path: Path) -> None:
    freeze = _snapshot_fail_html()
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=freeze, filename="continentie.html", title="Continentie"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    texts = [_text_of(obj) for obj in objects]
    for label in CHROME_LABELS:
        assert label not in texts
        assert all(label.casefold() != text.casefold() for text in texts)
    source = APP_SOURCE.read_text(encoding="utf-8")
    assert SLOGAN not in source
    html = _client(console, "researcher.anne").get(
        f"/review?document={receipt['snapshot_id']}"
    ).text
    assert SLOGAN not in html
    assert "wat een EPD MAG zeggen" not in html
    assert "envelope" not in html.lower()
    assert "Documentenhiërarchie" in html
    rec = next(obj for obj in objects if OVERWEEG in _text_of(obj))
    card = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}"
    ).text
    assert "Sterkte van de aanbeveling" not in card or recommendation_strength_ui_applies(rec)
    if rec.get("proposed_object_type") != "recommendation" and rec.get("object_type") != "recommendation":
        assert "data-stamp-block" not in card
    right = _bronpassage_column(card)
    assert "brxe-" not in right
    assert "&lt;p&gt;" not in right
    assert "&lt;div" not in right
    prose = researcher_visible_prose(
        console.open_source_passage(
            snapshot_id=receipt["snapshot_id"], object_id=rec["object_id"]
        )["passage"]
    )
    assert "<" not in prose
    assert "class=" not in prose
    assert is_kennisplatform_chrome_text("Tools") is True
    chrome = _ingest(
        console,
        accounts,
        data=_chrome_freeze(),
        filename="chrome.html",
        title="Chrome",
        family="continentie-chrome",
    )
    chrome_texts = [
        _text_of(obj)
        for obj in _non_document(console.snapshot_objects(chrome["snapshot_id"]))
    ]
    assert "Tools" not in chrome_texts
    assert "Home" not in chrome_texts


# ---------------------------------------------------------------------------
# 6. Serving fail-closed; G2 still blocks publish
# ---------------------------------------------------------------------------


def test_serving_still_fail_closed_only_confirmed_recommendation_mag() -> None:
    heading = _record(
        object_id="h1",
        object_type="heading",
        text="1.1 Inleiding",
        confirmed="heading",
    )
    clause = _record(
        object_id="c1",
        object_type="unclassified",
        text=EVENTUEEL,
    )
    unclassified = _record(
        object_id="u1",
        object_type="unclassified",
        text=FULL_RECOMMENDATION,
        proposed="recommendation",
    )
    confirmed_rec = _record(
        object_id="r1",
        object_type="recommendation",
        text="Bespreek het onderwerp met de zorgvrager.",
        confirmed="recommendation",
    )
    for blocked in (heading, clause, unclassified):
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
    receipt = _ingest(
        console, accounts, data=_snapshot_fail_html(), filename="continentie.html", title="Continentie"
    )
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
# 7. Freeze store paths remain confined (CodeQL / commit 2cc34c1)
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
def test_v218_ingest_filename_cannot_escape_source_store(
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


def test_v218_safe_filename_still_accepts_plain_basenames() -> None:
    assert safe_store_filename("continentie.html") == "continentie.html"
    assert safe_store_filename("richtlijn-v2.html") == "richtlijn-v2.html"
