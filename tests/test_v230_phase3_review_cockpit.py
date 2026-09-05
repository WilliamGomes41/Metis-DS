"""Protocol v2.30 Forge Phase 3: review cockpit (Block B).

Review UI + open-bron real context + collapsed documentpositie.
Richtlijn inhoudelijke candidates. Phase 1+2 admission / deep context stay.
Passage register / gold / metrics are Phase 4 and MUST NOT appear here.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here. publish() stays
G2-BLOCKED.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED, admission_of, blocked_audit_lane, ordinary_review_queue
from src.integrity_kernel import compute_canonical_object_hash
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole, is_slow_review_duty


ROOT = Path(__file__).resolve().parents[1]
PHASE2_FIXTURE = ROOT / "data/fixtures/v230_phase2_deep_context_regression.html"
DJG = "De dJG wordt in Nederland vaker gebruikt."
ADVISEERT = (
    "De werkgroep adviseert de verpleegkundige de risicofactoren "
    "scorelijst te gebruiken bij iedere intake."
)
PREV_CONDITION = (
    "Bij een cliënt van 60 jaar of ouder zonder recente fractuur "
    "geldt extra aandacht voor botgezondheid."
)
NEXT_OVERLEG = (
    "Overleg bij een vastgesteld verhoogd fractuurrisico met de cliënt over verwijzing."
)
CURRENT_HEADING = "2 Aanbevelingen"
ANCESTOR_HEADING = "Richtlijn Fractuurpreventie"

REVIEWER_COPY = (
    "Je beoordeelt één geselecteerde passage.",
    "De volledige richtlijn blijft ongewijzigd.",
    "Metis maakt geschikte passages apart bruikbaar.",
)
PROTOCOL_JARGON = (
    "Relatie bevestigen",
    "gate_result",
    "reason_codes",
    "type_contract",
    "admission_gate",
    "source_locator",
    "confirmed relation",
    "Voorgestelde relatie",
    "Ouder kiezen",
    "ouder/kind",
)
SUITABILITY_LABELS = (
    "Ja",
    "mist context",
    "samenvoegen",
    "alleen onderbouwing",
    "geen kenniseenheid",
)
EINDOORDEEL_LABELS = (
    "Goedkeuren",
    "Goedkeuren na correctie",
    "Afwijzen",
    "Later beoordelen",
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
    return {"researcher": researcher, "reviewer": reviewer}


def _ingest(console: OperationsConsole, accounts: dict, fixture: Path = PHASE2_FIXTURE, **overrides) -> dict:
    kwargs = {
        "actor_id": accounts["researcher"]["account_id"],
        "filename": fixture.name,
        "data": fixture.read_bytes(),
        "content_type": "text/html",
        "ingest_kind": "new",
        "title": "Phase 3 review cockpit",
        "version": "1.0",
        "date": "2025-04-01",
        "live_url": "",
        "class_": "richtlijn",
        "family": "fractuurpreventie",
        "named_reviewers": [accounts["reviewer"]["account_id"]],
    }
    kwargs.update(overrides)
    return console.ingest(**kwargs)


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


def _text_of(obj: dict) -> str:
    return ((obj.get("content") or {}).get("clean_text") or obj.get("candidate_text") or "").strip()


def _admission(obj: dict) -> dict:
    return admission_of(obj)


def _scan_of(obj: dict) -> dict:
    admission = _admission(obj)
    scan = admission.get("context_scan") or {}
    return scan if isinstance(scan, dict) else {}


def _find_by_text(objects: list[dict], snippet: str) -> dict:
    for obj in objects:
        if snippet in _text_of(obj):
            return obj
    raise AssertionError(f"no object contains {snippet!r}")


def _client(console: OperationsConsole) -> TestClient:
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    return client


def _card(html: str, object_id: str) -> str:
    match = re.search(
        rf'<article class="[^"]*review-card[^"]*"[^>]*>.*?</article>',
        html,
        flags=re.S,
    )
    if match and object_id in match.group(0):
        return match.group(0)
    raise AssertionError("review cockpit card not found")


def _visible_text(html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script[^>]*>", " ", html, flags=re.S | re.IGNORECASE)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_hidden(html: str) -> str:
    """Drop collapsed choosers from the primary surface. Hidden inputs stay."""
    cleaned = re.sub(
        r"<details\b[^>]*>.*?</details>",
        " ",
        html,
        flags=re.S | re.I,
    )
    cleaned = re.sub(
        r"<(div|section|aside|select)[^>]*\bhidden\b[^>]*>.*?</\1>",
        " ",
        cleaned,
        flags=re.S | re.I,
    )
    return cleaned


def _step(card: str, letter: str) -> str:
    match = re.search(
        rf'<section[^>]*data-review-step="{letter}"[^>]*>.*?</section>',
        card,
        flags=re.S,
    )
    assert match, f"review step {letter} missing"
    return match.group(0)


def _strip_locator(console: OperationsConsole, snapshot_id: str, object_id: str) -> None:
    rows = console._load_objects(snapshot_id)
    for row in rows:
        if row["object_id"] != object_id:
            continue
        provenance = row.setdefault("provenance", {})
        for frag in provenance.get("source_fragments") or []:
            frag.pop("source_locator", None)
        row.pop("source_locator", None)
    console._save_objects(snapshot_id, rows)


def _heading_id(objects: list[dict], current_id: str) -> str:
    for obj in objects:
        if obj["object_id"] == current_id:
            continue
        if (obj.get("object_type") == "heading" or obj.get("proposed_object_type") == "heading") and obj.get("object_id"):
            return str(obj["object_id"])
    raise AssertionError("no heading available as parent")


def _setup_adviseert(tmp_path: Path) -> tuple[OperationsConsole, dict, dict, dict, str]:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    adviseert = _find_by_text(objects, "adviseert de verpleegkundige de risicofactoren")
    html = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={adviseert['object_id']}"
    ).text
    return console, accounts, receipt, adviseert, html


# ---------------------------------------------------------------------------
# Reviewer copy + visibility (no protocol jargon on the cockpit)
# ---------------------------------------------------------------------------


def test_review_cockpit_uses_fixed_ordinary_dutch_copy(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    visible = _visible_text(_strip_hidden(card))
    for sentence in REVIEWER_COPY:
        assert sentence in visible, sentence
    assert "Full guideline remains unchanged" not in visible
    assert "ignore this" not in visible.casefold()
    assert "chrome" not in visible.casefold()


def test_primary_surface_has_no_protocol_jargon_or_relation_chrome(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    primary = _strip_hidden(card)
    visible = _visible_text(primary)
    for token in PROTOCOL_JARGON:
        assert token not in primary, token
        assert token not in visible, token
    assert "Relatie bevestigen" not in html
    assert "data-parent-choice-list" not in primary
    assert 'aria-label="Inhoudsopgave"' not in primary
    assert "Koppen uit de hoofdtekst" not in primary
    assert "toc-headings" not in primary


def test_review_cockpit_is_a_to_f_order_with_one_save(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    positions = []
    for letter in "abcdef":
        idx = card.find(f'data-review-step="{letter}"')
        assert idx >= 0, letter
        positions.append(idx)
    assert positions == sorted(positions)
    assert card.count('data-submit-review') == 1
    assert "Review opslaan en volgende" in card
    assert "Review vastleggen" not in card
    form = re.search(r'<form[^>]*data-review-form[^>]*>.*?</form>', card, flags=re.S)
    assert form, "ONE save form missing"
    blob = form.group(0)
    for field in (
        'name="suitability"',
        'name="documentpositie_action"',
        'name="type_action"',
        'name="eindoordeel"',
    ):
        assert field in blob, field


# ---------------------------------------------------------------------------
# (A) selected passage + why selected
# ---------------------------------------------------------------------------


def test_step_a_shows_selected_passage_and_why(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    step = _step(_card(html, adviseert["object_id"]), "a")
    visible = _visible_text(step)
    assert "adviseert de verpleegkundige" in visible
    assert "Geselecteerd omdat" in visible
    assert "aanbeveling" in visible.casefold()


# ---------------------------------------------------------------------------
# (B) broncontext is real surrounding freeze context
# ---------------------------------------------------------------------------


def test_step_b_broncontext_is_surrounding_freeze_not_card_enlarge(tmp_path: Path) -> None:
    console, _accounts, receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    step = _step(card, "b")
    visible = _visible_text(step)
    assert "Broncontext" in step or "broncontext" in step.casefold()
    assert PREV_CONDITION in visible
    assert NEXT_OVERLEG in visible
    assert CURRENT_HEADING in visible
    assert ANCESTOR_HEADING in visible
    marked = re.search(
        r'<mark\b[^>]*class="[^"]*broncontext-marked[^"]*"[^>]*>(.*?)</mark>',
        step,
        flags=re.S,
    )
    assert marked, "source_text_exact must be visually marked inside surrounding context"
    assert "adviseert de verpleegkundige" in _visible_text(marked.group(1))
    admission = _admission(adviseert)
    source_exact = str(admission.get("source_text_exact") or "")
    assert source_exact
    assert source_exact in step or "adviseert de verpleegkundige" in marked.group(1)
    # MUST NOT merely enlarge the same truncated card sentence.
    assert PREV_CONDITION != ADVISEERT
    assert 'class="object-text"' not in step
    scan = _scan_of(adviseert)
    assert PREV_CONDITION in str(admission.get("context_before") or scan.get("previous_paragraph") or "")
    opened = console.open_source_passage(
        snapshot_id=receipt["snapshot_id"],
        object_id=adviseert["object_id"],
    )
    assert opened.get("reserialized") is False


def test_broncontext_is_not_a_css_zoom_of_the_card_snippet(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    step = _step(card, "b")
    assert "transform: scale" not in step.casefold()
    assert "font-size: 2" not in step.casefold()
    assert PREV_CONDITION in _visible_text(step)
    assert _visible_text(step).count("adviseert de verpleegkundige") >= 1


# ---------------------------------------------------------------------------
# (C) suitability
# ---------------------------------------------------------------------------


def test_step_c_suitability_options_are_ordinary_dutch(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    step = _step(_card(html, adviseert["object_id"]), "c")
    visible = _visible_text(step)
    for label in SUITABILITY_LABELS:
        assert label in visible, label
    for value in (
        "ja",
        "mist_context",
        "samenvoegen",
        "alleen_onderbouwing",
        "geen_kenniseenheid",
    ):
        assert f'value="{value}"' in step, value


# ---------------------------------------------------------------------------
# (D) documentpositie collapsed; hierarchy only after Andere kop
# ---------------------------------------------------------------------------


def test_step_d_documentpositie_is_gevonden_onder_not_parent_dump(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    step = _step(card, "d")
    primary = _strip_hidden(step)
    visible = _visible_text(primary)
    assert "Gevonden onder:" in visible or "Gevonden onder" in visible
    assert CURRENT_HEADING in visible
    assert "Dit klopt" in visible
    assert "Andere kop kiezen" in visible
    assert "Koppen uit de hoofdtekst" not in primary
    assert "data-parent-choice-list" not in primary
    assert "Inhoudsopgave" not in visible
    chooser = re.search(
        r'<(details|section|div)[^>]*(data-heading-chooser|id="heading-chooser")[^>]*>.*?</\1>',
        step,
        flags=re.S,
    )
    assert chooser, "heading chooser must exist, collapsed until Andere kop"
    chooser_html = chooser.group(0)
    assert "hidden" in chooser.group(0)[:200].casefold() or chooser.group(0).startswith("<details")
    assert "data-parent-choice-list" in chooser_html
    assert 'name="parent_choice"' in chooser_html
    assert 'type="search"' in chooser_html or 'data-heading-search' in chooser_html
    assert "Inhoudsopgave" not in _visible_text(chooser_html)
    assert "1. Signalering" not in chooser_html or 'data-heading-role="toc"' not in chooser_html
    assert 'data-heading-role="toc"' not in chooser_html
    assert 'data-heading-role="body"' in chooser_html
    radios = re.findall(r'<input[^>]*type="radio"[^>]*name="parent_choice"[^>]*>', chooser_html)
    links = re.findall(r'<a[^>]*href="/review\?document=', chooser_html)
    assert radios, "select must be a distinct radio"
    assert links, "navigate must be a distinct link"
    assert 'form="relations-' not in chooser_html


def test_heading_chooser_browse_does_not_silently_select(tmp_path: Path) -> None:
    console, accounts, receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    step = _step(card, "d")
    radio_values = re.findall(
        r'<input[^>]*name="parent_choice"[^>]*value="([^"]+)"',
        step,
    )
    assert radio_values
    heading_id = radio_values[0]
    client = _client(console)
    browsed = client.get(
        f"/review?document={receipt['snapshot_id']}&object={heading_id}"
    ).text
    assert f'value="{heading_id}"' not in browsed or 'checked' not in browsed.split(heading_id, 1)[0][-80:]
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == adviseert["object_id"]
    )
    assert live.get("parent_object_id") in (None, "")
    confirmed = [
        row
        for row in (live.get("confirmed_relations") or [])
        if row.get("relation_type") in {"child", "parent"}
    ]
    assert confirmed == []


# ---------------------------------------------------------------------------
# (E) type proposal + Dit klopt / Type wijzigen
# ---------------------------------------------------------------------------


def test_step_e_starts_from_metis_proposal_not_only_unconfirmed(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    step = _step(_card(html, adviseert["object_id"]), "e")
    primary = _visible_text(_strip_hidden(step))
    assert "Metis stelt voor:" in primary
    assert "Aanbeveling" in primary
    assert "Dit klopt" in primary
    assert "Type wijzigen" in primary
    assert primary.strip().startswith("Metis") or "Metis stelt voor" in primary
    assert not re.search(r"^nog niet bevestigd$", primary)
    select = re.search(r"<select[^>]*name=\"confirmed_object_type\"[^>]*>.*?</select>", step, flags=re.S)
    if select:
        opening = select.group(0).split(">", 1)[0]
        assert "hidden" in opening or 'hidden' in step[step.find("Type wijzigen") :][:400]


def test_sterkte_stays_hidden_until_confirmed_aanbeveling(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    assert adviseert.get("confirmed_object_type") not in {"recommendation", "outcome"}
    stamp = re.search(r"<section[^>]*data-stamp-block[^>]*>", card)
    assert stamp, "stamp block must exist for live reveal"
    assert "hidden" in stamp.group(0)
    assert 'name="recommendation_strength"' in card
    strength = re.search(r"<select[^>]*name=\"recommendation_strength\"[^>]*>", card)
    assert strength
    assert "disabled" in strength.group(0)


# ---------------------------------------------------------------------------
# (F) eindoordeel + ONE save persistence
# ---------------------------------------------------------------------------


def test_step_f_eindoordeel_options(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    step = _step(_card(html, adviseert["object_id"]), "f")
    visible = _visible_text(step)
    for label in EINDOORDEEL_LABELS:
        assert label in visible, label
    for value in (
        "goedkeuren",
        "goedkeuren_na_correctie",
        "afwijzen",
        "later_beoordelen",
    ):
        assert f'value="{value}"' in step, value
    assert "Revisie vragen" not in visible


def test_one_save_stores_suitability_documentpositie_type_and_eindoordeel(tmp_path: Path) -> None:
    console, accounts, receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    parent_ids = re.findall(r'<input[^>]*name="parent_choice"[^>]*value="([^"]+)"', card)
    parent_id = parent_ids[0] if parent_ids else ""
    client = _client(console)
    posted = client.post(
        "/review",
        data={
            "snapshot_id": receipt["snapshot_id"],
            "object_id": adviseert["object_id"],
            "suitability": "ja",
            "documentpositie_action": "dit_klopt",
            "parent_choice": parent_id,
            "found_under": CURRENT_HEADING,
            "type_action": "dit_klopt",
            "confirmed_object_type": "recommendation",
            "eindoordeel": "goedkeuren",
            "decision": "approve",
            "recommendation_strength": "doen",
        },
        follow_redirects=False,
    )
    assert posted.status_code in {303, 200}
    location = posted.headers.get("location") or ""
    assert "/review" in location
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == adviseert["object_id"]
    )
    review = (live.get("metadata") or {}).get("review_passage") or {}
    assert review.get("suitability") == "ja"
    assert review.get("eindoordeel") == "goedkeuren"
    assert review.get("type_action") == "dit_klopt"
    assert review.get("documentpositie_action") == "dit_klopt"
    path = (review.get("documentpositie") or {}).get("path") or review.get("found_under") or ""
    assert CURRENT_HEADING in str(path)
    assert live.get("confirmed_object_type") == "recommendation"
    bindings = console.object_review_bindings(receipt["snapshot_id"])
    mine = [row for row in bindings if row.get("object_id") == adviseert["object_id"]]
    assert mine
    assert mine[-1].get("suitability") == "ja" or review.get("suitability") == "ja"
    assert mine[-1].get("eindoordeel") == "goedkeuren" or review.get("eindoordeel") == "goedkeuren"


def test_later_beoordelen_saves_without_approving(tmp_path: Path) -> None:
    console, accounts, receipt, adviseert, _html = _setup_adviseert(tmp_path)
    client = _client(console)
    posted = client.post(
        "/review",
        data={
            "snapshot_id": receipt["snapshot_id"],
            "object_id": adviseert["object_id"],
            "suitability": "mist_context",
            "documentpositie_action": "dit_klopt",
            "found_under": CURRENT_HEADING,
            "type_action": "dit_klopt",
            "confirmed_object_type": "recommendation",
            "eindoordeel": "later_beoordelen",
        },
        follow_redirects=False,
    )
    assert posted.status_code in {303, 200}
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == adviseert["object_id"]
    )
    review = (live.get("metadata") or {}).get("review_passage") or {}
    assert review.get("suitability") == "mist_context"
    assert review.get("eindoordeel") == "later_beoordelen"
    assert (live.get("governance") or {}).get("validation_status") != "approved"
    bindings = [
        row
        for row in console.object_review_bindings(receipt["snapshot_id"])
        if row.get("object_id") == adviseert["object_id"] and row.get("valid") and row.get("decision") == "approve"
    ]
    assert bindings == []


def test_save_redirects_to_next_ordinary_object(tmp_path: Path) -> None:
    console, accounts, receipt, adviseert, _html = _setup_adviseert(tmp_path)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    ordinary = [obj for obj in ordinary_review_queue(objects) if is_slow_review_duty(obj)]
    assert len(ordinary) >= 2
    current_index = next(i for i, obj in enumerate(ordinary) if obj["object_id"] == adviseert["object_id"])
    nxt = ordinary[current_index + 1]
    client = _client(console)
    posted = client.post(
        "/review",
        data={
            "snapshot_id": receipt["snapshot_id"],
            "object_id": adviseert["object_id"],
            "suitability": "ja",
            "documentpositie_action": "dit_klopt",
            "found_under": CURRENT_HEADING,
            "type_action": "dit_klopt",
            "confirmed_object_type": "recommendation",
            "eindoordeel": "later_beoordelen",
        },
        follow_redirects=False,
    )
    assert posted.status_code in {303, 200}
    location = posted.headers.get("location") or ""
    assert nxt["object_id"] in location


# ---------------------------------------------------------------------------
# Phase 1+2 gates remain
# ---------------------------------------------------------------------------


def test_blocked_candidate_still_cannot_be_approved_or_type_confirmed(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    djg = _find_by_text(console.snapshot_objects(receipt["snapshot_id"]), DJG)
    assert _admission(djg)["gate_result"] == GATE_BLOCKED
    with pytest.raises(ConsoleError, match="blocked_candidate_not_reviewable"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=djg["object_id"],
            decision="approve",
            confirmed_object_type="recommendation",
            suitability="ja",
            eindoordeel="goedkeuren",
        )
    client = _client(console)
    posted = client.post(
        "/review",
        data={
            "snapshot_id": receipt["snapshot_id"],
            "object_id": djg["object_id"],
            "suitability": "ja",
            "type_action": "dit_klopt",
            "confirmed_object_type": "recommendation",
            "eindoordeel": "goedkeuren",
            "decision": "approve",
        },
    )
    assert posted.status_code in {400, 403}
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == djg["object_id"]
    )
    assert live.get("confirmed_object_type") != "recommendation"
    assert _admission(live)["gate_result"] == GATE_BLOCKED


def test_ordinary_queue_and_index_remain_allowed_only(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    ordinary = ordinary_review_queue(objects)
    assert all(_admission(obj).get("gate_result") == GATE_ALLOWED for obj in ordinary)
    assert not any(obj in ordinary for obj in blocked_audit_lane(objects))
    client = _client(console)
    index = client.get(f"/review?document={receipt['snapshot_id']}").text
    slow = index.split('class="review-lane-slow"', 1)[-1].split("review-blocked-audit", 1)[0]
    assert DJG not in slow
    assert "adviseert de verpleegkundige" in slow
    assert "review-blocked-audit" in index


def test_boom_path_is_unchanged_and_publish_stays_blocked(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="valrisico-boom.json",
        data=_boom_freeze_bytes(),
        content_type="application/json",
        ingest_kind="new",
        title="Valrisico boom",
        version="1.0",
        date="2025-04-01",
        live_url="",
        class_="beslisboom",
        family="valrisico",
        named_reviewers=[accounts["reviewer"]["account_id"]],
    )
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    kinds = {obj.get("proposed_object_type") or obj.get("object_type") for obj in objects}
    assert "path" in kinds and "node" in kinds and "outcome" in kinds
    assert not (ROOT / "HANDOFF.md").exists()
    source = (ROOT / "src/operations_console_v1.py").read_text(encoding="utf-8")
    assert '"g2": "BLOCKED"' in source
    publisher = console.create_account(
        username="publisher.carla",
        password="carla-secret",
        roles=("publisher",),
        display_name="Carla Publisher",
    )
    considered = console.consider_publish(
        actor_id=publisher["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert considered["publish_allowed"] is False
    assert considered["g2"] == "BLOCKED"
    published = console.publish(
        actor_id=publisher["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert published["status"] == "BLOCKED"


def test_review_and_correction_do_not_change_sibling_canonical_hash(tmp_path: Path) -> None:
    console, accounts, receipt, adviseert, _html = _setup_adviseert(tmp_path)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    sibling = next(obj for obj in objects if obj["object_id"] != adviseert["object_id"])
    sibling_hash = compute_canonical_object_hash(sibling)
    sibling_json = json.dumps(sibling, sort_keys=True)
    adviseert_hash = compute_canonical_object_hash(adviseert)

    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=adviseert["object_id"],
        decision="reject",
        comment="Onjuiste weergave van de bron.",
    )
    after_reject = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == sibling["object_id"]
    )
    assert compute_canonical_object_hash(after_reject) == sibling_hash
    assert json.dumps(after_reject, sort_keys=True) == sibling_json

    other = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] != adviseert["object_id"] and obj["object_id"] != sibling["object_id"]
        and obj.get("object_type") != "document"
    )
    other_hash = compute_canonical_object_hash(other)
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=other["object_id"],
        decision="revise",
        comment="Corrigeer de formulering.",
        proposed_correction="Bespreek het onderwerp expliciet met de zorgvrager.",
    )
    console.correct_object(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=other["object_id"],
        patch={
            "reason": "reviewer correction",
            "operations": [
                {
                    "op": "set",
                    "path": "content.clean_text",
                    "value": "Bespreek het onderwerp expliciet met de zorgvrager.",
                }
            ],
        },
    )
    still_other_old = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"], include_blocked=True)
        if obj["object_id"] == other["object_id"] and obj["object_version"] == other["object_version"]
    )
    assert compute_canonical_object_hash(still_other_old) == other_hash
    untouched = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == sibling["object_id"]
    )
    assert compute_canonical_object_hash(untouched) == sibling_hash
    live_adviseert = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == adviseert["object_id"]
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=live_adviseert["object_id"],
        decision="later",
        suitability="ja",
        eindoordeel="later_beoordelen",
        documentpositie_action="dit_klopt",
        type_action="dit_klopt",
        found_under="2 Aanbevelingen",
    )
    still_sibling = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == sibling["object_id"]
    )
    assert compute_canonical_object_hash(still_sibling) == sibling_hash
    assert compute_canonical_object_hash(adviseert) == adviseert_hash


def test_merge_heading_parent_relations_keeps_semantic_edges() -> None:
    from src.review_cockpit_v1 import merge_heading_parent_relations

    merged = merge_heading_parent_relations(
        [
            {"relation_type": "applies_if", "target_object_id": "cond-1"},
            {"relation_type": "except_if", "target_object_id": "exc-1"},
            {"relation_type": "child", "target_object_id": "old-heading"},
            {"relation_type": "parent", "target_object_id": "old-child"},
        ],
        "new-heading",
    )
    assert {"relation_type": "applies_if", "target_object_id": "cond-1"} in merged
    assert {"relation_type": "except_if", "target_object_id": "exc-1"} in merged
    assert {"relation_type": "child", "target_object_id": "new-heading"} in merged
    assert not any(row.get("relation_type") in {"parent", "child"} and row.get("target_object_id") != "new-heading" for row in merged)


def test_documentpositie_save_preserves_confirmed_semantic_relations(tmp_path: Path) -> None:
    console, accounts, receipt, adviseert, _html = _setup_adviseert(tmp_path)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    condition = _find_by_text(objects, PREV_CONDITION)
    heading_id = _heading_id(objects, adviseert["object_id"])
    console.confirm_relations(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=adviseert["object_id"],
        relations=[{"relation_type": "applies_if", "target_object_id": condition["object_id"]}],
    )
    after_bind = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == adviseert["object_id"]
    )
    assert any(
        row.get("relation_type") == "applies_if" and row.get("target_object_id") == condition["object_id"]
        for row in (after_bind.get("confirmed_relations") or [])
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=adviseert["object_id"],
        decision="later",
        suitability="ja",
        eindoordeel="later_beoordelen",
        documentpositie_action="andere_kop",
        parent_choice=heading_id,
        type_action="dit_klopt",
        found_under=CURRENT_HEADING,
    )
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == adviseert["object_id"]
    )
    rels = live.get("confirmed_relations") or []
    assert any(
        row.get("relation_type") == "applies_if" and row.get("target_object_id") == condition["object_id"]
        for row in rels
    ), "applies_if must survive heading/parent assignment"
    assert any(
        row.get("relation_type") == "child" and row.get("target_object_id") == heading_id
        for row in rels
    )


def test_failed_review_does_not_persist_parent_relation(tmp_path: Path) -> None:
    console, accounts, receipt, adviseert, _html = _setup_adviseert(tmp_path)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    heading_id = _heading_id(objects, adviseert["object_id"])
    before = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == adviseert["object_id"]
    )
    before_rels = list(before.get("confirmed_relations") or [])
    before_parent = before.get("parent_object_id")
    before_version = before.get("object_version")
    _strip_locator(console, receipt["snapshot_id"], adviseert["object_id"])
    with pytest.raises(ConsoleError, match="open_original|source_locator"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=adviseert["object_id"],
            decision="approve",
            confirmed_object_type="recommendation",
            suitability="ja",
            eindoordeel="goedkeuren",
            documentpositie_action="andere_kop",
            parent_choice=heading_id,
            type_action="dit_klopt",
        )
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == adviseert["object_id"]
    )
    assert live.get("parent_object_id") == before_parent
    assert live.get("object_version") == before_version
    assert (live.get("confirmed_relations") or []) == before_rels


def test_empty_suitability_is_rejected_and_creates_no_approval_binding(tmp_path: Path) -> None:
    console, accounts, receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    assert 'name="suitability"' in card
    source = (ROOT / "src/operations_console_app.py").read_text(encoding="utf-8")
    gate = source[source.find("const update = ") : source.find("updateChooser();")]
    assert "suitability" in gate
    client = _client(console)
    posted = client.post(
        "/review",
        data={
            "snapshot_id": receipt["snapshot_id"],
            "object_id": adviseert["object_id"],
            "suitability": "",
            "documentpositie_action": "dit_klopt",
            "type_action": "dit_klopt",
            "confirmed_object_type": "recommendation",
            "eindoordeel": "goedkeuren",
            "decision": "approve",
            "recommendation_strength": "doen",
        },
    )
    assert posted.status_code == 400
    assert "geschikt" in posted.text.casefold()
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == adviseert["object_id"]
    )
    assert live.get("confirmed_object_type") != "recommendation"
    bindings = [
        row
        for row in console.object_review_bindings(receipt["snapshot_id"])
        if row.get("object_id") == adviseert["object_id"] and row.get("decision") == "approve"
    ]
    assert bindings == []
    with pytest.raises(ConsoleError, match="suitability_required"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=adviseert["object_id"],
            decision="approve",
            confirmed_object_type="recommendation",
            eindoordeel="goedkeuren",
            recommendation_strength="doen",
        )


def test_dit_klopt_reveals_sterkte_before_one_save(tmp_path: Path) -> None:
    _console, _accounts, _receipt, adviseert, html = _setup_adviseert(tmp_path)
    card = _card(html, adviseert["object_id"])
    assert 'value="dit_klopt" checked' in card
    source = (ROOT / "src/operations_console_app.py").read_text(encoding="utf-8")
    stamp_fn = source[source.find("const strengthTypes") : source.find("const updateChooser")]
    assert "dit_klopt" in stamp_fn
    assert "liveType" in stamp_fn
    assert "recommendation" in stamp_fn
    assert "confirmingProposal" in stamp_fn


def test_phase3_does_not_add_passage_register_or_gold_metrics() -> None:
    app = (ROOT / "src/operations_console_app.py").read_text(encoding="utf-8")
    kernel = (ROOT / "src/operations_console_v1.py").read_text(encoding="utf-8")
    for blob in (app, kernel):
        assert "selected_as_candidate" not in blob
        assert "coverage vs gold" not in blob
        assert "review_burden" not in blob
        assert "passage_register" not in blob
