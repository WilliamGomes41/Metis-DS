"""Issue #458: actionable errors and honest pending submission feedback.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import re
import shutil
import subprocess

import pytest

from src.operations_console_v1 import ConsoleError
from test_vsa_review_workboard_v1 import _client, _login, _system


def test_error_has_safe_fallback_and_ingest_return_link(tmp_path, monkeypatch):
    console, _, _, _ = _system(tmp_path)
    client = _client(console)
    _login(client, "researcher.anne")

    def fail(**kwargs):
        raise ConsoleError("unexpected_<code>", "private internal detail")

    monkeypatch.setattr(console, "ingest", fail)
    response = client.post("/ingest", data={
        "ingest_kind": "new", "title": "Test", "version": "1.0", "date": "2026-09-29",
        "class_": "richtlijn", "family": "Test",
    })
    assert response.status_code == 400
    assert "Controleer de huidige status" in response.text
    assert '<a href="/ingest">Terug naar Inleveren</a>' in response.text
    assert '<details><summary>Technische informatie' in response.text
    assert "unexpected_&lt;code&gt;" in response.text
    assert "private internal detail" not in response.text
    anonymous = _client(console).get("/ingest")
    assert anonymous.status_code == 401
    assert "Meld je aan" in anonymous.text


def test_ingest_pending_prevents_repeat_and_restores_on_pageshow(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required to execute the rendered submission handlers")
    console, _, _, _ = _system(tmp_path)
    client = _client(console)
    _login(client, "researcher.anne")
    html = client.get("/ingest").text
    script = next(s for s in re.findall(r"<script>(.*?)</script>", html, re.S) if 'ingest-submit' in s)
    # Execute the shipped handler against a small DOM interface; input fields
    # must remain enabled so native multipart submission includes their values.
    harness = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const handlers = {}, windowHandlers = {};
const form = {addEventListener: (name, fn) => handlers[name] = fn,
    setAttribute: (k, v) => form[k] = v, removeAttribute: k => delete form[k]};
const button = {form, disabled: false, textContent: 'Inleveren'};
const status = {hidden: true, textContent: ''};
const kind = {value: 'new', addEventListener: () => {}};
const row = {};
const fields = {'ingest-submit': button, 'ingest-status': status, ingest_kind: kind, 'replaces-row': row};
const document = {getElementById: id => fields[id], querySelector: () => null};
const window = {addEventListener: (name, fn) => windowHandlers[name] = fn};
vm.runInNewContext(SCRIPT, {document, window});
let prevented = 0;
const event = {preventDefault: () => prevented++};
handlers.submit(event);
assert.equal(prevented, 0);
assert.equal(button.disabled, true);
assert.equal(status.hidden, false);
assert.match(status.textContent, /enkele minuten/);
assert.equal(form['aria-busy'], 'true');
handlers.submit(event);
assert.equal(prevented, 1);
windowHandlers.pageshow();
assert.equal(button.disabled, false);
assert.equal(status.hidden, true);
assert.equal(form['aria-busy'], undefined);
handlers.submit(event);
assert.equal(prevented, 1);
'''
    result = subprocess.run([node, '-e', harness.replace('SCRIPT', json.dumps(script))], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'id="ingest-status" role="status" aria-live="polite"' in html
