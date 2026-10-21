"""#627 fix: structured log redaction (Sherlock retro-audit) and library logger levels.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs

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
    text = 'attempt pa_123 finished state=incomplete_budget snapshot snap-1'
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


# --- OPENVRAAG-627-1 closed: pre-existing root handlers and the performance logger ---

def test_preexisting_root_handler_emits_only_redacted_text():
    import io
    stream = io.StringIO()
    foreign = logging.StreamHandler(stream)
    foreign.setFormatter(logging.Formatter('%(message)s'))
    root = logging.getLogger()
    root.addHandler(foreign)
    try:
        install_structured_logging()
        logging.getLogger('metis.test.foreign').warning('login %s password=%s', 'anne.de.vries@example.nl', 'hunter2')
    finally:
        root.removeHandler(foreign)
    out = stream.getvalue()
    assert 'hunter2' not in out and 'example.nl' not in out and '[REDACTED' in out


def test_performance_logger_goes_through_the_json_formatter():
    from fastapi import FastAPI
    from src.console_performance_v1 import _LOGGER as perf, install_console_performance
    saved = list(perf.handlers)
    for h in saved:
        perf.removeHandler(h)
    try:
        install_console_performance(FastAPI())
        assert perf.handlers and all(isinstance(h.formatter, JsonLogFormatter) for h in perf.handlers)
        record = logging.LogRecord(perf.name, logging.INFO, __file__, 1, 'perf Cookie: sessionid=s3cr3t', (), None)
        row = json.loads(perf.handlers[0].format(record))
        assert row['logger'] == perf.name and 's3cr3t' not in row['message']
    finally:
        for h in list(perf.handlers):
            perf.removeHandler(h)
        for h in saved:
            perf.addHandler(h)


# --- Sherlock re-audit #638 F1: exc_info MAG NIET leak secrets through foreign handlers ---

def _foreign(stream):
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter('%(message)s'))  # default formatter appends the traceback
    return handler


def test_exception_message_secret_is_redacted_in_foreign_handler():
    import io
    stream = io.StringIO()
    foreign = _foreign(stream)
    root = logging.getLogger()
    root.addHandler(foreign)
    try:
        install_structured_logging()
        try:
            raise RuntimeError('connect failed password=hunter2 for anne.de.vries@example.nl')
        except RuntimeError:
            logging.getLogger('metis.test.exc').exception('upstream failed')
    finally:
        root.removeHandler(foreign)
    out = stream.getvalue()
    assert 'hunter2' not in out and 'example.nl' not in out
    assert 'RuntimeError' in out and 'Traceback' not in out


def test_json_formatter_exception_secret_never_rendered():
    try:
        raise ValueError('token=abc123secret')
    except ValueError:
        import sys
        record = logging.LogRecord('x', logging.ERROR, __file__, 1, 'boom', (), sys.exc_info())
    out = JsonLogFormatter().format(record)
    assert 'abc123secret' not in out and json.loads(out)['exc_type'] == 'ValueError'


# --- Sherlock re-audit #638 F2: known non-propagating loggers are covered explicitly ---

@pytest.mark.parametrize('name', ['uvicorn', 'uvicorn.error', 'uvicorn.access', 'gunicorn.error', 'gunicorn.access'])
def test_non_propagating_logger_handlers_emit_only_redacted_text(name):
    import io
    stream = io.StringIO()
    logger = logging.getLogger(name)
    saved = (list(logger.handlers), logger.propagate, logger.level)
    handler = _foreign(stream)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        install_structured_logging()
        logger.info('GET / Authorization: Bearer abcdefghijk cookie=sessionid=s3cr3t')
        try:
            raise OSError('password=hunter2')
        except OSError:
            logger.exception('failed')
    finally:
        logger.handlers, logger.propagate = saved[0], saved[1]
        logger.setLevel(saved[2])
    out = stream.getvalue()
    assert 'abcdefghijk' not in out and 's3cr3t' not in out and 'hunter2' not in out
    assert '[REDACTED]' in out


# --- Metis 638-1: re-install idempotently at startup, AFTER the server's own log setup ---

@pytest.mark.parametrize('name', ['uvicorn.error', 'uvicorn.access', 'gunicorn.error'])
def test_server_handlers_added_after_build_are_redacted_after_startup(name):
    import io
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.structured_logging_v1 import install_startup_reinstall
    app = FastAPI()
    install_structured_logging()
    install_startup_reinstall(app)
    logger = logging.getLogger(name)
    saved = (list(logger.handlers), logger.propagate, logger.level)
    stream = io.StringIO()
    logger.handlers = [_foreign(stream)]  # server dictConfig runs after build_app()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        with TestClient(app):  # runs startup
            logger.info('Cookie: sessionid=s3cr3t password=hunter2')
            install_structured_logging()  # idempotent: no second filter, no second root handler
            assert sum(1 for f in logger.handlers[0].filters if f.__class__.__name__ == 'RedactingFilter') == 1
    finally:
        logger.handlers, logger.propagate = saved[0], saved[1]
        logger.setLevel(saved[2])
    out = stream.getvalue()
    assert 's3cr3t' not in out and 'hunter2' not in out and '[REDACTED]' in out
    assert sum(1 for h in logging.getLogger().handlers if getattr(h, 'name', None) == 'metis-structured-json') == 1


def test_build_app_registers_the_startup_reinstall(production_app):
    assert install_structured_logging in production_app().router.on_startup


# --- Sherlock 02:10 #638 F1: record.args stays a redacted tuple (NEVER None); real uvicorn AccessFormatter ---

def test_uvicorn_access_formatter_works_and_redacts_after_filter():
    from uvicorn.logging import AccessFormatter
    from src.structured_logging_v1 import RedactingFilter
    formatter = AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False)
    record = logging.LogRecord('uvicorn.access', logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                               ('10.0.0.1:5000', 'GET', '/login?token=abc123secret&email=anne@example.nl', '1.1', 200), None)
    assert RedactingFilter().filter(record) is True
    assert isinstance(record.args, tuple) and len(record.args) == 5
    out = formatter.format(record)
    assert 'abc123secret' not in out and 'example.nl' not in out and '200' in out and 'GET' in out


def test_redacting_filter_never_sets_args_to_none():
    from src.structured_logging_v1 import RedactingFilter
    for args in ((), ('password=hunter2',), None):
        record = logging.LogRecord('x', logging.INFO, __file__, 1, 'm %s' if args else 'm', args, None)
        RedactingFilter().filter(record)
        assert record.args is not None and 'hunter2' not in record.getMessage()


def test_contract_attributes_f2_acceptance_to_metis():
    # Sherlock 02:55: F2 (handlers added after startup) was accepted by Metis, not by Sherlock.
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / 'docs' / 'change-contracts' / 'a2-log-redaction.md').read_text()
    assert 'accepted by Sherlock' not in text and 'accepted by Metis' in text


@pytest.mark.parametrize('path', ['/a?cookie=s3cr3t', '/a?Authorization: Bearer s3cr3tvalue', '/a?password=s3cr3t'])
def test_uvicorn_access_redacts_each_arg_and_keeps_five_args(path):
    # Sherlock 02:55: uvicorn.access MOET keep its 5 positional args, each redacted.
    from uvicorn.logging import AccessFormatter
    from src.structured_logging_v1 import RedactingFilter
    record = logging.LogRecord('uvicorn.access', logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                               ('10.0.0.1:5000', 'GET', path, '1.1', 200), None)
    RedactingFilter().filter(record)
    assert isinstance(record.args, tuple) and len(record.args) == 5
    out = AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False).format(record)
    assert 's3cr3t' not in out and '200' in out and 'HTTP/1.1' in out
