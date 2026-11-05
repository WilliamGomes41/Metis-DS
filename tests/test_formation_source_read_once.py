"""#974 P1: one Vorming detail request reads its stored source once.

The formation problem report stays identical; only repeated deep comparison of
the same immutable source input disappears. Mutable inputs keep their
mutation detection.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import logging
from contextlib import contextmanager
from copy import deepcopy

import pytest

from tests.semantic_fixture_support import bind_fixture_selections

PARAGRAPHS = 20
SELECTED = 5


@pytest.fixture
def formation_document(tmp_path, production_console):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "source", runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming." for i in range(PARAGRAPHS)]
    bind_fixture_selections(console, [(text, "definition") for text in texts[:SELECTED]])
    sid = console.ingest(
        actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join(f"<p>{text}</p>" for text in texts) + "</body></html>").encode(),
        ingest_kind="new", title="Read once", version="1.0", date="2026-11-04", live_url="",
        class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]],
    )["snapshot_id"]
    return console, reviewer, sid


@contextmanager
def captured_diagnostics():
    from src.request_diagnostics_v1 import _LOGGER
    seen = []

    class Capture(logging.Handler):
        def emit(self, record):
            text = record.getMessage()
            if text.startswith("metis_diagnostic "):
                seen.append(json.loads(text[len("metis_diagnostic "):]))

    handler = Capture()
    _LOGGER.addHandler(handler)
    try:
        yield seen
    finally:
        _LOGGER.removeHandler(handler)


def test_frozen_source_report_equals_mutable_source_report(formation_document, monkeypatch):
    import src.vorming.formation_problems_v1 as problems
    console, reviewer, sid = formation_document
    actual = problems.collect(console, actor_id=reviewer["account_id"], snapshot_id=sid)
    monkeypatch.setattr(problems, "freeze_extraction", lambda fragments: fragments)
    expected = problems.collect(console, actor_id=reviewer["account_id"], snapshot_id=sid)
    assert actual == expected
    assert [(row["kind"], row["code"]) for row in actual["problems"]] == (
        [("source", "legacy_source_policy")] * (PARAGRAPHS - SELECTED))
    assert len({row["problem_id"] for row in actual["problems"]}) == PARAGRAPHS - SELECTED


def test_in_place_edit_of_mutable_source_selects_new_entry(formation_document):
    import src.vorming.knowledge_materialisation_v1 as materialisation
    from src.vorming.source_preparation_context_v1 import stored_extraction
    console, _, sid = formation_document
    fragments = stored_extraction(console._processing_history_envelope(sid))
    assert type(fragments) is list
    with materialisation.source_reconstruction_scope():
        first = materialisation._read_source_blocks(fragments, include_headings=True)
        assert materialisation._read_source_blocks(fragments, include_headings=True) is first
        fragments[0]["clean_text"] = "Gewijzigde bron."
        fragments[0]["raw_text"] = "Gewijzigde bron."
        changed = materialisation._read_source_blocks(fragments, include_headings=True)
    assert changed is not first
    assert any(public["text"] == "Gewijzigde bron." for public, _ in changed.values())


def test_frozen_source_reuses_its_entry_by_identity(formation_document, monkeypatch):
    import src.vorming.knowledge_materialisation_v1 as materialisation
    from src.vorming.prepared_source_views_v1 import freeze_extraction, preserve_fragments
    from src.vorming.source_preparation_context_v1 import stored_extraction
    console, _, sid = formation_document
    frozen = freeze_extraction(stored_extraction(console._processing_history_envelope(sid)))
    assert preserve_fragments(frozen) is frozen

    def no_comparison(*args, **kwargs):
        raise AssertionError("an identical immutable input was compared again")

    with materialisation.source_reconstruction_scope():
        first = materialisation._read_source_blocks(frozen, include_headings=True)
        monkeypatch.setattr(materialisation, "_source_input_snapshot", no_comparison)
        monkeypatch.setattr(type(frozen), "__eq__", no_comparison)
        monkeypatch.setattr(type(frozen), "__ne__", no_comparison)
        assert materialisation._read_source_blocks(frozen, include_headings=True) is first


def test_extraction_record_survives_freezing():
    from src.operations_console_v1 import ConsoleError
    from src.vorming.docling_contract_v1 import ExtractedFragments
    from src.vorming.prepared_source_views_v1 import FrozenList, freeze_extraction, preserve_fragments
    rows = [{"fragment_id": "f1", "raw_text": "Tekst.", "source_page": 1}]
    record = {"set_aside_pages": [{"page": 2, "reason": "image_only"}], "pages": 2}
    frozen = freeze_extraction(ExtractedFragments(deepcopy(rows), deepcopy(record)))
    assert isinstance(frozen, FrozenList)
    assert frozen == rows
    assert frozen.extraction_record == record
    frozen.extraction_record["pages"] = 3
    assert frozen.extraction_record == record
    assert preserve_fragments(frozen) is frozen
    with pytest.raises(ConsoleError, match="source_views_carrier_immutable"):
        frozen.append({})
    with pytest.raises(ConsoleError, match="source_views_carrier_immutable"):
        frozen[0]["raw_text"] = "Anders."
    plain = freeze_extraction(deepcopy(rows))
    assert plain == rows and getattr(plain, "extraction_record", None) is None
    assert freeze_extraction(None) is None


def test_source_selection_detail_reads_source_once(formation_document, production_app):
    from fastapi.testclient import TestClient
    console, _, sid = formation_document
    client = TestClient(production_app(console), base_url="https://testserver")
    login = client.post("/login", data={"username": "reviewer", "password": "fixture-only"},
                        headers={"origin": "https://testserver"}, follow_redirects=False)
    assert login.status_code in (302, 303)
    with captured_diagnostics() as seen:
        response = client.get(f"/source-selection?document={sid}")
    assert response.status_code == 200
    finished = [row for row in seen if row.get("event") == "request_finished"][-1]
    counters = finished["counters"]
    assert counters.get("source_reconstruction_built", 0) <= 2, counters
    assert counters.get("source_input_compared", 0) <= 2, counters
    assert counters.get("source_reconstruction_reused", 0) >= SELECTED, counters


@pytest.mark.parametrize("route", ["docling-retained-pdf", "decision-boom", "legacy-html"])
def test_real_extraction_routes_keep_their_report(route, tmp_path, complete_postgres, monkeypatch):
    import src.vorming.formation_problems_v1 as problems
    from src.vorming.source_preparation_context_v1 import stored_extraction
    from tests.test_a10_source_cache_repair import seed
    _, console, reviewer, sid, _, _ = seed(tmp_path, "postgres", route, monkeypatch)
    stored = stored_extraction(console._processing_history_envelope(sid))
    if route.startswith("docling"):
        assert stored.extraction_record
        assert problems.freeze_extraction(stored).extraction_record == stored.extraction_record
    elif route.startswith("legacy"):
        assert stored is None
    actual = problems.collect(console, actor_id=reviewer["account_id"], snapshot_id=sid)
    monkeypatch.setattr(problems, "freeze_extraction", lambda fragments: fragments)
    assert actual == problems.collect(console, actor_id=reviewer["account_id"], snapshot_id=sid)
