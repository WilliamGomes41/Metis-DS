"""Ingest beschikbaarheid (ROADMAP wave 2).

Console ingest MUST keep the async event loop free, MUST fail-closed on
oversize upload/download, and MUST stay usable with overlapping requests
from at least two users. PROTOCOL.md and docs/PROTOCOL_V2_* are not edited
here. publish() stays G2-BLOCKED. Wave 1 reviewopslag paths stay.

# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import asyncio
import importlib.util
import re
import threading
import time
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
SCRIPT = ROOT / "scripts" / "release_control_preflight.py"
INGEST_PAYLOAD_TOO_LARGE = "ingest_payload_too_large"
ENV_INGEST_MAX_BYTES = "CONSOLE_INGEST_MAX_BYTES"

pytestmark = [
    pytest.mark.release_control_beschikbaarheid,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _load_preflight():
    spec = importlib.util.spec_from_file_location("release_control_preflight", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    second = console.create_account(
        username="researcher.dirk",
        password="dirk-secret",
        roles=("researcher", "reviewer"),
        display_name="Dirk Onderzoeker",
    )
    return {"researcher": researcher, "reviewer": reviewer, "second": second}


def _tiny_pdf(tmp_path: Path, text: str = "Richtlijn test PDF") -> bytes:
    import fitz

    path = tmp_path / "generated.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path.read_bytes()


def _ingest_form(accounts: dict, *, extra: dict | None = None) -> dict[str, str]:
    data = {
        "ingest_kind": "new",
        "title": "Continentie via console",
        "version": "1.0",
        "date": "2025-04-01",
        "live_url": "https://example.test/continentie",
        "class_": "richtlijn",
        "family": "continentie",
        "named_reviewers": accounts["reviewer"]["account_id"],
    }
    if extra:
        data.update(extra)
    return data


async def _login(client: httpx.AsyncClient, username: str, password: str) -> None:
    response = await client.post("/login", data={"username": username, "password": password})
    assert response.status_code in {200, 303}


def test_ingest_limits_module_maps_to_beschikbaarheid() -> None:
    item = _load_preflight().classify_paths(["src/ingest_limits_v1.py"])["beschikbaarheid"]
    assert item["status"] == "required"
    assert "src/ingest_limits_v1.py" in item["paths"]


def test_ingest_work_does_not_block_event_loop(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    started = threading.Event()
    original = console.ingest

    def slow_ingest(**kwargs):
        started.set()
        time.sleep(0.45)
        return original(**kwargs)

    console.ingest = slow_ingest  # type: ignore[method-assign]
    app = create_console_app(console)

    async def _run() -> None:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
            await _login(client, "researcher.anne", "anne-secret")
            ingest_task = asyncio.create_task(
                client.post(
                    "/ingest",
                    data=_ingest_form(accounts),
                    files={"file": ("continentie.html", HTML_FIXTURE.read_bytes(), "text/html")},
                )
            )
            for _ in range(80):
                if started.is_set():
                    break
                await asyncio.sleep(0.01)
            assert started.is_set(), "ingest work never started"

            heartbeat_task = asyncio.create_task(asyncio.sleep(0.05))
            t0 = time.perf_counter()
            ping = await client.get("/login")
            elapsed = time.perf_counter() - t0
            await heartbeat_task
            ingest_response = await ingest_task

        assert ping.status_code == 200
        assert elapsed < 0.25, f"lightweight request waited {elapsed:.3f}s; event loop was blocked"
        assert ingest_response.status_code == 200
        assert "document ingeleverd" in ingest_response.text.lower()

    asyncio.run(_run())


def test_oversize_upload_and_download_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_INGEST_MAX_BYTES, "64")
    console = _console(tmp_path)
    accounts = _accounts(console)
    oversize = b"<html><body>" + (b"x" * 200) + b"</body></html>"
    pdf_payload = _tiny_pdf(tmp_path)
    assert len(pdf_payload) > 64
    console.url_fetcher = lambda _url: (pdf_payload, "application/pdf", "payload.bin")
    app = create_console_app(console)
    url = "https://example.test/payload.bin"

    async def _run() -> None:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
            await _login(client, "researcher.anne", "anne-secret")
            upload = await client.post(
                "/ingest",
                data=_ingest_form(accounts, extra={"title": "Te groot upload"}),
                files={"file": ("too-big.html", oversize, "text/html")},
            )
            download = await client.post(
                "/ingest",
                data=_ingest_form(
                    accounts,
                    extra={"title": "Te groot download", "url": url, "live_url": url},
                ),
            )
        assert upload.status_code == 400
        assert INGEST_PAYLOAD_TOO_LARGE in upload.text
        assert "te groot" in upload.text.lower()
        assert upload.status_code != 200 or "document ingeleverd" not in upload.text.lower()
        assert download.status_code == 400
        assert INGEST_PAYLOAD_TOO_LARGE in download.text
        assert "te groot" in download.text.lower()

    asyncio.run(_run())
    assert console.list_envelopes() == []


def test_two_users_overlap_ingest_and_other_request(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    started = threading.Event()
    original = console.ingest

    def slow_ingest(**kwargs):
        started.set()
        time.sleep(0.35)
        return original(**kwargs)

    console.ingest = slow_ingest  # type: ignore[method-assign]
    app = create_console_app(console)

    async def _run() -> None:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as anne:
            async with httpx.AsyncClient(transport=transport, base_url="https://test") as dirk:
                await _login(anne, "researcher.anne", "anne-secret")
                await _login(dirk, "researcher.dirk", "dirk-secret")
                ingest_task = asyncio.create_task(
                    anne.post(
                        "/ingest",
                        data=_ingest_form(accounts),
                        files={"file": ("continentie.html", HTML_FIXTURE.read_bytes(), "text/html")},
                    )
                )
                for _ in range(80):
                    if started.is_set():
                        break
                    await asyncio.sleep(0.01)
                assert started.is_set()
                t0 = time.perf_counter()
                other = await dirk.get("/tree")
                elapsed = time.perf_counter() - t0
                ingest_response = await ingest_task

        assert other.status_code == 200
        headings = [
            re.sub(r"<[^>]+>", "", block).strip()
            for block in re.findall(r"<h1[^>]*>.*?</h1>", other.text, flags=re.I | re.S)
        ]
        assert headings and headings[0] == "Documenten"
        nav = re.search(r'<nav class="rooms">(.*?)</nav>', other.text, flags=re.S)
        assert nav, "/tree must render room nav during overlapping ingest"
        tree_label = re.search(r'<a href="/tree"[^>]*>(.*?)</a>', nav.group(1), flags=re.S)
        assert tree_label
        assert re.sub(r"<[^>]+>", "", tree_label.group(1)).strip() == "Documenten"
        assert "documentenhiërarchie" not in other.text.lower()
        assert "documentenhierarchie" not in other.text.lower()
        assert elapsed < 0.25, f"second user waited {elapsed:.3f}s during overlapping ingest"
        assert ingest_response.status_code == 200
        assert "document ingeleverd" in ingest_response.text.lower()

    asyncio.run(_run())
