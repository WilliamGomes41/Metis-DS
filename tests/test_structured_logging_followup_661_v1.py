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


def test_owned_handler_redacts_logger_name():
    # 4295299116
    row = json.loads(_json(_record('hello', name='tenant.anne@example.com')))
    assert 'anne@example.com' not in json.dumps(row)


@pytest.mark.parametrize('field', ['request_id', 'event', 'attempt_id', 'snapshot_id', 'phase', 'reason_code'])
def test_owned_handler_redacts_whitelisted_extras(field):
    # 4295299116
    row = json.loads(_json(_record('hello', **{field: 'sk-abcdefghijk'})))
    assert 'sk-abcdefghijk' not in json.dumps(row)


def test_reserved_handler_with_overriding_formatter_subclass_is_not_trusted():
    # 4296203798
    from src.structured_logging_v1 import install_structured_logging, _HANDLER_NAME

    class Plain(JsonLogFormatter):
        def format(self, record):
            return record.getMessage()

    root = logging.getLogger()
    saved, level = list(root.handlers), root.level
    stream = io.StringIO()
    impostor = logging.StreamHandler(stream)
    impostor.set_name(_HANDLER_NAME)
    impostor.setFormatter(Plain())
    try:
        root.handlers = [impostor]
        install_structured_logging()
        logging.getLogger('impostor.subclass').warning('Authorization: Bearer opaque-secret')
    finally:
        root.handlers, root.level = saved, level
    assert 'opaque-secret' not in stream.getvalue()


@pytest.mark.parametrize('key', [('owner', 'anne@example.com'), frozenset({'anne@example.com'}), ('a', ('b', 'anne@example.com'))])
def test_composite_keys_in_nested_extras_are_redacted(key):
    # 4296203813
    record = _record('x', context={key: 'admin'})
    RedactingFilter().filter(record)
    assert 'anne@example.com' not in logging.Formatter('%(context)s').format(record)


@pytest.mark.parametrize('addr', ['\U0001F600@example.com', 'a\U0001F600b@example.com', '\u2603@example.com', '\u00a9x@example.com'])
def test_smtputf8_local_part_outside_word_class_is_redacted(addr):
    # 4296203827 (RFC 6531: UTF-8 non-ASCII is atext)
    assert addr.split('@')[0] not in redact('mail ' + addr)
    assert addr.split('@')[0] not in _json(_record('mail %s', (addr,)))


class _Pair(tuple):
    """Tuple subclass whose constructor takes two arguments, not one iterable."""
    def __new__(cls, a, b):
        return super().__new__(cls, (a, b))


@pytest.mark.parametrize('extra', [
    {'context': {_Pair('owner', 'anne@example.com'): 'admin'}},
    {'context': [_Pair('owner', 'anne@example.com')]},
    {'context': {_Pair('authorization', 'opaque-secret'): 'x'}},
])
def test_tuple_subclass_with_custom_constructor_never_raises(extra):
    # 4296870561: redaction MAG NOOIT raise; composite keys are still redacted.
    record = _record('x', **extra)
    assert RedactingFilter().filter(record) is True
    out = logging.Formatter('%(context)s').format(record)
    assert 'anne@example.com' not in out and 'opaque-secret' not in out


class _FrozenMap(dict):
    """A hashable Mapping used as a key."""
    def __hash__(self):
        return hash(tuple(sorted(self.items())))


def test_hashable_mapping_key_never_raises():
    # 4297499491: a key MOET stay hashable after redaction; redaction MAG NOOIT raise.
    record = _record('x', context={_FrozenMap({'owner': 'anne@example.com'}): 'admin'})
    assert RedactingFilter().filter(record) is True
    assert 'anne@example.com' not in logging.Formatter('%(context)s').format(record)


@pytest.mark.parametrize('addr', ['\U0001F600@[127.0.0.1]', '\u2603x@[IPv6:2001:db8::1]'])
def test_smtputf8_local_part_with_domain_literal_is_redacted(addr):
    # 4297911904 (PII)
    assert addr.split('@')[0] not in redact('mail ' + addr)
