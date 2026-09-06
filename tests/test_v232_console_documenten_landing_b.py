"""Protocol v2.32 Forge: Documenten UI rename + landing sketch B.

Live `/tree` heading / nav / page title MUST be Documenten. Forbidden live
labels Documentenhiërarchie / Documentenhierarchie / Familieboom MUST NOT
render. v2.27 unpublished-delete stays on that same `/tree` room only +
type-to-confirm. Logged-in `/` is a centered sparse home (sketch B);
post-auth redirect lands on that home, not `/ingest`.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here. publish() stays
G2-BLOCKED. Kernel family × class UNCHANGED.

Markers in this file are CI metadata pointing at these checks
(scripts/release_control_preflight.py and this suite). They are not
live-release evidence.

# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole


pytestmark = [
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "src/operations_console_app.py"
DELETE_LABEL = "Verwijder unpublished document"
TITLE_FIELD = "confirm_title"
FORBIDDEN_LIVE_LABELS = (
    "Documentenhiërarchie",
    "Documentenhierarchie",
    "Familieboom",
)
NO_DELETE_ROOMS = (
    ("/ingest", "Inleveren"),
    ("/review", "Review"),
    ("/publish", "Publiceren"),
    ("/accounts", "Accounts"),
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


def _tiny_html(title: str) -> bytes:
    return (
        "<!doctype html><html lang='nl'><head><title>"
        f"{title}</title></head><body>"
        f"<h1>{title}</h1>"
        f"<p>Dit is een aanbeveling voor {title} in de praktijk.</p>"
        "</body></html>"
    ).encode("utf-8")


def _ingest(console: OperationsConsole, accounts: dict, *, title: str = "Test richtlijn") -> dict:
    return console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="richtlijn.html",
        data=_tiny_html(title),
        content_type="text/html",
        ingest_kind="new",
        title=title,
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


def _fresh_client(console: OperationsConsole) -> TestClient:
    return TestClient(create_console_app(console))


def _client(console: OperationsConsole, username: str = "researcher.anne") -> TestClient:
    client = _fresh_client(console)
    passwords = {
        "reviewer.bert": "bert-secret",
        "researcher.anne": "anne-secret",
        "publisher.carla": "carla-secret",
    }
    client.post("/login", data={"username": username, "password": passwords[username]})
    return client


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


def _h1s(html: str) -> list[str]:
    return [
        re.sub(r"<[^>]+>", "", block).strip()
        for block in re.findall(r"<h1[^>]*>.*?</h1>", html, flags=re.I | re.S)
    ]


def _title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    assert match, "page must have a title"
    return re.sub(r"<[^>]+>", "", match.group(1)).strip()


def _nav_html(html: str) -> str:
    match = re.search(r'<nav class="rooms">(.*?)</nav>', html, flags=re.S)
    assert match, "page must render room nav"
    return match.group(1)


def _nav_label_for(html: str, href: str) -> str:
    nav = _nav_html(html)
    match = re.search(
        rf'<a href="{re.escape(href)}"[^>]*>(.*?)</a>',
        nav,
        flags=re.S,
    )
    assert match, f"nav must include {href}"
    return re.sub(r"<[^>]+>", "", match.group(1)).strip()


def _location_path(response) -> str:
    location = response.headers.get("location") or ""
    parsed = urlparse(location)
    return parsed.path or location


def _has_delete_control(html: str) -> bool:
    return (
        DELETE_LABEL in html
        or 'action="/documents/delete"' in html
        or "delete-unpublished" in html
    )


def _primary_ctas(html: str) -> list[str]:
    body = html.split('<nav class="rooms">', 1)[-1] if '<nav class="rooms">' in html else html
    if "</nav>" in body:
        body = body.split("</nav>", 1)[-1]
    return re.findall(
        r'<a[^>]*class="[^"]*btn-primary[^"]*"[^>]*>(.*?)</a>',
        body,
        flags=re.S,
    )


# ---------------------------------------------------------------------------
# 1. Live /tree heading, nav label, page title = Documenten
# ---------------------------------------------------------------------------


def test_tree_live_heading_nav_and_page_title_are_documenten(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    client = _client(console)
    tree = client.get("/tree").text
    headings = _h1s(tree)
    assert headings, "/tree must render an h1"
    assert headings[0] == "Documenten"
    assert _nav_label_for(tree, "/tree") == "Documenten"
    assert "Documenten" in _title(tree)
    ingest_nav = _nav_label_for(client.get("/ingest").text, "/tree")
    assert ingest_nav == "Documenten"
    assert client.get("/tree").status_code == 200


def test_live_ui_forbids_hierarchy_and_familieboom_labels(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    client = _client(console)
    for path in ("/tree", "/ingest", "/review", "/"):
        html = client.get(path).text
        visible = _visible_text(html)
        lowered = html.lower()
        for label in FORBIDDEN_LIVE_LABELS:
            assert label not in html, f"{label} must not appear as live UI on {path}"
            assert label.lower() not in lowered
            assert label not in visible
            assert label not in _title(html)
        if path == "/tree":
            assert _h1s(html)[0] == "Documenten"
            assert _nav_label_for(html, "/tree") == "Documenten"


# ---------------------------------------------------------------------------
# 2. v2.27 unpublished-delete stays on the Documenten /tree room only
# ---------------------------------------------------------------------------


def test_unpublished_delete_stays_on_documenten_tree_room_only(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Alleen Documenten-kamer")
    snap = receipt["snapshot_id"]
    client = _client(console)

    tree = client.get("/tree").text
    assert _h1s(tree)[0] == "Documenten"
    assert DELETE_LABEL in tree
    assert snap in tree
    assert TITLE_FIELD in tree
    assert 'action="/documents/delete"' in tree
    assert _has_delete_control(tree)

    for path, heading in NO_DELETE_ROOMS:
        html = client.get(path).text
        assert heading in html
        assert DELETE_LABEL not in html
        assert not _has_delete_control(html)

    chosen = client.get(f"/review?document={snap}").text
    assert "Beoordeel" in chosen
    assert DELETE_LABEL not in chosen
    assert not _has_delete_control(chosen)

    home = client.get("/").text
    assert DELETE_LABEL not in home
    assert not _has_delete_control(home)
    assert client.get("/delete").status_code in {404, 405}


def test_app_source_still_wires_delete_only_on_tree() -> None:
    source = APP_SOURCE.read_text(encoding="utf-8")
    ingest_get = source.split("def ingest_get", 1)[1].split("\n    @app.", 1)[0]
    review = source.split("def review_get", 1)[1].split("\n    @app.", 1)[0]
    publish = source.split("def publish_get", 1)[1].split("\n    @app.", 1)[0]
    accounts = source.split("def accounts_get", 1)[1].split("\n    @app.", 1)[0]
    tree = source.split("def tree(", 1)[1].split("\n    @app.", 1)[0]
    assert "_unpublished_delete_control" not in ingest_get
    assert "_unpublished_delete_control" not in review
    assert "_unpublished_delete_control" not in publish
    assert "_unpublished_delete_control" not in accounts
    assert "_unpublished_delete_control" in tree
    assert TITLE_FIELD in source
    assert DELETE_LABEL in source


# ---------------------------------------------------------------------------
# 3. Landing sketch B + post-auth home redirect
# ---------------------------------------------------------------------------


def test_logged_in_home_is_sketch_b_sparse_chooser_not_ingest_redirect(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    _accounts(console)
    client = _client(console)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert _location_path(response) != "/ingest"
    html = response.text
    assert 'class="home-chooser"' in html or 'class="room home-chooser"' in html
    primaries = _primary_ctas(html)
    assert len(primaries) == 1
    primary = re.sub(r"<[^>]+>", "", primaries[0]).strip()
    assert primary in {"Bron inleveren", "Document inleveren"}
    assert re.search(r'<a[^>]*href="/ingest"[^>]*class="[^"]*btn-primary', html)
    visible = _visible_text(html)
    assert "Documenten" in visible
    assert "Review" in visible
    assert html.count("doc-card") == 0
    assert "duty-card" not in html
    assert html.count("btn-primary") == 1
    assert 'enctype="multipart/form-data"' not in html
    assert re.search(r'<a[^>]*href="/tree"[^>]*>\s*Documenten', html)
    assert re.search(r'<a[^>]*href="/review"[^>]*>\s*Review', html)
    for label in FORBIDDEN_LIVE_LABELS:
        assert label not in html


def test_post_auth_redirect_lands_on_home_not_ingest(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    client = _fresh_client(console)
    login = client.post(
        "/login",
        data={"username": "researcher.anne", "password": "anne-secret"},
        follow_redirects=False,
    )
    assert login.status_code in {302, 303}
    assert _location_path(login) == "/"
    assert _location_path(login) != "/ingest"
    home = client.get("/", follow_redirects=False)
    assert home.status_code == 200
    assert "Bron inleveren" in home.text or "Document inleveren" in home.text
    assert _location_path(home) != "/ingest"
