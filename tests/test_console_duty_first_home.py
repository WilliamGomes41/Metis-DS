"""Duty-first logged-in home SUPERSEDES #127 sketch B.

Logged-in `/` MUST use the horizontal Metis workboard: nav Mijn werk
first and current on `/`, then Inleveren, Review, Publiceren and
Documenten; four large clickable tiles in that same order. Review is
visually prioritised only when work is waiting. Post-auth still lands
on `/`, not `/ingest`. `/tree` Documenten stays unchanged (v2.32).

PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here. publish()
stays G2-BLOCKED. Item A Recent activity, Item B SHA-256 duplicate
guard, and Item C OIDC/release-identity are out of scope.

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
from secrets import token_urlsafe
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
CSS_SOURCE = ROOT / "assets/brand/console.css"
FORBIDDEN_LIVE_LABELS = (
    "Documentenhiërarchie",
    "Documentenhierarchie",
    "Familieboom",
)
SKETCH_B_PRIMARY_MARKERS = (
    'class="home-chooser"',
    'class="room home-chooser"',
    'class="home-secondary"',
)
TEST_PASSWORD = token_urlsafe(24)


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
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
    client.post("/login", data={"username": username, "password": TEST_PASSWORD})
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


def _location_path(response) -> str:
    location = response.headers.get("location") or ""
    parsed = urlparse(location)
    return parsed.path or location


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


def test_nav_home_is_first_room_and_current_on_home(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console).get("/").text
    hrefs = _nav_hrefs(html)
    assert hrefs, "logged-in pages must render room nav"
    assert hrefs[:5] == ["/", "/ingest", "/review", "/publish", "/tree"]
    home_label, home_current = _nav_entry(html, "/")
    assert home_label == "Mijn werk"
    assert home_current == "page"
    ingest_html = _client(console).get("/ingest").text
    ingest_hrefs = _nav_hrefs(ingest_html)
    assert ingest_hrefs[0] == "/"
    _ingest_home_label, ingest_home_current = _nav_entry(ingest_html, "/")
    assert ingest_home_current != "page"
    _ingest_label, ingest_current = _nav_entry(ingest_html, "/ingest")
    assert ingest_current == "page"


def test_home_must_not_mark_inleveren_current(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console).get("/").text
    ingest_label, ingest_current = _nav_entry(html, "/ingest")
    assert "Inleveren" in ingest_label
    assert ingest_current != "page"
    home = _nav_html(html)
    ingest_link = re.search(r'<a href="/ingest"[^>]*>', home)
    assert ingest_link, "home nav must include Inleveren"
    assert "aria-current" not in ingest_link.group(0)


def test_home_heading_and_lead(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console).get("/").text
    headings = _h1s(html)
    assert headings, "logged-in home must render an h1"
    assert headings[0] == "Mijn werk"
    assert "Kies de volgende stap in het proces." in html
    visible = _visible_text(html)
    assert "Mijn werk" in visible
    assert "Kies de volgende stap in het proces." in visible


def test_home_has_four_horizontal_process_tiles_with_links(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console).get("/").text
    visible = _visible_text(html)
    assert "Inleveren" in visible
    assert "Nieuwe bron toevoegen" in visible
    assert "Review" in visible
    assert "Beoordeel aangeleverde bronnen" in visible
    assert "Publiceren" in visible
    assert "Goedgekeurde stukken publiceren" in visible
    assert "Documenten" in visible
    assert "Zoeken, openen of beheren" in visible
    assert len(re.findall(r'<a class="home-tile(?: |")', html)) == 4
    assert [match.group(1) for match in re.finditer(r'<a class="home-tile[^>]* href="([^"]+)"', html)] == [
        "/ingest", "/review", "/publish", "/tree"
    ]
    assert 'enctype="multipart/form-data"' not in html


def test_home_review_tile_shows_waiting_count_and_priority(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    empty_home = _client(console).get("/").text
    assert "Geen open taken" in empty_home
    assert "home-tile-priority" not in empty_home
    _ingest(console, accounts, title="Wachtende richtlijn")
    waiting = console.waiting_task_counts(accounts["researcher"]["account_id"])["review"]
    assert waiting >= 1
    home = _client(console).get("/").text
    assert re.search(rf"{waiting}\s*wachten op jou", home)
    review_tile = re.search(
        r'<a class="home-tile home-tile-priority" href="/review">(.*?)</a>',
        home,
        flags=re.S,
    )
    assert review_tile
    assert "Nu doen" in review_tile.group(1)
    assert "wacht" in review_tile.group(1).lower()
    assert str(waiting) in review_tile.group(1)


def test_post_auth_redirect_lands_on_home_not_ingest(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    client = _fresh_client(console)
    login = client.post(
        "/login",
        data={"username": "researcher.anne", "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    assert login.status_code in {302, 303}
    assert _location_path(login) == "/"
    assert _location_path(login) != "/ingest"
    home = client.get("/", follow_redirects=False)
    assert home.status_code == 200
    assert _location_path(home) != "/ingest"
    assert _h1s(home.text)[0] == "Mijn werk"


def test_tree_documenten_unchanged_v232(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    client = _client(console)
    tree = client.get("/tree").text
    headings = _h1s(tree)
    assert headings, "/tree must render an h1"
    assert headings[0] == "Documenten"
    tree_label, tree_current = _nav_entry(tree, "/tree")
    assert tree_label == "Documenten" or tree_label.startswith("Documenten")
    assert tree_current == "page"
    home_label, home_current = _nav_entry(tree, "/")
    assert home_label == "Mijn werk"
    assert home_current != "page"
    for label in FORBIDDEN_LIVE_LABELS:
        assert label not in tree
    title = re.search(r"<title[^>]*>(.*?)</title>", tree, flags=re.I | re.S)
    assert title and "Documenten" in re.sub(r"<[^>]+>", "", title.group(1))


def test_mobile_nav_does_not_clip_publiceren_to_pub(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console).get("/").text
    nav = _nav_html(html)
    publish_label, _current = _nav_entry(html, "/publish")
    assert "Publiceren" in publish_label
    assert publish_label.strip() != "Pub"
    assert re.search(r">\s*Pub\s*<", nav) is None
    css = CSS_SOURCE.read_text(encoding="utf-8")
    source = APP_SOURCE.read_text(encoding="utf-8")
    assert '"Publiceren"' in source or ">Publiceren<" in source
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


def test_home_uses_tiles_instead_of_the_previous_small_duty_cards(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console).get("/").text
    for marker in SKETCH_B_PRIMARY_MARKERS:
        assert marker not in html
    assert "duty-card" not in html
    assert "duty-grid" not in html
    assert len(re.findall(r'<a class="home-tile(?: |")', html)) == 4
    assert "home-secondary" not in html
    assert "home-chooser" not in html
    visible = _visible_text(html)
    assert "Inleveren" in visible
    assert "Review" in visible
    assert "Publiceren" in visible
    assert "Documenten" in visible
    quiet_secondaries = re.findall(
        r'<a[^>]*class="[^"]*quiet[^"]*"[^>]*href="/(tree|review|publish|accounts)"',
        html.split("</nav>", 1)[-1] if "</nav>" in html else html,
    )
    assert quiet_secondaries == []
