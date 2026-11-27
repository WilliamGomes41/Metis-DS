"""Role-specific console landing and shared navigation.

# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import re
from pathlib import Path
from secrets import token_urlsafe

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import OperationsConsole


pytestmark = [
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "src/operations_console_app.py"
CSS_SOURCE = ROOT / "assets/brand/console.css"
FORBIDDEN_LIVE_LABELS = (
    "Documentenhiërarchie",
    "Documentenhierarchie",
    "Familieboom",
)
TEST_PASSWORD = token_urlsafe(24)


def _console(tmp_path: Path, *, production_console) -> OperationsConsole:
    return production_console(processing_binder=bind_fixture_selections,
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def _accounts(console: OperationsConsole) -> dict[str, dict]:
    researcher = console.create_account(
        username="researcher.anne",
        password=TEST_PASSWORD,
        roles=("researcher", "reviewer"),
        display_name="Anne Onderzoeker",
    )
    reviewer = console.create_account(
        username="reviewer.bert",
        password=TEST_PASSWORD,
        roles=("reviewer",),
        display_name="Bert Reviewer",
    )
    return {"researcher": researcher, "reviewer": reviewer}


def _fresh_client(console: OperationsConsole, *, production_app) -> TestClient:
    return TestClient(production_app(console))


def _client(console: OperationsConsole, username: str='researcher.anne', *, production_app) -> TestClient:
    client = _fresh_client(console, production_app=production_app)
    client.post("/login", data={"username": username, "password": TEST_PASSWORD})
    return client


def _h1s(html: str) -> list[str]:
    return [
        re.sub(r"<[^>]+>", "", block).strip()
        for block in re.findall(r"<h1[^>]*>.*?</h1>", html, flags=re.I | re.S)
    ]


def _nav_html(html: str) -> str:
    match = re.search(r'<nav class="rooms"[^>]*>(.*?)</nav>', html, flags=re.S)
    assert match, "page must render room nav"
    return match.group(1)


def _nav_links(html: str) -> list[tuple[str, str, str]]:
    nav = _nav_html(html)
    found: list[tuple[str, str, str]] = []
    for match in re.finditer(r'<a\s+([^>]+)>(.*?)</a>', nav, flags=re.S):
        attrs = match.group(1)
        href_m = re.search(r'href="([^"]*)"', attrs)
        if not href_m:
            continue
        href = href_m.group(1)
        current = "page" if "aria-current" in attrs else ""
        label = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        found.append((href, label, current))
    return found


def _nav_hrefs(html: str) -> list[str]:
    return [href for href, _label, _current in _nav_links(html)]


def _nav_entry(html: str, href: str) -> tuple[str, str]:
    for link_href, label, current in _nav_links(html):
        if link_href == href:
            return label, current
    raise AssertionError(f"nav must include {href}")


def _media_560(css: str) -> str:
    match = re.search(r"@media\s*\(max-width:\s*560px\)\s*\{", css)
    assert match, "console.css must keep a 560px mobile breakpoint"
    start = match.end()
    depth = 1
    i = start
    while i < len(css) and depth:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
        i += 1
    return css[start : i - 1]


def _rule(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", css)
    assert match, f"CSS must define {selector}"
    return match.group(1)


@pytest.mark.parametrize(("roles", "destination"), [
    (("researcher",), "/source-selection"),
    (("reviewer",), "/review"),
    (("publisher",), "/publish"),
    (("researcher", "reviewer"), "/source-selection"),
    (("publisher", "researcher"), "/source-selection"),
    (("publisher", "reviewer"), "/review"),
    (("reviewer", "publisher", "researcher"), "/source-selection"),
])
def test_authenticated_start_opens_the_workspace_for_the_account(tmp_path, roles, destination, production_app, production_console):
    console = _console(tmp_path, production_console=production_console)
    console.create_account(username="start.user", password=TEST_PASSWORD, roles=roles)
    client = _fresh_client(console, production_app=production_app)
    login = client.post("/login", data={"username": "start.user", "password": TEST_PASSWORD})
    assert login.status_code == 200
    assert login.url.path == destination
    start = client.get("/", follow_redirects=False)
    assert start.status_code == 303
    assert start.headers["location"] == destination
    assert start.headers["cache-control"] == "no-store"
    assert _nav_entry(login.text, destination)[1] == "page"
    assert "/" not in _nav_hrefs(login.text)
    assert 'class="brand metis-brand" href="/"' in login.text


def test_tree_documenten_unchanged_v232(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    _accounts(console)
    client = _client(console, production_app=production_app)
    tree = client.get("/tree").text
    headings = _h1s(tree)
    assert headings, "/tree must render an h1"
    assert headings[0] == "Documenten"
    tree_label, tree_current = _nav_entry(tree, "/tree")
    assert tree_label == "Documenten" or tree_label.startswith("Documenten")
    assert tree_current == "page"
    assert '/' not in _nav_hrefs(tree)
    assert re.search(r'<a class="brand metis-brand" href="/"', tree)
    for label in FORBIDDEN_LIVE_LABELS:
        assert label not in tree
    title = re.search(r"<title[^>]*>(.*?)</title>", tree, flags=re.I | re.S)
    assert title and "Documenten" in re.sub(r"<[^>]+>", "", title.group(1))


def test_mobile_nav_does_not_clip_publiceren_to_pub(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    _accounts(console)
    html = _client(console, production_app=production_app).get("/tree").text
    nav = _nav_html(html)
    publish_label, _current = _nav_entry(html, "/publish")
    assert "Publicatie" in publish_label
    assert publish_label.strip() != "Pub"
    assert re.search(r">\s*Pub\s*<", nav) is None
    css = CSS_SOURCE.read_text(encoding="utf-8")
    source = APP_SOURCE.read_text(encoding="utf-8")
    assert '"Publicatie"' in source or ">Publicatie<" in source
    assert re.search(r'["\']Pub["\']', source) is None
    mobile = _media_560(css)
    rooms = _rule(mobile, ".rooms")
    rooms_a = _rule(mobile, ".rooms a")
    assert "flex-wrap: wrap" in rooms
    assert "nowrap" not in rooms
    assert "overflow: hidden" not in rooms
    assert "text-overflow" not in rooms
    assert "ellipsis" not in rooms
    assert "overflow: hidden" not in rooms_a
    assert "text-overflow" not in rooms_a
    assert "ellipsis" not in rooms_a
