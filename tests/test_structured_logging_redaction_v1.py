"""#627 fix: structured log redaction (Sherlock retro-audit) and library logger levels.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop

Rules (B18): emails, Basic/Bearer/other Authorization values, API-key headers and
Cookie/Set-Cookie values MAG NIET leave the JSON formatter; library loggers MOETEN
stay at WARNING after install_structured_logging.
"""
import json
import logging

import pytest

from src.structured_logging_v1 import JsonLogFormatter, install_structured_logging, redact

SECRETS = ['anne.de.vries@example.nl', 'dXNlcjpodW50ZXIy', 'abc.def.ghi', 'sessionid=s3cr3t', 's3cr3t',
           'hunter2', 'k3y-value-9', 'csrf=t0k']


@pytest.mark.parametrize('text', [
    'login failed for anne.de.vries@example.nl',
    'Authorization: Basic dXNlcjpodW50ZXIy',
    "headers={'Authorization': 'Basic dXNlcjpodW50ZXIy', 'Accept': 'x'}",
    'authorization=Digest username="hunter2", nonce="k3y-value-9"',
    'Proxy-Authorization: Negotiate abc.def.ghi',
    'Authorization: abc.def.ghi',
    'Cookie: sessionid=s3cr3t; csrf=t0k',
    'Set-Cookie: sessionid=s3cr3t; Path=/; HttpOnly',
    '{"Cookie": "sessionid=s3cr3t; csrf=t0k"}',
    'X-Api-Key: k3y-value-9',
    'api-key: k3y-value-9',
    'Ocp-Apim-Subscription-Key: k3y-value-9',
    'password="hunter2"',
    '{"password":"hunter2"}',
    "{'client_secret': 'hunter2'}",
    'Basic dXNlcjpodW50ZXIy',
])
def test_sensitive_values_are_redacted(text):
    out = redact(text)
    assert not any(secret in out for secret in SECRETS), out
    assert '[REDACTED' in out


def test_safe_text_is_unchanged():
    text = 'attempt pa_123 finished state=incomplete_budget snapshot snap-1 basic flow'
    assert redact(text) == text


def test_formatter_redacts_email_and_cookie_in_rendered_message():
    record = logging.LogRecord('metis.x', logging.WARNING, __file__, 1,
                               'user %s cookie %s', ('anne.de.vries@example.nl', 'Cookie: sessionid=s3cr3t'), None)
    row = json.loads(JsonLogFormatter().format(record))
    assert 'example.nl' not in row['message'] and 's3cr3t' not in row['message']


LIBRARIES = ('azure', 'azure.core.pipeline.policies.http_logging_policy', 'urllib3', 'httpx', 'httpcore',
             'openai', 'msal', 'psycopg', 'asyncio')


def test_library_loggers_stay_at_warning(monkeypatch):
    for name in LIBRARIES:
        monkeypatch.setattr(logging.getLogger(name), 'level', logging.NOTSET)
    install_structured_logging()
    for name in LIBRARIES:
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING, name
        assert not logging.getLogger(name).isEnabledFor(logging.INFO), name
