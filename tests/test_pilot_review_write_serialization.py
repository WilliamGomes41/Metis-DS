"""Pilot review-write serialization (lost local tip reconstruction).

Four MUST promises:

1. Full store mutations serialize — one complete store transaction at a
   time (objects/envelopes/bindings/ledger as applicable); no
   half-overlapping multi-file writes.
2. Conflict MUST NOT roll back another writer's already-committed work —
   loser/stale path rejects or reopens own action; winner stays on disk.
3. Form content + revision read together — GET→POST form-bound revision
   (extend #122); NOT ``threading.local``.
4. Heavy ingest MUST leave other reviewers available — keep wave-2
   ``asyncio.to_thread`` + limits; MUST NOT hold a global exclusive lock
   across ingest extract that blocks review POSTs.

#122 form-revision + promote copy-then-commit and #125 topology bound
stay. PROTOCOL.md and docs/PROTOCOL_V2_* are not edited. publish() stays
G2-BLOCKED.

# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import asyncio
import json
import re
import threading
import time
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport

from src.operations_console_app import create_console_app
from src.operations_console_v1 import (
    SNAPSHOT_OBJECT_WRITE_CONFLICT,
    ConsoleError,
    OperationsConsole,
)


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
ANNE_COMMENT = "G1-pilot-serial-anne-comment-42"
BERT_COMMENT = "G1-pilot-serial-bert-comment-99"
ANNE_SUIT = "geen_kenniseenheid"
BERT_SUIT = "samenvoegen"
RACED_MARKER = "raced-writer-generation-bert"

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_beschikbaarheid,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _console(tmp_path: Path, *, production_console) -> OperationsConsole:
    return production_console(processing_binder=bind_fixture_selections,
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def _restart(tmp_path: Path, *, production_console) -> OperationsConsole:
    return _console(tmp_path, production_console=production_console)


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
    second = console.create_account(
        username="researcher.dirk",
        password="dirk-secret",
        roles=("researcher", "reviewer"),
        display_name="Dirk Onderzoeker",
    )
    return {"researcher": researcher, "reviewer": reviewer, "second": second}


def _ingest(
    console: OperationsConsole,
    accounts: dict,
    *,
    title: str = "Continentie fixture",
    version: str = "1.0",
) -> dict:
    return console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="continentie.html",
        data=HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title=title,
        version=version,
        date="2025-04-01",
        live_url="https://example.test/continentie",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )


def _content_rows(console: OperationsConsole, snapshot_id: str) -> list[dict]:
    rows = [
        row
        for row in console.snapshot_objects(snapshot_id)
        if row.get("object_type") != "document"
    ]
    assert len(rows) >= 2
    return rows


def _disk_envelopes(console):
    return {row['snapshot_id']:row for row in console.workflow_document_store.list_envelopes()}


def _client(console: OperationsConsole, username: str, *, production_app) -> TestClient:
    client = TestClient(production_app(console))
    passwords = {
        "researcher.anne": "anne-secret",
        "reviewer.bert": "bert-secret",
        "researcher.dirk": "dirk-secret",
    }
    client.post("/login", data={"username": username, "password": passwords[username]})
    return client


def _hidden(html: str, name: str) -> str:
    match = re.search(
        rf'<input[^>]*name="{re.escape(name)}"[^>]*value="([^"]*)"',
        html,
    )
    if not match:
        match = re.search(
            rf'<input[^>]*value="([^"]*)"[^>]*name="{re.escape(name)}"',
            html,
        )
    return match.group(1) if match else ""


def _radio_checked(html: str, name: str, value: str) -> bool:
    pattern = (
        rf'<input[^>]*name="{re.escape(name)}"[^>]*value="{re.escape(value)}"[^>]*>'
        rf'|<input[^>]*value="{re.escape(value)}"[^>]*name="{re.escape(name)}"[^>]*>'
    )
    for match in re.finditer(pattern, html):
        if re.search(r"\bchecked\b", match.group(0)):
            return True
    return False


def _review_payload(
    snapshot_id: str,
    object_id: str,
    *,
    snapshot_revision: str,
    suitability: str,
    comment: str,
) -> dict[str, str]:
    return {
        "snapshot_id": snapshot_id,
        "object_id": object_id,
        "snapshot_revision": snapshot_revision,
        "suitability": suitability,
        "documentpositie_action": "dit_klopt",
        "type_action": "dit_klopt",
        "eindoordeel": "later_beoordelen",
        "comment": comment,
        "proposed_correction": "",
    }


def _open_review_form(
    client: TestClient,
    snapshot_id: str,
    object_id: str,
) -> tuple[str, str]:
    opened = client.get(f"/review?document={snapshot_id}&object={object_id}")
    assert opened.status_code == 200
    assert "data-review-form" in opened.text
    revision = _hidden(opened.text, "snapshot_revision")
    assert revision, "review GET MUST embed snapshot_revision on the edit form"
    return opened.text, revision


def _ingest_form(accounts: dict, *, extra: dict | None = None) -> dict[str, str]:
    data = {
        "ingest_kind": "new",
        "title": "Tweede document tijdens extract",
        "version": "2.0",
        "date": "2025-04-02",
        "live_url": "https://example.test/continentie-2",
        "class_": "richtlijn",
        "family": "continentie",
        "named_reviewers": accounts["reviewer"]["account_id"],
        "review_option": "one_other",
        "review_reviewers": accounts["reviewer"]["account_id"],
    }
    if extra:
        data.update(extra)
    return data


async def _login(client: httpx.AsyncClient, username: str, password: str) -> None:
    response = await client.post("/login", data={"username": username, "password": password})
    assert response.status_code in {200, 303}


def test_conflict_does_not_rollback_winner_already_committed_work(tmp_path: Path, *, production_console) -> None:
    """Promise 2: loser/stale path MUST NOT undo the winner on disk."""
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    snap_a = _ingest(console, accounts, title="Winner snapshot", version="1.0")["snapshot_id"]
    snap_b = _ingest(console, accounts, title="Loser snapshot", version="1.1")["snapshot_id"]
    stale_envelopes = deepcopy(_disk_envelopes(console))
    assert stale_envelopes[snap_a]["class"] == "richtlijn"
    console.promote_class(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=snap_a,
        new_class="handreiking",
    )
    assert _disk_envelopes(console)[snap_a]["class"] == "handreiking"

    rows_b = console._load_objects(snap_b)
    with pytest.raises(ConsoleError) as caught:
        console._commit_prepared_store(
            objects=(snap_b, rows_b),
            envelopes=stale_envelopes,
            expected_revision="stale-conflict-pin",
        )
    assert caught.value.code == SNAPSHOT_OBJECT_WRITE_CONFLICT
    assert _disk_envelopes(console)[snap_a]["class"] == "handreiking"

    console._commit_prepared_store(
        objects=(snap_b, rows_b),
        envelopes=stale_envelopes,
    )
    disk = _disk_envelopes(console)
    assert disk[snap_a]["class"] == "handreiking"
    assert snap_b in disk
    restarted = _restart(tmp_path, production_console=production_console)
    assert restarted._envelopes[snap_a]["class"] == "handreiking"
    assert _disk_envelopes(restarted)[snap_a]["class"] == "handreiking"


def test_review_form_content_and_revision_are_read_together(tmp_path: Path, monkeypatch, *, production_app, production_console) -> None:
    """Promise 3: a concurrent commit cannot mix new content with an old pin."""
    from concurrent.futures import ThreadPoolExecutor
    from src.review_passage_read_v1 import PREFIX, resolve_review_revision
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    snapshot_id = _ingest(console, accounts)["snapshot_id"]
    target = _content_rows(console, snapshot_id)[0]
    original_revision = console.objects_revision(snapshot_id)
    other = _console(tmp_path, production_console=production_console)
    real_histories = console.workflow_document_store.review_object_histories
    raced, captured = [], []

    def commit_other_writer():
        loaded = other._load_objects(snapshot_id)
        for row in loaded:
            if row["object_id"] == target["object_id"]:
                row["reliability_marker"] = RACED_MARKER
                row.setdefault("metadata", {}).setdefault("review_passage", {})["suitability"] = BERT_SUIT
        other._save_objects(snapshot_id, loaded)

    def raced_histories(snapshot_id_arg, object_ids):
        if not raced:
            # The detail already captured its document generation. A different
            # thread/connection commits BEFORE the object's SQL read, so this
            # fails if the production read loses repeatable-read isolation.
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(commit_other_writer).result(timeout=10)
            raced.append(True)
        rows = real_histories(snapshot_id_arg, object_ids)
        captured.extend(deepcopy(rows))
        return rows

    monkeypatch.setattr(console.workflow_document_store, 'review_object_histories', raced_histories)
    client = _client(console, "researcher.anne", production_app=production_app)
    body, revision = _open_review_form(client, snapshot_id, target["object_id"])
    live_revision = console.objects_revision(snapshot_id)
    assert raced and live_revision != original_revision
    assert revision.startswith(PREFIX)
    assert any(row["object_id"] == target["object_id"] for row in captured)
    assert all(row.get("reliability_marker") != RACED_MARKER for row in captured)
    assert RACED_MARKER not in body and not _radio_checked(body, "suitability", BERT_SUIT)
    with pytest.raises(ConsoleError) as caught:
        resolve_review_revision(console, snapshot_id, revision)
    assert caught.value.code == SNAPSHOT_OBJECT_WRITE_CONFLICT

    before = deepcopy(console.snapshot_objects(snapshot_id))
    events = console.workflow_review_store.read_events()
    response = client.post('/review', data=_review_payload(snapshot_id, target["object_id"],
        snapshot_revision=revision, suitability=ANNE_SUIT, comment=ANNE_COMMENT), follow_redirects=False)
    assert response.status_code == 409
    assert console.snapshot_objects(snapshot_id) == before
    assert console.workflow_review_store.read_events() == events
    _body, fresh = _open_review_form(client, snapshot_id, target["object_id"])
    assert resolve_review_revision(console, snapshot_id, fresh) == live_revision
    assert any(row.get("reliability_marker") == RACED_MARKER for row in captured)


def test_get_form_revision_is_not_taken_from_threading_local(tmp_path: Path, *, production_app, production_console) -> None:
    """Promise 3: form pin is durable, not TLS / worker reuse."""
    from src.review_passage_read_v1 import PREFIX, resolve_review_revision
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    snapshot_id = _ingest(console, accounts)["snapshot_id"]
    target = _content_rows(console, snapshot_id)[0]
    expected = console.objects_revision(snapshot_id)
    console._objects_tls.expected = {snapshot_id: "0" * 64}
    client = _client(console, "researcher.anne", production_app=production_app)
    _body, revision = _open_review_form(client, snapshot_id, target["object_id"])
    assert revision.startswith(PREFIX)
    assert resolve_review_revision(console, snapshot_id, revision) == expected
    assert revision != "0" * 64


def test_review_post_progresses_while_ingest_extract_is_heavy(tmp_path: Path, *, production_app, production_console) -> None:
    """Promise 4: review POST MUST progress while ingest extract is still running."""
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Al aanwezig", version="1.0")
    snapshot_id = receipt["snapshot_id"]
    target = _content_rows(console, snapshot_id)[0]
    anne = _client(console, "researcher.anne", production_app=production_app)
    body, revision = _open_review_form(anne, snapshot_id, target["object_id"])
    assert revision
    extract_started = threading.Event()
    extract_release = threading.Event()
    extract_still_running = threading.Event()
    original_fragments = console._fragments_and_spec

    def slow_extract(self, *args, **kwargs):
        extract_started.set()
        extract_still_running.set()
        assert extract_release.wait(timeout=8), "review POST never released ingest extract"
        extract_still_running.clear()
        return original_fragments(*args, **kwargs)

    console._fragments_and_spec = slow_extract.__get__(console, OperationsConsole)  # type: ignore[method-assign]
    app = production_app(console)

    async def _run() -> None:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as researcher:
            async with httpx.AsyncClient(transport=transport, base_url="https://test") as reviewer:
                await _login(researcher, "researcher.dirk", "dirk-secret")
                await _login(reviewer, "reviewer.bert", "bert-secret")
                async def receive_and_select():
                    received = await researcher.post("/ingest", data=_ingest_form(accounts),
                        files={"file": ("continentie.html", HTML_FIXTURE.read_bytes(), "text/html")})
                    assert received.status_code == 303
                    from urllib.parse import parse_qs, urlparse
                    sid = parse_qs(urlparse(received.headers["location"]).query)["document"][0]
                    started = await researcher.post("/source-selection/start", data={"document": sid,
                        "command_id": "independent-selection", "expected_revision": console.objects_revision(sid)})
                    assert started.status_code == 303
                    await asyncio.gather(*tuple(app.state.source_selection_workers))
                    return received
                ingest_task = asyncio.create_task(receive_and_select())
                for _ in range(80):
                    if extract_started.is_set():
                        break
                    await asyncio.sleep(0.01)
                assert extract_started.is_set(), "ingest extract never started"
                t0 = time.perf_counter()
                posted = await reviewer.post(
                    "/review",
                    data={**_review_payload(
                        snapshot_id,
                        target["object_id"],
                        snapshot_revision=revision,
                        suitability="ja",
                        comment=BERT_COMMENT,
                    ), "eindoordeel": "afwijzen"},
                    follow_redirects=False,
                )
                elapsed = time.perf_counter() - t0
                assert extract_still_running.is_set(), "review POST waited for ingest extract to finish"
                extract_release.set()
                ingest_response = await ingest_task

        assert posted.status_code in {303, 200}
        assert elapsed < 0.6, f"review POST waited {elapsed:.3f}s during ingest extract"
        assert ingest_response.status_code == 303
        assert ingest_response.headers["location"].startswith("/source-selection?document=")

    asyncio.run(_run())
    live = next(
        row
        for row in _restart(tmp_path, production_console=production_console).snapshot_objects(snapshot_id)
        if row["object_id"] == target["object_id"]
    )
    passage = ((live.get("metadata") or {}).get("review_passage") or {})
    assert passage.get("suitability") == "ja"
    assert live["governance"]["validation_status"] == "rejected"
    _ = body
    _ = ANNE_COMMENT
    _ = ANNE_SUIT


def _file_console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )



def _file_restart(tmp_path: Path) -> OperationsConsole:
    return _file_console(tmp_path)



def _file_disk_envelopes(console: OperationsConsole) -> dict:
    return json.loads((console.runtime / "envelopes.json").read_text(encoding="utf-8"))
