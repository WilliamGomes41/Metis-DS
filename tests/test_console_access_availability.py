"""#546: access must not depend on review work or confuse outages with expiry.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import re
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.console_entra_routes_v1 import install_entra_routes
from src.operations_console_app import _page, create_console_app
from src.operations_console_v1 import ConsoleError
from tests.test_console_duty_first_home import _accounts, _client, _console, _visible_text


def unavailable(*args, **kwargs):
    raise ConsoleError("workflow_identity_unavailable")


@pytest.mark.parametrize("path", ["/", "/ingest", "/tree", "/review", "/publish", "/settings", "/over-console"])
def test_navigation_does_not_request_review_badges(tmp_path, monkeypatch, path):
    console = _console(tmp_path)
    _accounts(console)
    client = _client(console)

    def forbidden(*args, **kwargs):
        pytest.fail("page navigation requested the review-count calculation")

    monkeypatch.setattr(console, "waiting_task_counts", forbidden)
    response = client.get(path)
    assert response.status_code == 200
    assert '<nav class="rooms">' in response.text


def test_authenticated_home_does_not_load_document_inventory(tmp_path, monkeypatch):
    console = _console(tmp_path)
    _accounts(console)
    client = _client(console)

    def forbidden():
        pytest.fail("home requested the complete document inventory")

    monkeypatch.setattr(console, "list_envelopes", forbidden)
    response = client.get("/")
    assert response.status_code == 200
    assert "Mijn werk" in response.text
    assert "Geen open taken" not in response.text
    assert "0 documenten" not in response.text


@pytest.mark.parametrize("path", ["/", "/settings"])
def test_identity_outage_is_503_and_keeps_cookie(tmp_path, monkeypatch, path):
    console = _console(tmp_path)
    _accounts(console)
    client = _client(console)
    cookie = client.cookies.get("console_session")
    with monkeypatch.context() as patch:
        patch.setattr(console, "session_account", unavailable)
        response = client.get(path, follow_redirects=False)
    assert response.status_code == 503
    assert "tijdelijk niet beschikbaar" in response.text
    assert 'href="/login"' not in response.text
    assert "Je sessie is verlopen" not in _visible_text(response.text)
    assert client.cookies.get("console_session") == cookie
    assert client.get("/").status_code == 200
    assert "Mijn werk" in client.get("/").text


def test_navigation_renewal_outage_preserves_cookie_and_denies_access(tmp_path, monkeypatch):
    console = _console(tmp_path)
    _accounts(console)
    login_client = _client(console)
    app = create_console_app(console)
    # Exercise the real Entra navigation middleware, injecting only its boundary.
    monkeypatch.setattr("src.console_entra_routes_v1.MicrosoftLogin", lambda config: None)
    identity = SimpleNamespace(config=None, renew_session=unavailable)
    install_entra_routes(app, console, identity, render_page=_page)
    client = TestClient(app, base_url="https://testserver", cookies=login_client.cookies)
    cookie = client.cookies.get("console_session")
    response = client.get("/settings", follow_redirects=False)
    assert response.status_code == 503
    assert "tijdelijk niet beschikbaar" in response.text
    assert 'href="/login"' not in response.text
    assert client.cookies.get("console_session") == cookie
    identity.renew_session = lambda token: {}
    assert client.get("/settings").status_code == 200


def test_invalid_session_still_denies_protected_page(tmp_path):
    client = TestClient(create_console_app(_console(tmp_path)))
    client.cookies.set("console_session", "invalid-test-session")
    response = client.get("/settings", follow_redirects=False)
    assert response.status_code == 401
    assert 'class="doc-card"' not in response.text


def run_session_script(html, *, status=401, remaining=0, reason="idle", ticks=0, click=False, path="/"):
    """Execute the rendered browser code, with only DOM/network/clock replaced."""
    node = shutil.which("node")
    assert node, "Node.js is required to verify session browser behavior"
    script = next(s for s in re.findall(r"<script>(.*?)</script>", html, re.S)
                  if "const sessionWarning =" in s)
    result = subprocess.run([node, "-e", r"""
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const callbacks = {};
const warning = {hidden: true};
const text = {textContent: ''};
const title = {textContent: 'Je sessie verloopt bijna'};
const button = {textContent: '', addEventListener: (_, fn) => {callbacks.click = fn;}};
const elements = {
  '[data-session-warning]': warning, '[data-session-warning-text]': text,
  '[data-session-renew]': button, '#session-warning-title': title
};
const requests = [];
const sandbox = {
  document: {
    querySelector: (selector) => {
      const attr = selector.slice(1, -1);
      return (selector[0] === '#' || input.html.includes(attr)) ? elements[selector] || null : null;
    },
    querySelectorAll: () => []
  },
  location: {pathname: input.path, search: '', href: ''},
  window: {setInterval: (fn, ms) => {callbacks[ms] = fn;}},
  fetch: async (url) => {
    requests.push(url);
    return {status: input.status, ok: input.status === 200,
      json: async () => ({remaining_seconds: input.remaining, warning_reason: input.reason})};
  }
};
// Use actual attributes in the rendered HTML, not JS selector strings.
input.html = input.html.replace(/<script>[\s\S]*?<\/script>/g, '');
vm.runInNewContext(input.script, sandbox);
setImmediate(async () => {
  for (let i = 0; i < input.ticks; i++) if (callbacks[1000]) callbacks[1000]();
  if (input.click && callbacks.click) await callbacks.click();
  process.stdout.write(JSON.stringify({requests, hidden: warning.hidden,
    text: text.textContent, title: title.textContent, button: button.textContent,
    href: sandbox.location.href}));
});
"""], input=json.dumps(dict(html=html, script=script, status=status, remaining=remaining,
                            reason=reason, ticks=ticks, click=click, path=path)),
                            text=True, capture_output=True, check=True, timeout=10)
    return json.loads(result.stdout)


@pytest.mark.parametrize("path", ["/", "/login"])
def test_anonymous_page_never_checks_or_warns_about_session(tmp_path, path):
    client = TestClient(create_console_app(_console(tmp_path)))
    result = run_session_script(client.get(path).text, path=path)
    assert result["requests"] == []
    assert result["hidden"] is True


@pytest.mark.parametrize("status,remaining,reason,ticks,expected_title", [
    (401, 0, "idle", 0, "Je sessie is verlopen"),
    (200, 1, "idle", 1, "Je sessie is verlopen"),
    (200, 60, "idle", 0, "Je sessie verloopt bijna"),
    (200, 60, "absolute", 0, "Je sessie verloopt bijna"),
])
def test_authenticated_session_warning_and_renewal(tmp_path, status, remaining, reason, ticks, expected_title):
    console = _console(tmp_path)
    _accounts(console)
    result = run_session_script(_client(console).get("/").text, status=status,
                                remaining=remaining, reason=reason, ticks=ticks, click=True)
    assert result["hidden"] is False
    assert result["title"] == expected_title
    if status == 401 or ticks or reason == "absolute":
        assert result["button"] == "Opnieuw aanmelden"
        assert result["href"].startswith("/auth/microsoft?next=")
    else:
        assert result["requests"] == ["/session/status", "/session/renew"]


def test_session_poll_outage_does_not_claim_expiry(tmp_path):
    console = _console(tmp_path)
    _accounts(console)
    result = run_session_script(_client(console).get("/").text, status=503)
    assert result["hidden"] is True
    assert result["href"] == ""
