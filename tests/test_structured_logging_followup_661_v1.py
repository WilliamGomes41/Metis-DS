"""#661 redaction hardening follow-up of #638. Each test MOET fail before its fix.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import io
import json
import logging

import pytest

from src.structured_logging_v1 import JsonLogFormatter, RedactingFilter, redact


def _json(record):
    return JsonLogFormatter().format(record)


def _record(msg, args=None, name='x', **extra):
    record = logging.LogRecord(name, logging.WARNING, __file__, 1, msg, args, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


@pytest.mark.parametrize('key', ['password', 'secret', 'token', 'api_key'])
def test_unquoted_value_with_spaces_is_redacted_to_end_of_value(key):
    # 4295299102
    msg = key + '=%s'
    assert 'two' not in redact(key + '=hunter two words')
    assert 'two' not in _json(_record(msg, ('hunter two words',)))
    record = _record(msg, ('hunter two words',))
    RedactingFilter().filter(record)
    assert 'two' not in record.getMessage()


def test_unquoted_value_stops_at_next_assignment():
    out = redact('password=hunter two words user=bob')
    assert 'two' not in out and 'user=bob' in out
