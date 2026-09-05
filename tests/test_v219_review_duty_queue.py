"""Acceptance tests for Protocol v2.19 review duty and queue presentation.

Researchers MUST NOT open thousands of Inhoud cards one by one (Koppen 78 /
Inhoud 2008 style fail). Koppen stay batch-confirmable as structure, never
as advice. Slow duty is proposed recommendation plus condition/exception/
any high-risk. Leftover unclassified is not equal one-by-one work and is
never served. Tests hit the real functions.
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
from src.four_eyes_v1 import requires_four_eyes
from src.integrity_kernel import sha256_bytes
from src.object_taxonomy_v1 import (
    is_advice_weight,
    is_continuation_fragment,
    is_kennisplatform_chrome_text,
    is_list_number_only,
    is_strength_stamp,
    is_tiny_confirmable_text,
    published_object_type,
    recommendation_strength_ui_applies,
)
from src.open_original_v1 import researcher_visible_prose
from src.operations_console_app import create_console_app
from src.operations_console_v1 import (
    ConsoleError,
    OperationsConsole,
    remaining_not_duty,
    remaining_unclassified,
    review_card_sentence,
    review_lane,
    review_stacks,
    safe_store_filename,
    slow_review_duty,
)


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
APP_SOURCE = ROOT / "src/operations_console_app.py"
CSS = ROOT / "assets/brand/console.css"
SLOGAN = "Dit wordt wat een EPD MAG zeggen."
KOPPEN_78 = 78
INHOUD_2008 = 2008
CHROME_LABELS = ("Tools", "Home", "Richtlijnen", "Meedenken")
EVENTUEEL = "Eventueel met hulp van de mantelzorger."
OVERWEEG = (
    "Overweeg om bij ouderen met urine-incontinentie én een cognitieve "
    "beperking het advies te geven om op vaste tijden te gaan plassen."
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


def _index_link_titles(html: str) -> list[str]:
    titles = []
    for match in re.finditer(
        r'<a[^>]*href="/review\?document=[^"]+(?:&|&amp;)object=[^"]+"[^>]*>\s*(.*?)\s*</a>',
        html,
        flags=re.S,
    ):
        titles.append(_visible_text(match.group(1)).strip())
    return titles


def _section(html: str, css_class: str) -> str:
    match = re.search(rf'class="{css_class}".*?</(?:section|aside)>', html, flags=re.S)
    return match.group(0) if match else ""


def _knowledge_obj(
    oid: str,
    otype: str,
    text: str,
    *,
    proposed: str | None = None,
    confirmed: str | None = None,
    risk_level: str | None = None,
    risk_fields: list[str] | None = None,
) -> dict:
    row: dict = {
        "object_id": oid,
        "object_type": otype,
        "proposed_object_type": proposed,
        "confirmed_object_type": confirmed,
        "content": {"clean_text": text, "raw_text": text},
        "governance": {"validation_status": "needs_review"},
    }
    if risk_level or risk_fields:
        row["risk"] = {
            "risk_level": risk_level or "standard",
            "risk_fields": list(risk_fields or []),
        }
    return row


def _koppen_78_inhoud_2008_style() -> list[dict]:
    """Live-fail shape: Koppen 78 / Inhoud 2008 leftover unclassified plus a small duty set."""
    objects = [
        _knowledge_obj("doc", "document", "Continentie"),
    ]
    for index in range(1, KOPPEN_78 + 1):
        objects.append(
            _knowledge_obj(
                f"h{index}",
                "heading",
                f"{index}. Kop {index}",
                proposed="heading",
            )
        )
    for index in range(1, INHOUD_2008 + 1):
        objects.append(
            _knowledge_obj(
                f"u{index}",
                "unclassified",
                f"Gewone toelichtende tekst nummer {index} zonder advieszin.",
            )
        )
    objects.append(
        _knowledge_obj(
            "r1",
            "unclassified",
            "Bespreek het onderwerp met de zorgvrager.",
            proposed="recommendation",
        )
    )
    objects.append(
        _knowledge_obj(
            "c1",
            "unclassified",
            "Wanneer de cliënt een alarmsignaal heeft.",
            proposed="condition",
        )
    )
    objects.append(
        _knowledge_obj(
            "e1",
            "unclassified",
            "Tenzij de huisarts al is ingeschakeld.",
            proposed="exception",
        )
    )
    objects.append(
        _knowledge_obj(
            "hr1",
            "unclassified",
            "Leeftijdsgrens volgt het protocol van de voorschrijver.",
            risk_level="high",
        )
    )
    return objects


def _duty_html(*, leftover: int = 40) -> bytes:
    parts = [
        "<!doctype html><html lang=\"nl\"><body>",
        "<h1>Richtlijn Continentie</h1>",
        "<h2>1. Inleiding</h2>",
        "<h2>2. Diagnostiek</h2>",
        "<h2>3. Aanbevelingen</h2>",
        "<p>Bespreek het onderwerp met de zorgvrager.</p>",
        "<p>Gebruik gedurende minimaal drie dagen een dagboek.</p>",
        "<p>Wanneer de cliënt een alarmsignaal heeft.</p>",
        "<p>Tenzij de huisarts al is ingeschakeld.</p>",
    ]
    for index in range(1, leftover + 1):
        parts.append(
            f"<p>Gewone toelichtende tekst nummer {index} zonder advieszin.</p>"
        )
    parts.append("</body></html>")
    return "".join(parts).encode("utf-8")


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
        "source_locator": {
            "locator_type": "web_line_range",
            "locator_value": "lines:4-4;p:1",
        },
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
# 1. Koppen 78 / Inhoud 2008 style fail: leftover is not one-by-one duty
# ---------------------------------------------------------------------------


def test_old_queue_would_require_2008_inhoud_cards_new_duty_does_not() -> None:
    objects = _koppen_78_inhoud_2008_style()
    koppen, old_inhoud = review_stacks(objects)
    duty = slow_review_duty(objects)
    leftover = remaining_unclassified(objects)
    assert len(koppen) == KOPPEN_78
    assert len(old_inhoud) == INHOUD_2008 + 4
    assert len(leftover) == INHOUD_2008
    assert len(duty) == 4
    assert len(duty) != len(old_inhoud)
    assert {obj["object_id"] for obj in duty} == {"r1", "c1", "e1", "hr1"}
    leftover_ids = {obj["object_id"] for obj in leftover}
    assert leftover_ids.isdisjoint({obj["object_id"] for obj in duty})
    assert leftover_ids.isdisjoint({obj["object_id"] for obj in koppen})


def test_researchers_are_not_required_to_open_thousands_of_inhoud_cards(
    tmp_path: Path,
) -> None:
    leftover_n = 40
    freeze = _duty_html(leftover=leftover_n)
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=freeze, filename="wachtrij.html", title="Wachtrij"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    koppen, old_inhoud = review_stacks(objects)
    duty = slow_review_duty(objects)
    leftover = remaining_unclassified(objects)
    assert koppen
    assert len(old_inhoud) >= leftover_n
    assert len(leftover) >= leftover_n
    assert len(duty) < leftover_n
    assert len(duty) >= 3
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    visible = _visible_text(html)
    assert re.search(rf"Koppen[^<]*\({len(koppen)}\)", html)
    assert re.search(rf"Inhoud[^<]*\({len(duty)}\)", html)
    assert f"Inhoud ({len(old_inhoud)})" not in html
    assert f"Inhoud ({len(leftover)})" not in html
    slow = _section(html, "review-lane-slow")
    duty_titles = _index_link_titles(slow)
    assert len(duty_titles) == len(duty)
    leftover_snips = [_text_of(obj)[:40] for obj in leftover]
    for snip in leftover_snips:
        assert not any(snip in title for title in duty_titles)
    assert f"Resterend unclassified: {len(leftover)}" in visible
    assert "niet als één-voor-één plicht" in visible.casefold()
    assert "unclassified wordt niet geserveerd" in visible.casefold()
    assert "Beoordeel elk kennisobject afzonderlijk." not in html
    for obj in leftover:
        assert obj in console.snapshot_objects(receipt["snapshot_id"])


def test_leftover_unclassified_stays_in_store_and_is_openable_not_duty(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_duty_html(leftover=8), filename="open.html", title="Open"
    )
    leftover = remaining_unclassified(
        _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    )
    planted = leftover[0]
    list_html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    slow = _section(list_html, "review-lane-slow")
    assert planted["object_id"] not in slow
    card = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={planted['object_id']}"
    ).text
    assert _text_of(planted) in _visible_text(card)
    assert "review-card-two-column" in card
    assert "batch-confirm" not in card


# ---------------------------------------------------------------------------
# 2. Koppen remain batch-confirmable as structure, never as advice
# ---------------------------------------------------------------------------


def test_koppen_remain_batch_confirmable_as_structure_never_advice(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_duty_html(leftover=5), filename="koppen.html", title="Koppen"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    koppen, _ = review_stacks(objects)
    assert koppen
    assert all(review_lane(obj) == "fast" for obj in koppen)
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    fast = _section(html, "review-lane-fast")
    assert "/review/headings/batch-confirm" in fast
    assert "Bevestig geselecteerde koppen als structuur" in fast
    assert "nooit als advies" in fast.casefold() or "nooit als advies" in html.casefold()
    confirmed = console.batch_confirm_headings(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_ids=[obj["object_id"] for obj in koppen],
    )
    assert confirmed
    refreshed = {
        obj["object_id"]: obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
    }
    for obj in koppen:
        row = refreshed[obj["object_id"]]
        assert row["confirmed_object_type"] == "heading"
        assert row["object_type"] == "heading"
        assert is_advice_weight("action_advice", published_object_type(row)) is False


def test_batch_confirm_rejects_slow_duty_and_leftover_unclassified(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_duty_html(leftover=5), filename="batch.html", title="Batch"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    duty = slow_review_duty(objects)
    leftover = remaining_unclassified(objects)
    assert duty and leftover
    with pytest.raises(ConsoleError, match="fast_lane_heading_required"):
        console.batch_confirm_headings(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_ids=[duty[0]["object_id"]],
        )
    with pytest.raises(ConsoleError, match="fast_lane_heading_required"):
        console.batch_confirm_headings(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_ids=[leftover[0]["object_id"]],
        )


# ---------------------------------------------------------------------------
# 3. Slow review duty is recommendation + condition/exception/high-risk
# ---------------------------------------------------------------------------


def test_slow_duty_is_recommendation_condition_exception_and_high_risk() -> None:
    objects = _koppen_78_inhoud_2008_style()
    objects.append(
        _knowledge_obj(
            "d1",
            "unclassified",
            "Continentie is een klinisch onderwerp.",
            proposed="definition",
        )
    )
    objects.append(
        _knowledge_obj(
            "x1",
            "unclassified",
            "Namelijk omdat de cliënt zelfstandig blijft.",
            proposed="explanation",
        )
    )
    duty_ids = {obj["object_id"] for obj in slow_review_duty(objects)}
    assert duty_ids == {"r1", "c1", "e1", "hr1"}
    leftover_ids = {obj["object_id"] for obj in remaining_unclassified(objects)}
    assert "u1" in leftover_ids
    assert "d1" in leftover_ids
    assert "x1" in leftover_ids
    assert leftover_ids.isdisjoint(duty_ids)
    not_duty = {obj["object_id"] for obj in remaining_not_duty(objects)}
    assert "d1" in not_duty and "x1" in not_duty
    high = next(obj for obj in objects if obj["object_id"] == "hr1")
    assert requires_four_eyes(high) is True


def test_console_inhoud_lists_only_slow_duty_cards(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_duty_html(leftover=12), filename="plicht.html", title="Plicht"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    duty = slow_review_duty(objects)
    leftover = remaining_unclassified(objects)
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    slow = _section(html, "review-lane-slow")
    titles = _index_link_titles(slow)
    assert len(titles) == len(duty)
    for obj in duty:
        assert any(
            _text_of(obj)[:40] in title or title[:40] in _text_of(obj) for title in titles
        )
        card = _client(console).get(
            f"/review?document={receipt['snapshot_id']}&object={obj['object_id']}"
        ).text
        assert "review-card-two-column" in card
        assert card.count('class="review-decision-form"') == 1
        assert "batch-confirm" not in card
    visible = _visible_text(html)
    assert "voorgestelde aanbevelingen" in visible.casefold()
    assert "voorwaarden" in visible.casefold()
    assert "uitzonderingen" in visible.casefold()
    assert "high-risk" in visible.casefold()
    assert leftover
    assert f"Resterend unclassified: {len(leftover)}" in visible


# ---------------------------------------------------------------------------
# 4. No zwaar/licht switch; no auto-confirm; no auto-promote; machine
#    does not decide something is light enough to serve
# ---------------------------------------------------------------------------


def test_no_zwaar_licht_switch_no_auto_confirm_no_auto_promote(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_duty_html(leftover=6), filename="geen-switch.html", title="Geen switch"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    leftover = remaining_unclassified(objects)
    assert leftover
    assert all(obj.get("object_type") == "unclassified" for obj in leftover)
    assert all(not obj.get("confirmed_object_type") for obj in leftover)
    ordinary = next(obj for obj in leftover if "Gewone toelichtende tekst" in _text_of(obj))
    assert ordinary.get("proposed_object_type") not in {"recommendation", "heading"}
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    lower = html.lower()
    for forbidden in (
        "zwaar/licht",
        "snel/langzaam",
        "snel-langzaam",
        "speed-toggle",
        'name="review_speed"',
        'id="review_speed"',
        "review-speed",
        "light enough",
        "licht genoeg",
    ):
        assert forbidden not in lower
    assert "envelope" not in lower
    assert "Documentenhiërarchie" in html
    source = APP_SOURCE.read_text(encoding="utf-8")
    assert "zwaar/licht" not in source
    assert "snel/langzaam" not in source
    css = CSS.read_text(encoding="utf-8")
    assert "zwaar/licht" not in css


def test_machine_does_not_decide_light_enough_to_serve() -> None:
    leftover = _record(
        object_id="u1",
        object_type="unclassified",
        text="Gewone toelichtende tekst nummer 1 zonder advieszin.",
    )
    proposed_rec = _record(
        object_id="p1",
        object_type="unclassified",
        text="Bespreek het onderwerp met de zorgvrager.",
        proposed="recommendation",
    )
    heading = _record(
        object_id="h1",
        object_type="heading",
        text="1. Inleiding",
        confirmed="heading",
    )
    confirmed_rec = _record(
        object_id="r1",
        object_type="recommendation",
        text="Bespreek het onderwerp met de zorgvrager.",
        confirmed="recommendation",
    )
    for blocked in (leftover, proposed_rec, heading):
        result = _eval("Wat adviseert deze richtlijn de zorgvrager?", [blocked])
        assert result["answerability"] != "supported"
        assert result["behavior"] == "abstain"
        assert published_object_type(blocked) != "recommendation"
    assert published_object_type(leftover) == "unclassified"
    assert published_object_type(proposed_rec) == "unclassified"
    supported = _eval("Wat adviseert deze richtlijn de zorgvrager?", [confirmed_rec])
    assert supported["answerability"] == "supported"
    assert is_advice_weight("action_advice", "unclassified") is False
    assert is_advice_weight("action_advice", "heading") is False
    assert is_advice_weight("action_advice", "recommendation") is True


# ---------------------------------------------------------------------------
# 5. Unclassified is never served; only confirmed recommendation MAG supported
# ---------------------------------------------------------------------------


def test_unclassified_never_served_only_confirmed_recommendation_mag_supported() -> None:
    unclassified = _record(
        object_id="u1",
        object_type="unclassified",
        text="Gewone toelichtende tekst.",
    )
    confirmed_rec = _record(
        object_id="r1",
        object_type="recommendation",
        text="Bespreek het onderwerp met de zorgvrager.",
        confirmed="recommendation",
    )
    result = _eval("Wat adviseert deze richtlijn de zorgvrager?", [unclassified])
    assert result["answerability"] != "supported"
    assert result["behavior"] == "abstain"
    supported = _eval("Wat adviseert deze richtlijn de zorgvrager?", [confirmed_rec])
    assert supported["answerability"] == "supported"


def test_four_eyes_unchanged_on_exception_and_high_risk() -> None:
    exception = _knowledge_obj(
        "e1",
        "exception",
        "Tenzij de huisarts al is ingeschakeld.",
        confirmed="exception",
    )
    high = _knowledge_obj(
        "hr1",
        "unclassified",
        "Leeftijdsgrens volgt het protocol.",
        risk_level="high",
    )
    ordinary = _knowledge_obj(
        "u1",
        "unclassified",
        "Gewone toelichtende tekst nummer 1 zonder advieszin.",
    )
    assert requires_four_eyes(exception, confirmed_type="exception") is True
    assert requires_four_eyes(high) is True
    assert requires_four_eyes(ordinary) is False


# ---------------------------------------------------------------------------
# 6. v2.16 tiny-objects, v2.17 chrome/slogans/bronpassage, v2.18 once-only
# ---------------------------------------------------------------------------


def test_v216_tiny_objects_v217_chrome_v218_no_duplicate_sentence_still_hold(
    tmp_path: Path,
) -> None:
    freeze = (
        "<!doctype html><html lang=\"nl\"><body>"
        "<nav class=\"bricks-nav-menu\"><a>Tools</a><a>Home</a>"
        "<a>Richtlijnen</a><a>Meedenken</a></nav>"
        "<h1>Richtlijn Continentie</h1>"
        "<h2>1.1 Inleiding</h2>"
        "<h2>2. Inleiding</h2>"
        "<h2>DOEN</h2>"
        "<p>1.</p>"
        f"<p>{OVERWEEG}</p>"
        f"<p>{EVENTUEEL}</p>"
        "<p>Bespreek het onderwerp met de zorgvrager.</p>"
        "</body></html>"
    ).encode("utf-8")
    html_path = tmp_path / "hold.html"
    html_path.write_bytes(freeze)
    fragments = extract_html(html_path, document_id="doc-hold", source_id="src-hold")
    texts = [row["clean_text"] for row in fragments]
    for label in CHROME_LABELS:
        assert label not in texts
    assert "1.1 Inleiding" in texts
    assert "2. Inleiding" in texts
    fused = split_meaning_units(f"{OVERWEEG} {EVENTUEEL}")
    assert len(fused) == 1
    assert EVENTUEEL in fused[0]
    assert is_continuation_fragment(EVENTUEEL) is True
    fused_exception = (
        "Verwijs de cliënt naar de huisarts. "
        "Tenzij samen met de cliënt hiervan wordt afgezien."
    )
    assert fusion_is_forbidden(fused_exception) is True
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=freeze, filename="hold.html", title="Hold"
    )
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    stored = [_text_of(obj) for obj in objects]
    for label in CHROME_LABELS:
        assert label not in stored
        assert all(label.casefold() != text.casefold() for text in stored)
    assert all(not is_strength_stamp(_text_of(obj)) for obj in objects)
    assert all(not is_list_number_only(_text_of(obj)) for obj in objects)
    assert all(not is_tiny_confirmable_text(_text_of(obj)) for obj in objects)
    assert EVENTUEEL not in stored
    assert any(OVERWEEG in text and EVENTUEEL in text for text in stored)
    rec = next(obj for obj in objects if OVERWEEG in _text_of(obj))
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    assert SLOGAN not in html
    assert "wat een EPD MAG zeggen" not in html
    assert "envelope" not in html.lower()
    assert "Documentenhiërarchie" in html
    card = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}"
    ).text
    heading = review_card_sentence(rec)
    assert EVENTUEEL in heading
    object_text = re.search(
        r'<div class="object-text">\s*<p>(.*?)</p>\s*</div>', card, flags=re.S
    )
    body = _visible_text(object_text.group(1)) if object_text else ""
    assert body == "" or re.sub(r"\s+", " ", body) != re.sub(r"\s+", " ", heading)
    assert is_kennisplatform_chrome_text("Tools") is True
    stored = rec.get("confirmed_object_type") or (
        rec.get("object_type") if rec.get("object_type") not in {None, "", "unclassified"} else None
    )
    assert recommendation_strength_ui_applies(rec) is (stored in {"recommendation", "outcome"})
    passage = researcher_visible_prose(
        console.open_source_passage(
            snapshot_id=receipt["snapshot_id"], object_id=rec["object_id"]
        )["passage"]
    )
    assert "<" not in passage
    assert "class=" not in passage
    assert "brxe-" not in passage


# ---------------------------------------------------------------------------
# 7. Unpublished Continentie re-extract; hiding without extract forbidden
# ---------------------------------------------------------------------------


def test_unpublished_continentie_reextract_on_same_sha256_allowed(tmp_path: Path) -> None:
    freeze = _duty_html(leftover=6)
    expected = sha256_bytes(freeze)
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=freeze, filename="continentie.html", title="Continentie"
    )
    assert receipt["sha256"] == expected
    before_ids = {
        obj["object_id"]
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    }
    again = console.reextract_unpublished(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert again["sha256"] == expected
    after = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    after_ids = {obj["object_id"] for obj in after}
    assert after_ids
    assert remaining_unclassified(after) is not None
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
    assert before_ids


def test_hiding_fragments_without_extract_is_forbidden(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_duty_html(leftover=4), filename="hide.html", title="Hide"
    )
    planted_text = "Geplant fragment dat in de store blijft tot extract."
    rows = console._load_objects(receipt["snapshot_id"])
    seed = next(row for row in rows if row.get("object_type") != "document")
    planted = {
        **seed,
        "object_id": f"{seed['object_id']}-planted-leftover",
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
    stored = [
        _text_of(obj)
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    ]
    assert planted_text in stored
    leftover = remaining_unclassified(
        _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    )
    assert any(obj["object_id"] == planted["object_id"] for obj in leftover)
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    visible = _visible_text(html)
    assert f"Resterend unclassified: {len(leftover)}" in visible
    slow = _section(html, "review-lane-slow")
    assert planted["object_id"] not in slow
    card = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={planted['object_id']}"
    ).text
    assert planted_text in _visible_text(card)
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
        console, accounts, data=_duty_html(leftover=3), filename="pub.html", title="Pub"
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
# 8. Serving fail-closed; G2 still blocks publish
# ---------------------------------------------------------------------------


def test_publish_remains_g2_blocked(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console, accounts, data=_duty_html(leftover=3), filename="g2.html", title="G2"
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
# 9. Freeze store paths remain confined (CodeQL / commit 2cc34c1)
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
def test_v219_ingest_filename_cannot_escape_source_store(
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


def test_v219_safe_filename_still_accepts_plain_basenames() -> None:
    assert safe_store_filename("continentie.html") == "continentie.html"
    assert safe_store_filename("richtlijn-v2.html") == "richtlijn-v2.html"
