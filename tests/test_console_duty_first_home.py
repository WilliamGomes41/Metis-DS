"""Duty-first logged-in home SUPERSEDES #127 sketch B.

Logged-in `/` MUST follow the Metis Design mock: nav Home first and
current on `/`; MUST NOT mark Inleveren current on home; heading
«Waar wil je verder?» + lead «Kies wat je nu wilt doen.»; three duty
cards (Review / Inleveren / Documenten) with waiting badge and
room links. Post-auth still lands on `/`, not `/ingest`. `/tree`
Documenten UNCHANGED (v2.32). Mobile nav MUST NOT clip Publiceren
to «Pub». Sketch B sparse one-CTA / quiet-only secondaries MUST NOT
remain the primary home.

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


def _nav_html(html: str) -> str:
    match = re.search(r'<nav class="rooms">(.*?)</nav>', html, flags=re.S)
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


def _primary_ctas(html: str) -> list[tuple[str, str]]:
    body = html.split('<nav class="rooms">', 1)[-1] if '<nav class="rooms">' in html else html
    if "</nav>" in body:
        body = body.split("</nav>", 1)[-1]
    found: list[tuple[str, str]] = []
    for match in re.finditer(
        r'<a([^>]*class="[^"]*btn-primary[^"]*"[^>]*)>(.*?)</a>',
        body,
        flags=re.S,
    ):
        href_m = re.search(r'href="([^"]*)"', match.group(1))
        label = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        found.append((href_m.group(1) if href_m else "", label))
    return found


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
    assert hrefs[0] == "/", "Home must be the first nav room"
    home_label, home_current = _nav_entry(html, "/")
    assert home_label == "Home" or home_label.startswith("Home")
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
    assert headings[0] == "Waar wil je verder?"
    assert "Kies wat je nu wilt doen." in html
    visible = _visible_text(html)
    assert "Waar wil je verder?" in visible
    assert "Kies wat je nu wilt doen." in visible


def test_home_has_three_duty_cards_with_links(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console).get("/").text
    visible = _visible_text(html)
    assert "Openstaand reviewwerk" in visible
    assert "Bron inleveren" in visible
    assert "PDF of HTML-freeze toevoegen" in visible
    assert "Documenten" in visible
    assert "Zoeken, openen of verwijderen" in visible
    assert html.count("duty-card") == 3
    primaries = _primary_ctas(html)
    labels = [label for _href, label in primaries]
    hrefs = [href for href, _label in primaries]
    assert "Naar review" in labels
    assert "Naar inleveren" in labels
    assert "Naar documenten" in labels
    assert "/review" in hrefs
    assert "/ingest" in hrefs
    assert "/tree" in hrefs
    assert re.search(
        r'<a[^>]*href="/review"[^>]*>\s*Naar review',
        html,
    )
    assert re.search(
        r'<a[^>]*href="/ingest"[^>]*>\s*Naar inleveren',
        html,
    )
    assert re.search(
        r'<a[^>]*href="/tree"[^>]*>\s*Naar documenten',
        html,
    )
    assert 'enctype="multipart/form-data"' not in html


def test_home_review_card_shows_waiting_count_badge(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    empty_home = _client(console).get("/").text
    assert re.search(r"0\s*wachten", empty_home)
    _ingest(console, accounts, title="Wachtende richtlijn")
    waiting = console.waiting_task_counts(accounts["researcher"]["account_id"])["review"]
    assert waiting >= 1
    home = _client(console).get("/").text
    assert re.search(rf"{waiting}\s*wachten", home)
    review_card = home[home.find("Openstaand reviewwerk") : home.find("Bron inleveren")]
    assert "wacht" in review_card.lower()
    assert str(waiting) in review_card


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
    assert _location_path(home) != "/ingest"
    assert _h1s(home.text)[0] == "Waar wil je verder?"


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
    assert home_label.startswith("Home")
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


def test_home_forbids_sketch_b_as_primary(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    html = _client(console).get("/").text
    for marker in SKETCH_B_PRIMARY_MARKERS:
        assert marker not in html
    primaries = _primary_ctas(html)
    assert len(primaries) == 3
    primary_labels = {label for _href, label in primaries}
    assert primary_labels == {"Naar review", "Naar inleveren", "Naar documenten"}
    assert not any(label in {"Bron inleveren", "Document inleveren"} for label in primary_labels)
    assert "home-secondary" not in html
    assert "home-chooser" not in html
    visible = _visible_text(html)
    assert "Openstaand reviewwerk" in visible
    assert "Naar review" in visible
    assert "Naar inleveren" in visible
    assert "Naar documenten" in visible
    quiet_secondaries = re.findall(
        r'<a[^>]*class="[^"]*quiet[^"]*"[^>]*href="/(tree|review|publish|accounts)"',
        html.split("</nav>", 1)[-1] if "</nav>" in html else html,
    )
    assert quiet_secondaries == []
