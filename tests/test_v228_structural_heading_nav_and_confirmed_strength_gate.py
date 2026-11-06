"""Protocol v2.28 first Forge wave: Blocks A+B, independently testable.

Block A — structural heading / parent-list navigation.
Block B — confirmed-type Sterkte gate.

A pass MUST NOT be treated as a B pass. B pass MUST NOT be treated as an A pass.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here. publish() stays G2-BLOCKED.
"""
from __future__ import annotations

from tests.ko_review_fixture_support import affirmative_assessment
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_v215_ingest_date_version_review_lanes import _compact_review_form

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.object_taxonomy_v1 import recommendation_strength_ui_applies
from src.operations_console_v1 import ConsoleError, OperationsConsole


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "src/operations_console_app.py"


def _console(tmp_path: Path, *, production_console) -> OperationsConsole:
    return production_console(processing_binder=bind_fixture_selections,
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


def _tiny_html(title: str = "Test richtlijn") -> bytes:
    return (
        "<!doctype html><html lang='nl'><head><title>"
        f"{title}</title></head><body>"
        f"<h1>{title}</h1>"
        "<h2>Inhoudsopgave</h2>"
        "<h3>1. Inleiding</h3>"
        "<h3>2. Doel</h3>"
        "<h3>5. Aanbevelingen</h3>"
        "<h3>5.4 Diagnostiek</h3>"
        "<h3>5.4.1 Anamnese</h3>"
        "<h3>5.4.2 Lichamelijk onderzoek</h3>"
        "<h2>1 Inleiding</h2>"
        f"<p>Dit is de inleiding van {title} in de praktijk.</p>"
        "<h2>2 Doel</h2>"
        "<p>Het doel is helder beschreven voor de zorgverlener.</p>"
        "<h2>5 Aanbevelingen</h2>"
        "<p>Bespreek incontinentie met de zorgvrager.</p>"
        "<h2>5.4 Diagnostiek</h2>"
        "<p>Gebruik een gestandaardiseerde anamnese bij iedere intake.</p>"
        "<h2>5.4.1 Anamnese</h2>"
        "<p>Vraag naar de duur van de klachten bij de zorgvrager.</p>"
        "<h2>5.4.2 Lichamelijk onderzoek</h2>"
        "<p>Verricht een gericht lichamelijk onderzoek bij twijfel.</p>"
        "<h2>Inleiding</h2>"
        "<p>Tweede inleiding in een ander deel van het document.</p>"
        "</body></html>"
    ).encode("utf-8")


def _ingest(console: OperationsConsole, accounts: dict, **kwargs) -> dict:
    defaults = dict(
        actor_id=accounts["researcher"]["account_id"],
        filename="richtlijn.html",
        data=_tiny_html(),
        content_type="text/html",
        ingest_kind="new",
        title="Test richtlijn",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/richtlijn",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )
    defaults.update(kwargs)
    from tests.semantic_fixture_support import bind_fixture_selections, legacy_recommendation_fixture
    bind_fixture_selections(console)
    receipt = console.ingest(**defaults)
    legacy_recommendation_fixture(console, receipt["snapshot_id"])
    return receipt


def _client(console: OperationsConsole, username: str='researcher.anne', *, production_app) -> TestClient:
    client = TestClient(production_app(console))
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
    content = obj.get("content") or {}
    return str(content.get("clean_text") or obj.get("clean_text") or obj.get("text") or "").strip()


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0
        self._hidden = 0
        self._hidden_stack: list[bool] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style"}:
            self._skip += 1
        hidden = "hidden" in {key for key, _value in attrs}
        self._hidden_stack.append(hidden)
        if hidden:
            self._hidden += 1
        if tag.lower() in {
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        }:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip:
            self._skip -= 1
        if self._hidden_stack and self._hidden_stack.pop():
            self._hidden = max(0, self._hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self._skip and not self._hidden:
            self.parts.append(data)


def _visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    return " ".join(parser.parts)


def _heading(
    object_id: str,
    text: str,
    *,
    role: str | None = None,
    extract_index: int = 0,
    object_type: str = "heading",
) -> dict:
    row = {
        "object_id": object_id,
        "object_type": object_type,
        "proposed_object_type": "heading",
        "confirmed_object_type": None,
        "extract_index": extract_index,
        "content": {"clean_text": text, "raw_text": text},
        "text": text,
        "clean_text": text,
        "relations": [],
    }
    if role:
        row["heading_role"] = role
    return row


def _document_headings() -> list[dict]:
    """TOC crumbs first, then body. Nearby extract would bind 5.4.1 to 2."""
    return [
        _heading("h-toc-title", "Inhoudsopgave", role="toc", extract_index=0),
        _heading("h-toc-1", "1. Inleiding", role="toc", extract_index=1),
        _heading("h-toc-2", "2. Doel", role="toc", extract_index=2),
        _heading("h-toc-5", "5. Aanbevelingen", role="toc", extract_index=3),
        _heading("h-toc-54", "5.4 Diagnostiek", role="toc", extract_index=4),
        _heading("h-toc-541", "5.4.1 Anamnese", role="toc", extract_index=5),
        _heading("h-toc-542", "5.4.2 Lichamelijk onderzoek", role="toc", extract_index=6),
        _heading("h-body-1", "1 Inleiding", role="body", extract_index=7),
        _heading("h-body-2", "2 Doel", role="body", extract_index=8),
        _heading("h-body-5", "5 Aanbevelingen", role="body", extract_index=9),
        _heading("h-body-54", "5.4 Diagnostiek", role="body", extract_index=10),
        _heading("h-body-541", "5.4.1 Anamnese", role="body", extract_index=11),
        _heading("h-body-542", "5.4.2 Lichamelijk onderzoek", role="body", extract_index=12),
        _heading("h-body-inleiding", "Inleiding", role="body", extract_index=13),
        _heading("h-body-541-dup", "5.4.1 Anamnese", role="body", extract_index=14),
    ]


# ---------------------------------------------------------------------------
# Independence — A pass is not B pass; B pass is not A pass
# ---------------------------------------------------------------------------


def test_block_a_and_block_b_are_independently_named_in_this_file() -> None:
    text = Path(__file__).read_text(encoding="utf-8")
    assert "Block A — structural heading / parent-list navigation" in text
    assert "Block B — confirmed-type Sterkte gate" in text
    assert "A pass MUST NOT be treated as a B pass" in text
    a_mark = "# === " + "ACCEPTANCE BLOCK A" + " ==="
    b_mark = "# === " + "ACCEPTANCE BLOCK B" + " ==="
    assert a_mark in text
    assert b_mark in text
    a_start = text.index(a_mark)
    b_start = text.index(b_mark)
    assert a_start < b_start
    a_chunk = text[a_start:b_start]
    b_chunk = text[b_start:]
    assert "heading_parent_list_v1" in a_chunk
    assert "recommendation_strength_ui_applies" not in a_chunk
    assert "recommendation_strength_ui_applies" in b_chunk
    assert "heading_parent_list_v1" not in b_chunk


def test_block_b_can_fail_while_block_a_helpers_are_unused() -> None:
    """Block B does not import heading_parent_list_v1. A pass cannot satisfy B."""
    proposed = {
        "object_type": "unclassified",
        "proposed_object_type": "recommendation",
        "confirmed_object_type": None,
        "heading_role": "body",
        "proposed_recommendation_strength": "doen",
    }
    assert recommendation_strength_ui_applies(proposed) is False


# === ACCEPTANCE BLOCK A ===
# Block A — structural heading / parent-list navigation
# ---------------------------------------------------------------------------


def test_block_a_marks_toc_separately_from_body_headings() -> None:
    from src.vorming.heading_parent_list_v1 import heading_role, mark_heading_roles

    rows = _document_headings()
    marked = mark_heading_roles(rows)
    by_id = {row["object_id"]: row for row in marked}
    assert heading_role(by_id["h-toc-title"], marked) == "toc"
    assert heading_role(by_id["h-toc-541"], marked) == "toc"
    assert heading_role(by_id["h-body-541"], marked) == "body"
    assert heading_role(by_id["h-body-2"], marked) == "body"
    assert {row["heading_role"] for row in marked if row["object_id"].startswith("h-toc-")} == {"toc"}
    assert {row["heading_role"] for row in marked if row["object_id"].startswith("h-body-")} == {"body"}


def test_block_a_parent_choice_list_uses_body_not_toc_and_not_naive_global_sort() -> None:
    from src.vorming.heading_parent_list_v1 import parent_choice_list

    rows = _document_headings()
    choice = parent_choice_list(rows)
    choice_ids = [row["object_id"] for row in choice]
    choice_text = [_text_of(row) for row in choice]
    assert all(not object_id.startswith("h-toc-") for object_id in choice_ids)
    assert "h-body-5" in choice_ids
    assert "h-body-54" in choice_ids
    assert "h-body-541" in choice_ids
    assert "h-body-542" in choice_ids
    assert choice_ids.index("h-body-5") < choice_ids.index("h-body-54")
    assert choice_ids.index("h-body-54") < choice_ids.index("h-body-541")
    assert choice_ids.index("h-body-541") < choice_ids.index("h-body-542")
    naive = sorted(rows, key=lambda row: _text_of(row))
    naive_ids = [row["object_id"] for row in naive]
    assert choice_ids != naive_ids
    assert "Inhoudsopgave" not in choice_text


def test_block_a_near_duplicates_leave_choice_list_only_freeze_anchors_stay() -> None:
    from src.vorming.heading_parent_list_v1 import freeze_heading_anchors, parent_choice_list

    rows = _document_headings()
    freeze = freeze_heading_anchors(rows)
    freeze_ids = {row["object_id"] for row in freeze}
    assert "h-toc-541" in freeze_ids
    assert "h-body-541" in freeze_ids
    assert "h-body-541-dup" in freeze_ids
    assert len(freeze) == len(rows)
    choice_ids = [row["object_id"] for row in parent_choice_list(rows)]
    assert "h-body-541" in choice_ids
    assert "h-body-541-dup" not in choice_ids
    assert "h-toc-541" not in choice_ids


def test_block_a_unnumbered_headings_keep_extract_order_fallback() -> None:
    from src.vorming.heading_parent_list_v1 import parent_choice_list

    rows = [
        _heading("h-a", "Inleiding", role="body", extract_index=0),
        _heading("h-b", "5 Aanbevelingen", role="body", extract_index=1),
        _heading("h-c", "5.4 Diagnostiek", role="body", extract_index=2),
        _heading("h-d", "Slot", role="body", extract_index=3),
    ]
    choice_ids = [row["object_id"] for row in parent_choice_list(rows)]
    assert choice_ids.index("h-a") < choice_ids.index("h-b")
    assert choice_ids.index("h-b") < choice_ids.index("h-c")
    assert choice_ids.index("h-c") < choice_ids.index("h-d")


def test_block_a_invalid_nearby_parent_must_not_be_default_or_bind() -> None:
    from src.vorming.heading_parent_list_v1 import (
        default_structural_parent,
        is_structurally_valid_parent,
        parent_proposal_may_bind,
    )

    rows = _document_headings()
    child = next(row for row in rows if row["object_id"] == "h-body-541")
    nearby_two = next(row for row in rows if row["object_id"] == "h-body-2")
    structural = next(row for row in rows if row["object_id"] == "h-body-54")
    ancestor_five = next(row for row in rows if row["object_id"] == "h-body-5")
    assert is_structurally_valid_parent(child, nearby_two) is False
    assert is_structurally_valid_parent(child, structural) is True
    assert is_structurally_valid_parent(child, ancestor_five) is True
    assert parent_proposal_may_bind(child, nearby_two, rows) is False
    assert parent_proposal_may_bind(child, structural, rows) is True
    default = default_structural_parent(child, rows)
    assert default is not None
    assert default["object_id"] == "h-body-54"
    assert default["object_id"] != "h-body-2"


def test_block_a_confirm_relations_rejects_invalid_heading_parent(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rows = console._load_objects(receipt["snapshot_id"])
    child = {
        "object_id": "planted-541",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "5.4.1 Anamnese", "raw_text": "5.4.1 Anamnese"},
        "heading_role": "body",
        "relations": [
            {
                "relation_type": "child",
                "target_object_id": "planted-2",
                "confirmed": False,
            }
        ],
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    parent_two = {
        "object_id": "planted-2",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "2 Doel", "raw_text": "2 Doel"},
        "heading_role": "body",
        "relations": [],
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    rows.extend([child, parent_two])
    console._save_objects(receipt["snapshot_id"], rows)
    with pytest.raises(ConsoleError, match="invalid_parent_structure"):
        console.confirm_relations(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id="planted-541",
            relations=[{"relation_type": "child", "target_object_id": "planted-2"}],
        )
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == "planted-541"
    )
    confirmed = live.get("confirmed_relations") or []
    assert not any(
        row.get("target_object_id") == "planted-2" and row.get("confirmed")
        for row in confirmed
    )


def test_block_a_confirm_child_relation_updates_canonical_parent(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rows = console._load_objects(receipt["snapshot_id"])
    parent = {
        "object_id": "planted-54",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "5.4 Diagnostiek", "raw_text": "5.4 Diagnostiek"},
        "heading_role": "body",
        "relations": [],
        "confirmed_relations": [],
        "parent_object_id": None,
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    child = {
        **parent,
        "object_id": "planted-541",
        "content": {"clean_text": "5.4.1 Anamnese", "raw_text": "5.4.1 Anamnese"},
    }
    rows.extend([parent, child])
    console._save_objects(receipt["snapshot_id"], rows)

    confirmed = console.confirm_relations(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id="planted-541",
        relations=[{"relation_type": "child", "target_object_id": "planted-54"}],
    )
    assert confirmed["parent_object_id"] == "planted-54"

    cleared = console.confirm_relations(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id="planted-541",
        relations=[],
    )
    assert cleared["parent_object_id"] is None


def test_block_a_confirm_parent_relation_updates_child_record(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rows = console._load_objects(receipt["snapshot_id"])
    parent = {
        "object_id": "inverse-54",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "5.4 Diagnostiek", "raw_text": "5.4 Diagnostiek"},
        "heading_role": "body",
        "relations": [],
        "confirmed_relations": [],
        "parent_object_id": None,
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    child = {
        **parent,
        "object_id": "inverse-541",
        "content": {"clean_text": "5.4.1 Anamnese", "raw_text": "5.4.1 Anamnese"},
    }
    rows.extend([parent, child])
    console._save_objects(receipt["snapshot_id"], rows)

    console.confirm_relations(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id="inverse-54",
        relations=[{"relation_type": "parent", "target_object_id": "inverse-541"}],
    )
    live_child = next(
        row
        for row in console.snapshot_objects(receipt["snapshot_id"])
        if row["object_id"] == "inverse-541"
    )
    assert live_child["parent_object_id"] == "inverse-54"


def test_block_a_clearing_stale_parent_relation_preserves_new_parent(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rows = console._load_objects(receipt["snapshot_id"])
    ancestor = {
        "object_id": "reparent-5",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "5 Onderzoek", "raw_text": "5 Onderzoek"},
        "heading_role": "body",
        "relations": [],
        "confirmed_relations": [],
        "parent_object_id": None,
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    parent = {
        **ancestor,
        "object_id": "reparent-54",
        "content": {"clean_text": "5.4 Diagnostiek", "raw_text": "5.4 Diagnostiek"},
    }
    child = {
        **ancestor,
        "object_id": "reparent-541",
        "content": {"clean_text": "5.4.1 Anamnese", "raw_text": "5.4.1 Anamnese"},
    }
    rows.extend([ancestor, parent, child])
    console._save_objects(receipt["snapshot_id"], rows)

    console.confirm_relations(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id="reparent-54",
        relations=[{"relation_type": "parent", "target_object_id": "reparent-541"}],
    )
    console.confirm_relations(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id="reparent-541",
        relations=[{"relation_type": "child", "target_object_id": "reparent-5"}],
    )

    console.confirm_relations(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id="reparent-54",
        relations=[],
    )
    live_child = next(
        row
        for row in console.snapshot_objects(receipt["snapshot_id"])
        if row["object_id"] == "reparent-541"
    )
    assert live_child["parent_object_id"] == "reparent-5"


def test_block_a_console_parent_list_is_body_structure_onderzoekers_taal(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    target = next(obj for obj in objects if "Bespreek" in _text_of(obj) or obj.get("object_type") == "heading")
    from src.operations_console_app import _heading_chooser
    html = _heading_chooser(target, console.snapshot_objects(receipt['snapshot_id']), receipt['snapshot_id'])
    visible = _visible_text(html)
    assert "data-parent-choice-list" in html
    assert "hoofdtekst" in html.lower() or "documentlichaam" in visible.lower()
    assert 'data-heading-role="body"' in html
    assert "envelope" not in html.lower()
    toc_choice = re.search(
        r'data-parent-choice-list[\s\S]*data-heading-role="toc"',
        html,
    )
    assert toc_choice is None
    chooser = re.search(
        r'data-heading-chooser[\s\S]*?</div>',
        html,
    )
    if chooser:
        assert "Inhoudsopgave" not in chooser.group(0)
        assert 'data-heading-role="toc"' not in chooser.group(0)
    assert "checked" not in html or "planted-2" not in html


def test_block_a_toc_crumb_must_not_bind_as_structural_parent() -> None:
    from src.vorming.heading_parent_list_v1 import (
        is_structurally_valid_parent,
        parent_proposal_may_bind,
    )

    rows = _document_headings()
    child = next(row for row in rows if row["object_id"] == "h-body-541")
    toc_parent = next(row for row in rows if row["object_id"] == "h-toc-54")
    body_parent = next(row for row in rows if row["object_id"] == "h-body-54")
    assert is_structurally_valid_parent(child, toc_parent, rows) is False
    assert is_structurally_valid_parent(child, body_parent, rows) is True
    assert parent_proposal_may_bind(child, toc_parent, rows) is False
    assert parent_proposal_may_bind(child, body_parent, rows) is True


def test_block_a_confirm_relations_rejects_toc_heading_as_parent(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rows = console._load_objects(receipt["snapshot_id"])
    child = {
        "object_id": "planted-body-541",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "5.4.1 Anamnese", "raw_text": "5.4.1 Anamnese"},
        "heading_role": "body",
        "relations": [],
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    toc_parent = {
        "object_id": "planted-toc-54",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "5.4 Diagnostiek", "raw_text": "5.4 Diagnostiek"},
        "heading_role": "toc",
        "relations": [],
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    rows.extend([child, toc_parent])
    console._save_objects(receipt["snapshot_id"], rows)
    with pytest.raises(ConsoleError, match="invalid_parent_structure"):
        console.confirm_relations(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id="planted-body-541",
            relations=[{"relation_type": "child", "target_object_id": "planted-toc-54"}],
        )


def test_block_a_toc_inference_ends_without_exact_repeated_title() -> None:
    from src.vorming.heading_parent_list_v1 import heading_role, mark_heading_roles, parent_choice_list

    page_suffix_rows = [
        _heading("h-toc-title", "Inhoudsopgave", extract_index=0),
        _heading("h-toc-1", "1 Intro .... 3", extract_index=1),
        _heading("h-toc-2", "2 Doel .... 5", extract_index=2),
        _heading("h-toc-5", "5 Aanbevelingen .... 12", extract_index=3),
        _heading("h-toc-54", "5.4 Diagnostiek .... 14", extract_index=4),
        _heading("h-body-1", "1 Intro", extract_index=5),
        _heading("h-body-2", "2 Doel", extract_index=6),
        _heading("h-body-5", "5 Aanbevelingen", extract_index=7),
        _heading("h-body-54", "5.4 Diagnostiek", extract_index=8),
        _heading("h-body-541", "5.4.1 Anamnese", extract_index=9),
    ]
    marked = mark_heading_roles(page_suffix_rows)
    by_id = {row["object_id"]: row for row in marked}
    assert heading_role(by_id["h-toc-1"], marked) == "toc"
    assert heading_role(by_id["h-toc-54"], marked) == "toc"
    assert heading_role(by_id["h-body-1"], marked) == "body"
    assert heading_role(by_id["h-body-54"], marked) == "body"
    assert heading_role(by_id["h-body-541"], marked) == "body"
    choice_ids = [row["object_id"] for row in parent_choice_list(page_suffix_rows)]
    assert "h-body-5" in choice_ids
    assert "h-body-54" in choice_ids
    assert "h-toc-54" not in choice_ids

    omitted_first = [
        _heading("h-toc-title", "Inhoudsopgave", extract_index=0),
        _heading("h-toc-2", "2 Doel .... 5", extract_index=1),
        _heading("h-toc-5", "5 Aanbevelingen .... 12", extract_index=2),
        _heading("h-body-1", "1 Inleiding", extract_index=3),
        _heading("h-body-2", "2 Doel", extract_index=4),
        _heading("h-body-5", "5 Aanbevelingen", extract_index=5),
    ]
    omitted_marked = mark_heading_roles(omitted_first)
    omitted_by_id = {row["object_id"]: row for row in omitted_marked}
    assert heading_role(omitted_by_id["h-toc-2"], omitted_marked) == "toc"
    assert heading_role(omitted_by_id["h-body-1"], omitted_marked) == "body"
    assert heading_role(omitted_by_id["h-body-5"], omitted_marked) == "body"
    omitted_choice = [row["object_id"] for row in parent_choice_list(omitted_first)]
    assert "h-body-1" in omitted_choice
    assert "h-toc-2" not in omitted_choice


def test_block_a_parent_relation_uses_current_object_as_parent(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rows = console._load_objects(receipt["snapshot_id"])
    parent_heading = {
        "object_id": "planted-54",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "5.4 Diagnostiek", "raw_text": "5.4 Diagnostiek"},
        "heading_role": "body",
        "relations": [],
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    child_heading = {
        "object_id": "planted-541",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "5.4.1 Anamnese", "raw_text": "5.4.1 Anamnese"},
        "heading_role": "body",
        "relations": [],
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    rows.extend([parent_heading, child_heading])
    console._save_objects(receipt["snapshot_id"], rows)
    bound = console.confirm_relations(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id="planted-54",
        relations=[{"relation_type": "parent", "target_object_id": "planted-541"}],
    )
    assert any(
        row.get("relation_type") == "parent" and row.get("target_object_id") == "planted-541"
        for row in (bound.get("confirmed_relations") or [])
    )
    with pytest.raises(ConsoleError, match="invalid_parent_structure"):
        console.confirm_relations(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id="planted-541",
            relations=[{"relation_type": "parent", "target_object_id": "planted-54"}],
        )


def test_block_a_parent_choice_rows_are_actionable(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rows = console._load_objects(receipt["snapshot_id"])
    parent = {
        "object_id": "planted-body-54",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "5.4 Diagnostiek (hoofdtekst)", "raw_text": "5.4 Diagnostiek (hoofdtekst)"},
        "heading_role": "body",
        "relations": [],
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    child = {
        "object_id": "planted-body-541",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "object_version": "1.0",
        "content": {"clean_text": "5.4.1 Anamnese (hoofdtekst)", "raw_text": "5.4.1 Anamnese (hoofdtekst)"},
        "heading_role": "body",
        "relations": [],
        "governance": {"review_track": "clinical", "validation_status": "needs_review"},
        "provenance": {"source_fragments": []},
    }
    rows.extend([parent, child])
    console._save_objects(receipt["snapshot_id"], rows)
    from src.operations_console_app import _heading_chooser
    html = _heading_chooser(child, console.snapshot_objects(receipt['snapshot_id']), receipt['snapshot_id'])
    assert "data-parent-choice-list" in html
    assert not re.search(
        r'data-parent-choice-list[\s\S]*href="/review\?document=',
        html,
    )
    assert f'value="{parent["object_id"]}"' in html
    assert 'name="parent_choice"' in html
    assert 'type="radio"' in html
    assert f'value="{parent["object_id"]}"' in html
    assert "Relatie bevestigen" not in html
    posted = _client(console, production_app=production_app).post(
        "/review/relations",
        data={
            "snapshot_id": receipt["snapshot_id"],
            "object_id": child["object_id"],
            "parent_choice": parent["object_id"],
        },
        follow_redirects=False,
    )
    assert posted.status_code in {303, 200}
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == child["object_id"]
    )
    assert any(
        row.get("target_object_id") == parent["object_id"]
        and row.get("relation_type") == "child"
        for row in (live.get("confirmed_relations") or [])
    )


def test_block_a_does_not_open_publish_or_recreate_handoff() -> None:
    assert not (ROOT / "HANDOFF.md").exists()
    source = (ROOT / "src/operations_console_v1.py").read_text(encoding="utf-8")
    assert '"g2": "BLOCKED"' in source
    # Since D6b the publish refusal lives only in the PostgreSQL publication console.
    durable = (ROOT / "src/publication/durable_publication_console_v1.py").read_text(encoding="utf-8")
    assert '"status":"BLOCKED"' in durable and '"g2":considered.get("g2","BLOCKED")' in durable


# === ACCEPTANCE BLOCK B ===
# Block B — confirmed-type Sterkte gate
# ---------------------------------------------------------------------------


def test_block_b_proposed_recommendation_must_not_activate_sterkte() -> None:
    proposed = {
        "object_type": "unclassified",
        "proposed_object_type": "recommendation",
        "confirmed_object_type": None,
        "proposed_recommendation_strength": "doen",
    }
    heading = {
        "object_type": "heading",
        "proposed_object_type": "heading",
        "confirmed_object_type": None,
    }
    tools = {
        "object_type": "unclassified",
        "proposed_object_type": None,
        "confirmed_object_type": None,
        "content": {"clean_text": "Tools"},
    }
    proposed_outcome = {
        "object_type": "unclassified",
        "proposed_object_type": "outcome",
        "confirmed_object_type": None,
        "proposed_recommendation_strength": "overweeg",
    }
    assert recommendation_strength_ui_applies(proposed) is False
    assert recommendation_strength_ui_applies(heading) is False
    assert recommendation_strength_ui_applies(tools) is False
    assert recommendation_strength_ui_applies(proposed_outcome) is False


def test_block_b_sterkte_only_on_stored_or_confirmed_recommendation_or_outcome() -> None:
    confirmed_rec = {
        "object_type": "recommendation",
        "proposed_object_type": "heading",
        "confirmed_object_type": "recommendation",
    }
    stored_rec = {
        "object_type": "recommendation",
        "proposed_object_type": "recommendation",
        "confirmed_object_type": None,
    }
    confirmed_outcome = {
        "object_type": "outcome",
        "proposed_object_type": "outcome",
        "confirmed_object_type": "outcome",
    }
    confirmed_heading = {
        "object_type": "heading",
        "proposed_object_type": "recommendation",
        "confirmed_object_type": "heading",
    }
    assert recommendation_strength_ui_applies(confirmed_rec) is True
    assert recommendation_strength_ui_applies(stored_rec) is True
    assert recommendation_strength_ui_applies(confirmed_outcome) is True
    assert recommendation_strength_ui_applies(confirmed_heading) is False


def test_block_b_console_hides_sterkte_on_proposed_recommendation_until_confirm(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rec = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if "Bespreek" in _text_of(obj)
    )
    assert rec.get("confirmed_object_type") in {None, ""}
    assert rec.get("proposed_object_type") == "recommendation" or "Bespreek" in _text_of(rec)
    html = _client(console, production_app=production_app).get(
        f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}"
    ).text
    visible = _visible_text(html)
    assert "Sterkte van de aanbeveling" not in visible
    assert "envelope" not in html.lower()
    assert "Documenten" in html
    assert "Documentenhiërarchie" not in html
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
        decision="approve",
        confirmed_object_type="recommendation",
        recommendation_strength="doen",
        assessment=affirmative_assessment(), evidence_not_applicable=True,
    )
    confirmed_html = _client(console, production_app=production_app).get(
        f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}"
    ).text
    assert 'Sterkte van de aanbeveling: DOEN' in confirmed_html
    assert not any(item.get('name') == 'recommendation_strength' for item in _compact_review_form(confirmed_html)['inputs'])
    assert next(row for row in console.snapshot_objects(receipt['snapshot_id']) if row['object_id'] == rec['object_id'])['confirmed_recommendation_strength'] == 'doen'


def test_compact_review_requires_three_explicit_answers_without_strength_mutation(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rec = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if "Bespreek" in _text_of(obj)
    )
    client = _client(console, production_app=production_app)
    page = client.get(f'/review?document={receipt["snapshot_id"]}&object={rec["object_id"]}')
    html = page.text
    form = _compact_review_form(html)
    radios = [item for item in form['inputs'] if item.get('type') == 'radio']
    assert len(radios) == 6
    assert all('checked' not in item for item in radios)
    assert {item['name'] for item in radios} == {'applicable', 'complete', 'placed_correctly'}
    assert not any(item.get('name') in {'type_action', 'recommendation_strength'} for item in form['inputs'])
    assert 'data-ko-assessment-form' in html
    from tests.test_ko_new_pages import compact_submission
    before = console.snapshot_objects(receipt['snapshot_id'])
    posted = {**compact_submission(page), 'complete': ''}
    refused = client.post('/review', data=posted, follow_redirects=False)
    assert refused.status_code == 400
    assert console.snapshot_objects(receipt['snapshot_id']) == before


def test_block_b_type_change_away_clears_active_strength_audit_may_keep(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rec = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if "Bespreek" in _text_of(obj)
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
        decision="approve",
        confirmed_object_type="recommendation",
        recommendation_strength="doen",
        assessment=affirmative_assessment(), evidence_not_applicable=True,
    )
    after_confirm = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == rec["object_id"]
    )
    assert after_confirm.get("confirmed_recommendation_strength") == "doen"
    history_before = [
        row
        for row in console._load_objects(receipt["snapshot_id"])
        if row["object_id"] == rec["object_id"]
    ]
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
        confirmed_object_type="explanation",
    )
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == rec["object_id"]
    )
    assert live.get("confirmed_object_type") == "explanation"
    assert live.get("confirmed_recommendation_strength") in {None, ""}
    history = [
        row
        for row in console._load_objects(receipt["snapshot_id"])
        if row["object_id"] == rec["object_id"]
    ]
    assert len(history) >= len(history_before)
    assert any(row.get("confirmed_recommendation_strength") == "doen" for row in history)


def test_block_b_known_legacy_strength_is_shown_and_confirmed_by_three_answers(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rec = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if "Bespreek" in _text_of(obj)
    )
    rows = console._load_objects(receipt["snapshot_id"])
    for row in rows:
        if row["object_id"] == rec["object_id"]:
            row["proposed_recommendation_strength"] = "doen"
            row["proposed_object_type"] = "recommendation"
            row["confirmed_object_type"] = None
            if row.get("object_type") == "recommendation":
                row["object_type"] = "unclassified"
    from tests.semantic_fixture_support import install_fixture_history
    install_fixture_history(console, receipt["snapshot_id"], rows)
    planted = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == rec["object_id"]
    )
    assert recommendation_strength_ui_applies(planted) is False
    client = _client(console, production_app=production_app)
    page = client.get(f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}")
    form = _compact_review_form(page.text)
    assert 'Sterkte van de aanbeveling: DOEN — dit moet de zorgverlener doen.' in _visible_text(page.text)
    assert form['attrs']['data-can-approve'] == 'true'
    assert page.text.count('class="ko-question"') == 3
    assert not any(item.get('name') in {'recommendation_strength', 'recommendation_direction',
        'recommendation_strength_level', 'confirmed_object_type', 'type_action'} for item in form['inputs'])
    # Reading the known proposal does not itself confirm a type or invent modern semantics.
    assert console._current_object(receipt['snapshot_id'], rec['object_id']) == planted
    assert not planted.get('confirmed_object_type')
    assert 'proposed_recommendation_semantics' not in planted
    assert 'confirmed_recommendation_semantics' not in planted

    from tests.test_ko_new_pages import compact_submission
    saved = client.post('/review', data=compact_submission(page), follow_redirects=False)
    assert saved.status_code == 303, saved.text
    confirmed = console._current_object(receipt['snapshot_id'], rec['object_id'])
    assert confirmed['confirmed_object_type'] == 'recommendation'
    assert confirmed['confirmed_recommendation_strength'] == 'doen'
    assert 'proposed_recommendation_semantics' not in confirmed
    assert 'confirmed_recommendation_semantics' not in confirmed


@pytest.mark.parametrize('invalid_modern_record', [False, True])
def test_compact_review_cannot_approve_unknown_or_invalid_modern_strength(
    tmp_path: Path, invalid_modern_record, *, production_app, production_console,
) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rec = next(obj for obj in _non_document(console.snapshot_objects(receipt['snapshot_id']))
               if 'Bespreek' in _text_of(obj))
    if invalid_modern_record:
        rows = console._load_objects(receipt['snapshot_id'])
        row = next(row for row in rows if row['object_id'] == rec['object_id'])
        # An explicitly invalid modern record cannot fall back to an otherwise
        # known legacy stamp. This is adversarial input, not source evidence.
        row['proposed_recommendation_strength'] = 'doen'
        row['proposed_recommendation_semantics'] = {}
        from tests.semantic_fixture_support import install_fixture_history
        install_fixture_history(console, receipt['snapshot_id'], rows)
    client = _client(console, production_app=production_app)
    page = client.get(f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}")
    assert _compact_review_form(page.text)['attrs']['data-can-approve'] == 'false'
    assert 'Sterkte van de aanbeveling: DOEN' not in _visible_text(page.text)
    from tests.test_ko_new_pages import compact_submission
    from tests.test_review_command_bounded_http_v1 import physical_state
    before = physical_state(console, receipt['snapshot_id'])
    refused = client.post('/review', data=compact_submission(page), follow_redirects=False)
    assert refused.status_code == 400
    assert physical_state(console, receipt['snapshot_id']) == before


def test_block_b_confirm_object_type_clears_active_strength(tmp_path: Path, *, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rec = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if "Bespreek" in _text_of(obj)
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
        decision="approve",
        confirmed_object_type="recommendation",
        recommendation_strength="doen",
        assessment=affirmative_assessment(), evidence_not_applicable=True,
    )
    after_confirm = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == rec["object_id"]
    )
    assert after_confirm.get("confirmed_recommendation_strength") == "doen"
    history_before = [
        row
        for row in console._load_objects(receipt["snapshot_id"])
        if row["object_id"] == rec["object_id"]
    ]
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
        confirmed_object_type="explanation",
    )
    live = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == rec["object_id"]
    )
    assert live.get("confirmed_object_type") == "explanation"
    assert live.get("confirmed_recommendation_strength") in {None, ""}
    history = [
        row
        for row in console._load_objects(receipt["snapshot_id"])
        if row["object_id"] == rec["object_id"]
    ]
    assert len(history) >= len(history_before)
    assert any(row.get("confirmed_recommendation_strength") == "doen" for row in history)


def test_block_b_hidden_sterkte_select_is_disabled_until_type_confirm(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rec = next(
        obj
        for obj in _non_document(console.snapshot_objects(receipt["snapshot_id"]))
        if "Bespreek" in _text_of(obj)
    )
    html = _client(console, production_app=production_app).get(
        f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}"
    ).text
    form = _compact_review_form(html)
    assert not any(item.get('name') == 'recommendation_strength' for item in form['inputs'])
    assert not re.search(r'<select\b[^>]*name="recommendation_strength"', html)
    assert html.count('class="ko-question"') == 3
    current = next(row for row in console.snapshot_objects(receipt['snapshot_id']) if row['object_id'] == rec['object_id'])
    assert not current.get('confirmed_object_type')
    assert recommendation_strength_ui_applies(current) is False


def test_block_b_publish_stays_g2_blocked_and_handoff_absent(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    result = console.publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert result["status"] == "BLOCKED"
    assert result["g2"] == "BLOCKED"
    assert result.get("cutover") is False
    html = _client(console, "publisher.carla", production_app=production_app).get("/publish").text
    assert '<h1>Publiceren</h1>' in html
    assert "data-publish-form" not in html or "duurzame opslag" in html.lower()
    assert not (ROOT / "HANDOFF.md").exists()
