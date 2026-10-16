"""#638 Sherlock P1/P2 (2026-10-16): redaction gaps. Each test MOET fail before its fix.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import io
import json
import logging

import pytest

from src.structured_logging_v1 import RedactingFilter, install_structured_logging, redact


def test_escaped_quote_inside_quoted_secret_is_fully_redacted():
    out = redact('{"password":"hunter\\"2tail"}')
    assert 'hunter' not in out and '2tail' not in out
    assert 'hunter' not in redact("Authorization: 'ab\\'cd2tail'") and '2tail' not in redact("Authorization: 'ab\\'cd2tail'")


def test_explicitly_configured_child_library_logger_is_clamped():
    child = logging.getLogger('azure.core.pipeline.policies.http_logging_policy')
    saved = child.level
    child.setLevel(logging.INFO)
    try:
        install_structured_logging()
        assert not child.isEnabledFor(logging.INFO)
    finally:
        child.setLevel(saved)


def test_full_standalone_digest_credential_is_redacted():
    out = redact('sent Digest username="Mufasa", nonce="abc123", response="6629fae49393"')
    for part in ('Mufasa', 'abc123', '6629fae49393'):
        assert part not in out


def test_value_under_sensitive_mapping_key_is_redacted():
    record = logging.LogRecord('x', logging.WARNING, __file__, 1, '%(authorization)s', None, None)
    record.args = {'authorization': 'opaque-secret'}
    RedactingFilter().filter(record)
    assert 'opaque-secret' not in record.getMessage()


def test_existing_performance_handler_gets_redaction():
    import src.console_performance_v1 as perf
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    saved = list(perf._LOGGER.handlers)
    perf._LOGGER.handlers = [handler]
    try:
        class App:
            def middleware(self, _kind):
                return lambda fn: fn

            def add_middleware(self, *_a, **_k):
                pass
        perf.install_console_performance(App())
        perf._LOGGER.info('login anne@example.nl')
        assert 'anne@example.nl' not in stream.getvalue()
    finally:
        perf._LOGGER.handlers = saved


@pytest.mark.parametrize('text', ['Bearer abc', 'Basic YTo=', 'Authorization was Bearer x1'])
def test_short_standalone_scheme_credentials_are_redacted(text):
    secret = text.split()[-1]
    assert secret not in redact(text)


def test_scheme_word_followed_by_word_fails_closed():
    # Metis 2026-10-16: casing MAG NIET decide; prose after a scheme word is redacted (fail-closed).
    assert 'flow' not in redact('use the basic flow')


def test_non_ascii_email_is_redacted():
    assert 'josé' not in redact('mail from josé@example.com')
    assert 'ünïcode' not in redact('to ünïcode.user@exämple.de')


@pytest.mark.parametrize('text', ['bearer abcdefghijk', 'BeArEr abcdefghijk', 'basic YWJj', 'digest abcdef'])
def test_any_case_scheme_redacts_alphabetic_token(text):
    assert text.split()[-1] not in redact(text)


def test_quoted_secret_with_line_break_is_redacted():
    out = redact('password="hunter\nsecond-half"')
    assert 'hunter' not in out and 'second-half' not in out
    assert 'second' not in redact("Authorization: 'ab\r\nsecond'")


def test_email_with_quoted_local_part_is_redacted():
    out = redact('from "john..doe"@example.org today')
    assert 'john..doe' not in out and 'example.org' not in out
