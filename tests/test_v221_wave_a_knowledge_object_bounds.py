"""Acceptance tests for Protocol v2.21 wave A knowledge-object bounds.

Context-aware splitter + testable reject function + Continentie regression
fixtures. Tests hit the real functions. Wave B/C/D are out of scope.
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
from src.context_aware_split_v1 import (
    KEEP_OFFICIAL_HEADING,
    KEEP_SHORT_DEFINITION,
    MINIMUM_MEANING_WORDS,
    REJECT_BELOW_THRESHOLD,
    REJECT_CONTINUATION,
    REJECT_DUPLICATE,
    REJECT_LABEL_ONLY,
    REJECT_NAV_ONLY,
    REJECT_NOT_STANDALONE,
    REJECT_NUMBER_ONLY,
    REJECT_STAMP_ONLY,
    filter_before_object_creation,
    is_official_heading_text,
    is_short_real_definition,
    reject_candidate,
    split_context_aware_units,
)
from src.extract_html_v1 import extract as extract_html
from src.object_taxonomy_v1 import (
    is_advice_weight,
    is_continuation_fragment,
    is_kennisplatform_chrome_text,
    is_list_number_only,
    is_strength_stamp,
    is_tiny_confirmable_text,
    published_object_type,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import (
    ConsoleError,
    OperationsConsole,
    remaining_unclassified,
    review_stacks,
    safe_store_filename,
    slow_review_duty,
)


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
CONTINENTIE_FIXTURE = ROOT / "data/fixtures/continentie_v221_wave_a_regression.html"
APP_SOURCE = ROOT / "src/operations_console_app.py"
SLOGAN = "Dit wordt wat een EPD MAG zeggen."
EVENTUEEL = "Eventueel met hulp van de mantelzorger."
OVERWEEG = (
    "Overweeg om bij ouderen met urine-incontinentie én een cognitieve "
    "beperking het advies te geven om op vaste tijden te gaan plassen."
)
FULL_RECOMMENDATION = f"{OVERWEEG} {EVENTUEEL}"
BIJVOORBEELD = "Bijvoorbeeld een toiletdagboek van drie dagen."
SHORT_DEFINITION = "Continentie is het vermogen om urine en ontlasting op te houden."
CHROME_LABELS = ("Tools", "Home", "Richtlijnen", "Meedenken")
FAIL_STANDALONE = (
    "Tools",
    "Home",
    "Richtlijnen",
    "Meedenken",
    EVENTUEEL,
    "1.",
    "1",
    "2.",
    "DOEN",
    "OVERWEEG",
    "NIET DOEN",
    "problemen.",
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
        data=data if data is not None else CONTINENTIE_FIXTURE.read_bytes(),
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
        ((obj.get("content") or {}).get("clean_text") or obj.get("clean_text") or obj.get("text") or ""),
    ).strip()


def _locator_of(obj: dict) -> dict | None:
    for frag in (obj.get("provenance") or {}).get("source_fragments") or []:
        loc = frag.get("source_locator") or {}
        if loc.get("locator_value"):
            return loc
    return None


class _VisibleTextParser(HTMLParser):
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
    return [
        _visible_text(match).strip()
        for match in re.findall(r'<a class="review-row-link"[^>]*>(.*?)</a>', html, flags=re.S)
    ]


def _fragment(
    text: str,
    *,
    tag: str = "p",
    ordinal: int = 1,
    fragment_id: str = "f1",
    heading: str | None = None,
) -> dict:
    return {
        "fragment_id": fragment_id,
        "clean_text": text,
        "raw_text": text,
        "heading": heading,
        "section_path": [heading] if heading else [],
        "source_locator": {
            "locator_type": "web_line_range",
            "locator_value": f"lines:{ordinal}-{ordinal};{tag}:{ordinal}",
        },
    }


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
# 1. Reject function is unit-testable with explicit exceptions
# ---------------------------------------------------------------------------


def test_reject_function_is_unit_testable_with_explicit_exceptions() -> None:
    assert MINIMUM_MEANING_WORDS == 3
    assert reject_candidate("").rejected is True
    assert reject_candidate("DOEN").reason == REJECT_STAMP_ONLY
    assert reject_candidate("OVERWEEG").reason == REJECT_STAMP_ONLY
    assert reject_candidate("NIET DOEN").reason == REJECT_STAMP_ONLY
    assert reject_candidate("1.").reason == REJECT_NUMBER_ONLY
    assert reject_candidate("1").reason == REJECT_NUMBER_ONLY
    assert reject_candidate("Tools").reason == REJECT_NAV_ONLY
    assert reject_candidate("Home").reason == REJECT_NAV_ONLY
    assert reject_candidate("Richtlijnen").reason == REJECT_NAV_ONLY
    assert reject_candidate("Meedenken").reason == REJECT_NAV_ONLY
    assert reject_candidate(EVENTUEEL).reason == REJECT_CONTINUATION
    assert reject_candidate(BIJVOORBEELD).reason == REJECT_CONTINUATION
    assert reject_candidate("problemen.").reason in {
        REJECT_CONTINUATION,
        REJECT_LABEL_ONLY,
        REJECT_BELOW_THRESHOLD,
        REJECT_NOT_STANDALONE,
    }
    assert reject_candidate("Menu").reason in {
        REJECT_LABEL_ONLY,
        REJECT_BELOW_THRESHOLD,
        REJECT_CONTINUATION,
        REJECT_NOT_STANDALONE,
    }
    dup = reject_candidate(OVERWEEG, seen_clean_texts={OVERWEEG})
    assert dup.rejected is True
    assert dup.reason == REJECT_DUPLICATE

    heading = reject_candidate("Inleiding")
    assert heading.rejected is False
    assert heading.exception == KEEP_OFFICIAL_HEADING
    assert is_official_heading_text("Inleiding") is True
    numbered = reject_candidate("1.1 Inleiding")
    assert numbered.rejected is False
    assert numbered.exception == KEEP_OFFICIAL_HEADING
    assert is_official_heading_text("2. Inleiding") is True

    definition = reject_candidate(SHORT_DEFINITION)
    assert definition.rejected is False
    assert definition.exception == KEEP_SHORT_DEFINITION
    short_def = reject_candidate("Continentie is blaaskontrole.")
    assert short_def.rejected is False
    assert short_def.exception == KEEP_SHORT_DEFINITION
    assert is_short_real_definition(SHORT_DEFINITION) is True
    assert is_short_real_definition("Tools") is False
    assert is_kennisplatform_chrome_text("Inleiding") is False


def test_inleiding_is_kept_home_tools_richtlijnen_meedenken_are_chrome() -> None:
    assert is_kennisplatform_chrome_text("Inleiding") is False
    assert is_official_heading_text("Inleiding") is True
    assert filter_before_object_creation("Inleiding") is None
    for label in CHROME_LABELS:
        assert is_kennisplatform_chrome_text(label) is True
        assert reject_candidate(label).reason == REJECT_NAV_ONLY
        assert filter_before_object_creation(label) == REJECT_NAV_ONLY


# ---------------------------------------------------------------------------
# 2. Splitter: complete meaning units, stamps, trailing clauses, filter first
# ---------------------------------------------------------------------------


def test_splitter_yields_complete_units_with_bronpassage_and_locator(tmp_path: Path) -> None:
    html_path = tmp_path / "continentie.html"
    html_path.write_bytes(CONTINENTIE_FIXTURE.read_bytes())
    fragments = extract_html(
        html_path, document_id="doc-continentie", source_id="src-continentie"
    )
    units = split_context_aware_units(fragments, document_id="doc-continentie")
    texts = [item["text"] for item in units]
    assert EVENTUEEL not in texts
    assert any(OVERWEEG in text and EVENTUEEL in text for text in texts)
    rec = next(item for item in units if OVERWEEG in item["text"])
    assert rec["source_fragment_ids"]
    assert rec["clean_text"] == rec["text"]
    assert rec.get("proposed_recommendation_strength") == "overweeg"
    fused = split_meaning_units(f"{OVERWEEG} {EVENTUEEL}")
    assert fused == [FULL_RECOMMENDATION]
    assert is_continuation_fragment(EVENTUEEL) is True


def test_stamps_attach_to_following_advice_and_are_not_objects() -> None:
    fragments = [
        _fragment("DOEN", tag="h2", ordinal=1, fragment_id="s1"),
        _fragment(
            "Bespreek incontinentie met de cliënt en de mantelzorger.",
            tag="p",
            ordinal=2,
            fragment_id="a1",
        ),
        _fragment("OVERWEEG", tag="h2", ordinal=3, fragment_id="s2"),
        _fragment(OVERWEEG, tag="p", ordinal=4, fragment_id="a2"),
        _fragment(EVENTUEEL, tag="p", ordinal=5, fragment_id="c1"),
    ]
    units = split_context_aware_units(fragments, document_id="doc-stamps")
    texts = [item["text"] for item in units]
    assert "DOEN" not in texts
    assert "OVERWEEG" not in texts
    assert EVENTUEEL not in texts
    doen = next(item for item in units if item["text"].startswith("Bespreek"))
    assert doen.get("proposed_recommendation_strength") == "doen"
    overweeg = next(item for item in units if OVERWEEG in item["text"])
    assert EVENTUEEL in overweeg["text"]
    assert overweeg.get("proposed_recommendation_strength") == "overweeg"
    assert all(item["object_type"] != "heading" or item["text"] not in {"DOEN", "OVERWEEG"} for item in units)


def test_chrome_nav_list_numbers_filtered_before_object_creation() -> None:
    assert filter_before_object_creation("Tools") == REJECT_NAV_ONLY
    assert filter_before_object_creation("1.") == REJECT_NUMBER_ONLY
    assert filter_before_object_creation("") == "empty" or filter_before_object_creation("   ") == "empty"
    assert reject_candidate("Menu").reason in {
        REJECT_LABEL_ONLY,
        REJECT_BELOW_THRESHOLD,
        REJECT_CONTINUATION,
        REJECT_NOT_STANDALONE,
    }
    assert filter_before_object_creation("Inleiding") is None
    assert filter_before_object_creation(SHORT_DEFINITION) is None
    fragments = [
        _fragment("Tools", tag="li", ordinal=1, fragment_id="nav1"),
        _fragment("1.", tag="p", ordinal=2, fragment_id="n1"),
        _fragment("Inleiding", tag="h2", ordinal=3, fragment_id="h1", heading="Inleiding"),
        _fragment(SHORT_DEFINITION, tag="p", ordinal=4, fragment_id="d1"),
    ]
    units = split_context_aware_units(fragments, document_id="doc-filter")
    texts = [item["text"] for item in units]
    assert "Tools" not in texts
    assert "1." not in texts
    assert "Inleiding" in texts
    assert SHORT_DEFINITION in texts


def test_trailing_clauses_attach_to_previous_sentence() -> None:
    fragments = [
        _fragment(OVERWEEG, tag="p", ordinal=1, fragment_id="a1"),
        _fragment(EVENTUEEL, tag="p", ordinal=2, fragment_id="c1"),
        _fragment(f"Gebruik een toiletdagboek. {BIJVOORBEELD}", tag="p", ordinal=3, fragment_id="a2"),
    ]
    units = split_context_aware_units(fragments, document_id="doc-trail")
    texts = [item["text"] for item in units]
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


def test_no_duplicate_identical_clean_text_from_same_freeze() -> None:
    fragments = [
        _fragment("1.1 Inleiding", tag="h2", ordinal=1, fragment_id="h1", heading="1.1 Inleiding"),
        _fragment(FULL_RECOMMENDATION, tag="p", ordinal=2, fragment_id="a1"),
        _fragment("2. Inleiding", tag="h2", ordinal=3, fragment_id="h2", heading="2. Inleiding"),
        _fragment(FULL_RECOMMENDATION, tag="p", ordinal=4, fragment_id="a2"),
        _fragment(FULL_RECOMMENDATION, tag="p", ordinal=5, fragment_id="a3"),
    ]
    units = split_context_aware_units(fragments, document_id="doc-dedup")
    texts = [item["text"] for item in units]
    assert texts.count(FULL_RECOMMENDATION) == 1
    assert texts.count("1.1 Inleiding") == 1
    assert texts.count("2. Inleiding") == 1


# ---------------------------------------------------------------------------
# 3. Continentie regression fixtures: fail patterns stay out of duty queue
# ---------------------------------------------------------------------------


def test_continentie_fail_patterns_are_not_standalone_duty_objects(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    texts = [_text_of(obj) for obj in objects]
    for pattern in FAIL_STANDALONE:
        assert pattern not in texts
        assert all(pattern.casefold() != text.casefold() for text in texts)
    assert SHORT_DEFINITION in texts
    assert "1.1 Inleiding" in texts
    assert "2. Inleiding" in texts
    assert any(OVERWEEG in text and EVENTUEEL in text for text in texts)
    counts: dict[str, int] = {}
    for text in texts:
        counts[text] = counts.get(text, 0) + 1
    assert {text: count for text, count in counts.items() if count > 1} == {}

    koppen, _inhoud = review_stacks(objects)
    koppen_texts = [_text_of(obj) for obj in koppen]
    assert "Inleiding" in koppen_texts or "1.1 Inleiding" in koppen_texts
    assert "2. Inleiding" in koppen_texts
    for label in CHROME_LABELS:
        assert label not in koppen_texts
    assert all(not is_strength_stamp(_text_of(obj)) for obj in koppen)

    duty = slow_review_duty(objects)
    duty_texts = [_text_of(obj) for obj in duty]
    for pattern in FAIL_STANDALONE:
        assert pattern not in duty_texts
    assert all(EVENTUEEL not in text or OVERWEEG in text for text in duty_texts)
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    titles = _index_link_titles(html)
    for pattern in FAIL_STANDALONE:
        assert pattern not in titles
    assert "Documentenhiërarchie" in html
    assert "envelope" not in html.lower()
    assert SLOGAN not in html


def test_splitter_units_have_locator_and_bronpassage_after_ingest(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    rec = next(obj for obj in objects if OVERWEEG in _text_of(obj))
    assert _locator_of(rec)
    assert _locator_of(rec).get("locator_value")
    assert EVENTUEEL in _text_of(rec)
    html = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}"
    ).text
    assert OVERWEEG in _visible_text(html)
    assert EVENTUEEL in _visible_text(html)
    assert "brxe-" not in html or "review-card-bronpassage" in html


def test_pdf_shaped_once_and_html_repeated_modules_do_not_duplicate() -> None:
    html_shaped = [
        _fragment("1.1 Inleiding", tag="h2", ordinal=1, fragment_id="h1", heading="1.1 Inleiding"),
        _fragment(FULL_RECOMMENDATION, tag="p", ordinal=2, fragment_id="html-a"),
        _fragment("2. Inleiding", tag="h2", ordinal=3, fragment_id="h2", heading="2. Inleiding"),
        _fragment(FULL_RECOMMENDATION, tag="p", ordinal=4, fragment_id="html-b"),
    ]
    pdf_shaped = [
        _fragment("1.1 Inleiding", tag="h2", ordinal=1, fragment_id="pdf-h", heading="1.1 Inleiding"),
        _fragment(FULL_RECOMMENDATION, tag="p", ordinal=2, fragment_id="pdf-a"),
    ]
    html_units = split_context_aware_units(html_shaped, document_id="doc-html")
    pdf_units = split_context_aware_units(pdf_shaped, document_id="doc-pdf")
    html_recs = [item["text"] for item in html_units if OVERWEEG in item["text"]]
    pdf_recs = [item["text"] for item in pdf_units if OVERWEEG in item["text"]]
    assert html_recs == [FULL_RECOMMENDATION]
    assert pdf_recs == [FULL_RECOMMENDATION]


def test_short_definition_and_real_headings_survive_extract(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    texts = [_text_of(obj) for obj in objects]
    assert SHORT_DEFINITION in texts
    assert "1.1 Inleiding" in texts
    assert "2. Inleiding" in texts
    assert "Diagnostiek" in texts
    assert "Uitgangsvraag 3a - Niet-medicamenteuze interventies bij urine-incontinentie" in texts


# ---------------------------------------------------------------------------
# 4. v2.16 tiny-objects, v2.17 chrome, v2.18 no-duplicate-sentence still hold
# ---------------------------------------------------------------------------


def test_v216_tiny_objects_v217_chrome_v218_dedup_still_hold(tmp_path: Path) -> None:
    assert is_tiny_confirmable_text("1.") is True
    assert is_tiny_confirmable_text("DOEN") is True
    assert is_tiny_confirmable_text("problemen.") is True
    assert is_list_number_only("1.") is True
    assert is_strength_stamp("DOEN") is True
    assert is_kennisplatform_chrome_text("Tools") is True
    assert is_continuation_fragment(EVENTUEEL) is True
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    texts = [_text_of(obj) for obj in objects]
    assert "1." not in texts
    assert "DOEN" not in texts
    assert "problemen." not in texts
    for label in CHROME_LABELS:
        assert label not in texts
    assert texts.count(FULL_RECOMMENDATION) <= 1
    assert any(OVERWEEG in text and EVENTUEEL in text for text in texts)
    source = APP_SOURCE.read_text(encoding="utf-8")
    assert SLOGAN not in source
    html = _client(console, "researcher.anne").get(
        f"/review?document={receipt['snapshot_id']}"
    ).text
    assert SLOGAN not in html
    assert "wat een EPD MAG zeggen" not in html
    assert "envelope" not in html.lower()


def test_unpublished_reextract_allowed_hiding_without_extract_forbidden(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    freeze = CONTINENTIE_FIXTURE.read_bytes()
    receipt = _ingest(console, accounts, data=freeze)
    again = console.reextract_unpublished(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert again["sha256"] == receipt["sha256"]
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
            "raw_text": EVENTUEEL,
            "clean_text": EVENTUEEL,
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
    console.reextract_unpublished(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    after = [_text_of(obj) for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))]
    assert EVENTUEEL not in after


# ---------------------------------------------------------------------------
# 5. G2 still blocks publish; unclassified never served
# ---------------------------------------------------------------------------


def test_serving_still_fail_closed_unclassified_never_served() -> None:
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
# 6. Freeze store paths remain confined (CodeQL / commit 2cc34c1)
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
def test_v221_ingest_filename_cannot_escape_source_store(
    tmp_path: Path, filename: str
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    with pytest.raises(ConsoleError, match="invalid_store_path"):
        _ingest(console, accounts, filename=filename)


def test_v221_safe_filename_still_accepts_plain_basenames() -> None:
    assert safe_store_filename("continentie.html") == "continentie.html"
    assert safe_store_filename("richtlijn-v2.html") == "richtlijn-v2.html"


def test_factory_fixture_still_extracts(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(
        console,
        accounts,
        data=HTML_FIXTURE.read_bytes(),
        filename="factory.html",
        title="Factory",
        family="continentie-factory",
    )
    texts = [_text_of(obj) for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))]
    assert any("Bespreek het onderwerp" in text for text in texts)
    assert "Aanbevelingen" in texts
