"""Raad: shell only after sign-in, read-only route, existing view-check gates.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
import re
import subprocess

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import src.settings.view_check as view_check
from src import care_companion_v1
from src.operations_console_app import _nav
from src.operations_console_v1 import ConsoleError

pytestmark = pytest.mark.pure_function

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "assets/brand/care-companion.js"
ACCOUNT = {"account_id": "reviewer-1", "display_name": "Rita", "roles": ["reviewer"]}


def test_companion_renders_only_in_authenticated_navigation():
    signed_in = _nav(ACCOUNT, "review")
    assert 'data-care-companion' in signed_in and 'data-room="review"' in signed_in
    # After the session warning, so CSS can lift it above a visible warning.
    assert signed_in.index('data-session-warning') < signed_in.index('data-care-companion')
    assert 'data-care-companion' not in _nav(None)


def test_markup_escapes_room_and_versions_script_by_content():
    html = care_companion_v1.markup('"><script>x</script>')
    assert '<script>x' not in html and '&quot;&gt;&lt;script&gt;' in html
    assert re.search(r'src="/brand/care-companion\.js\?v=[0-9a-f]{16}" defer', html)


def test_script_is_valid_and_never_injects_server_text_as_html():
    subprocess.run(["node", "--check", str(SCRIPT)], check=True)
    source = SCRIPT.read_text(encoding="utf-8")
    assert "innerHTML" not in source and "insertAdjacentHTML" not in source and "eval(" not in source
    # The only mutation it performs is the existing view-check form.
    assert re.findall(r"method: 'post', action: '([^']+)'", source) == ["/inzicht/document/weergavecontrole"]


class Store:
    def __init__(self):
        self.rows = [{"id": "a" * 32, "state": "completed", "created_at": "2026-10-22T13:00:00+00:00",
                      "result": {"reason": "completed", "evidence": [{"key": "k"}],
                                 "checks": [{"verdict": "pass"}, {"verdict": "fail"}, {"verdict": "not_established"}]}},
                     {"id": "b" * 32, "state": "unexpected", "created_at": "", "result": None}]

    def history(self, document):
        assert document == "doc-1"
        return self.rows


def client(service=None, signed_in=True):
    app = FastAPI()
    app.state.view_checks = service

    def require(_request):
        if not signed_in:
            raise ConsoleError("not_authenticated")
        return ACCOUNT

    care_companion_v1.install(app, object(), require)

    @app.exception_handler(ConsoleError)
    async def refuse(_request, _error):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "not_authenticated"}, status_code=401)
    return TestClient(app)


def test_route_requires_sign_in():
    assert client(signed_in=False).get("/raad/weergavecontrole?document=doc-1").status_code == 401


@pytest.mark.parametrize("query,reason", [("", "no_document"), ("document=" + "x" * 201, "no_document"),
                                          ("document=doc-1", "not_configured")])
def test_route_reports_unavailable_without_document_or_service(query, reason):
    response = client().get("/raad/weergavecontrole?" + query)
    assert response.json() == {"available": False, "reason": reason}
    assert response.headers["cache-control"] == "no-store"


def test_route_uses_the_existing_reviewer_authorization(monkeypatch):
    def deny(_state, _actor, _document):
        raise view_check.ViewCheckAccessDenied("reviewer_not_named_on_snapshot")
    monkeypatch.setattr(view_check, "authorize", deny)
    body = client(type("Service", (), {"store": Store()})()).get("/raad/weergavecontrole?document=doc-1").json()
    assert body == {"available": False, "reason": "not_named_reviewer"}


def test_route_offers_the_existing_form_and_bounded_history(monkeypatch):
    monkeypatch.setattr(view_check, "authorize", lambda *_args: (ACCOUNT, {}))
    monkeypatch.setattr(view_check, "context", lambda _s, actor, document, attempt: {"revision": "rev-7"})
    body = client(type("Service", (), {"store": Store()})()).get(
        "/raad/weergavecontrole?document=doc-1&attempt=att-1").json()
    form = body["form"]
    assert body["available"] is True
    assert {k: form[k] for k in ("document", "attempt", "expected_revision")} == {
        "document": "doc-1", "attempt": "att-1", "expected_revision": "rev-7"}
    assert re.fullmatch(r"[0-9a-f]{32}", form["request_key"])
    first, second = body["checks"]
    assert (first["passed"], first["differences"], first["not_established"], first["evidence"]) == (1, 1, 1, True)
    assert second["state"] == "failed" and second["evidence"] is False


def test_route_keeps_history_but_no_form_when_the_scenario_is_unsupported(monkeypatch):
    monkeypatch.setattr(view_check, "authorize", lambda *_args: (ACCOUNT, {}))

    def unsupported(*_args):
        raise ValueError("scenario_not_supported")
    monkeypatch.setattr(view_check, "context", unsupported)
    body = client(type("Service", (), {"store": Store()})()).get("/raad/weergavecontrole?document=doc-1").json()
    assert body["form"] is None and body["reason"] == "not_supported" and len(body["checks"]) == 2


def test_docling_image_pins_ci_playwright_and_guards_the_render_fonts():
    dockerfile = (ROOT / "Dockerfile.docling").read_text(encoding="utf-8")
    action = (ROOT / ".github/actions/install-test-browser/action.yml").read_text(encoding="utf-8")
    ci_version = re.search(r"playwright@([0-9.]+)", action).group(1)
    assert re.findall(r"playwright@([0-9.]+)", dockerfile) == [ci_version]
    # Font packages are excluded and the Docling font inventory must be unchanged.
    assert "grep -v -E '^(fonts-.*|xfonts-.*|xvfb)$'" in dockerfile
    assert 'test "$before" = "$(fonts)"' in dockerfile
    assert "--with-deps" not in dockerfile
    # The browser layer precedes model preparation, which records the font inventory.
    assert dockerfile.index("playwright@") < dockerfile.index("prepare_docling_models.py /opt/docling-models")
    assert "METIS_BROWSER_EXECUTABLE=/opt/metis-browser/chrome-headless-shell" in dockerfile
    prep = (
        "src/vorming/__init__.py",
        "src/vorming/docling_contract_v1.py",
        "src/vorming/docling_render_fonts_v1.py",
    )
    assert all(name in dockerfile for name in prep)
    assert all((ROOT / name).is_file() for name in prep)


def test_deploy_check_opens_the_navigation_rooms_in_a_frame_that_cannot_submit():
    source = SCRIPT.read_text(encoding="utf-8")
    listed = re.search(r"const DEPLOY_PAGES = \[(.*?)\]\.map", source, re.S).group(1)
    paths = re.findall(r"'(/[^']*)'\]", listed)
    rooms = re.findall(r'<a href="(/[^"]*)"', re.search(r'<nav class="rooms">(.*?)</nav>', _nav(ACCOUNT), re.S).group(1))
    assert paths == rooms + ["/inzicht"]
    # Same-origin reads only: no forms, popups, downloads or top-level navigation.
    assert re.findall(r"sandbox: '([^']*)'", source) == ["allow-same-origin allow-scripts"]
    # Raad inside a probed page only counts errors; it never opens or fetches.
    assert "if (embedded) return;" in source
    assert source.index("if (embedded) return;") < source.index("setOpen(true, false)")
    # Copy verdicts are exercised through the actual button in browser_deploy_check.cjs.
