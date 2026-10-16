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


def test_sensitive_extra_fields_are_redacted_for_foreign_formatters():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter('%(message)s|%(authorization)s|%(note)s'))
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger('test.extra.redaction')
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.warning('x', extra={'authorization': 'opaque-secret-1', 'note': 'mail anne@example.nl'})
    finally:
        logger.removeHandler(handler)
    out = stream.getvalue()
    assert 'opaque-secret-1' not in out and 'anne@example.nl' not in out


@pytest.mark.parametrize('text', [
    "headers=[(b'authorization', b'opaque-secret')]",
    "scope headers [(b'cookie', b'opaque-secret'), (b'accept', b'*/*')]",
    "('Authorization', 'opaque-secret')",
    '("x-api-key", "opaque-secret")',
])
def test_tuple_shaped_header_pairs_are_redacted(text):
    # 4291899701: ASGI/HTTP-client header pairs use a comma, not = or :.
    out = redact(text)
    assert 'opaque-secret' not in out


@pytest.mark.parametrize('text', ['to user@[127.0.0.1] now', 'to anne.v@[IPv6:2001:db8::1] now', 'to "a b"@[10.0.0.1]'])
def test_domain_literal_emails_are_redacted(text):
    # 4291899714: bracketed domain literals.
    out = redact(text)
    assert '@[' not in out or '[REDACTED]' in out.split('@')[0]
    for part in ('user@', 'anne.v', '127.0.0.1', '2001:db8', '10.0.0.1'):
        assert part not in out


@pytest.mark.parametrize('value', [{'token': 'opaque-secret'}, ['opaque-secret'], ('opaque-secret',)])
def test_non_string_sensitive_extra_values_are_replaced(value):
    # 4292037261: a sensitive extra key MOET be replaced whatever the value type.
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter('%(message)s|%(authorization)s'))
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger('test.extra.nonstring')
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.warning('x', extra={'authorization': value})
    finally:
        logger.removeHandler(handler)
    assert 'opaque-secret' not in stream.getvalue()


def test_digest_username_star_parameter_list_is_fully_redacted():
    # 4292037272: RFC 7616 username* parameter.
    out = redact("Digest username*=UTF-8''Mufasa, nonce=\"abc123\", response=\"6629fae49393\"")
    for part in ('Mufasa', 'abc123', '6629fae49393'):
        assert part not in out


def test_quoted_email_local_part_with_escaped_quote_is_redacted():
    # 4292037282: RFC 5322 quoted-string with an escaped quote.
    out = redact('from "john\\"doe"@example.org now')
    assert 'john' not in out and 'example.org' not in out


@pytest.mark.parametrize('text', ["password=b'hunter2'", 'token=b"hunter2"', "{'password': b'hunter2'}", "Authorization: b'hunter2'"])
def test_bytes_shaped_credentials_are_redacted(text):
    # 4293501888
    assert 'hunter2' not in redact(text)


def test_digest_params_with_spaces_around_equals_are_redacted():
    # 4293501898
    out = redact('Digest username = "Mufasa" , nonce = "abc123", response = "6629fae49393"')
    for part in ('Mufasa', 'abc123', '6629fae49393'):
        assert part not in out


@pytest.mark.parametrize('value', [{'auth': {'password': 'opaque-secret'}}, [{'token': 'opaque-secret'}],
                                   {'note': 'mail anne@example.nl'}, ('Bearer opaque-secret',)])
def test_nested_values_in_non_string_extras_are_redacted(value):
    # 4293501908
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter('%(message)s|%(payload)s'))
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger('test.extra.nested')
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.warning('x', extra={'payload': value})
    finally:
        logger.removeHandler(handler)
    out = stream.getvalue()
    assert 'opaque-secret' not in out and 'anne@example.nl' not in out


# --- Metis 12:21: one complete pass over header and extra forms ---

@pytest.mark.parametrize('text', [
    "password=bytearray(b'hunter2')",
    "Authorization: bytearray(b'hunter2')",
    "(b'authorization', bytearray(b'hunter2'))",
    'Bearer\t\thunter2',
    'Basic    hunter2',
    "Bearer 'hunter2'",
    'Bearer "hunter2"',
    'BEARER=hunter2',
    'authorization : Bearer   hunter2',
    'Digest\tusername="u"\t,\tresponse="hunter2"',
    "Digest realm*=UTF-8''x, username*=UTF-8'en'hunter2, response=hunter2",
    "Digest username='u', response='hunter2'",
    'Digest username=u,response=hunter2',
    "{b'password': b'hunter2'}",
    "{'Authorization': b'Bearer hunter2'}",
])
def test_complete_header_forms_are_redacted(text):
    assert 'hunter2' not in redact(text), redact(text)


def _render_extra(value, key='payload'):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter('%(message)s|%(' + key + ')s'))
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger('test.extra.complete')
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.warning('x', extra={key: value})
    finally:
        logger.removeHandler(handler)
    return stream.getvalue()


@pytest.mark.parametrize('value', [
    {'a': {'b': {'c': {'password': 'hunter2'}}}},
    [[[('token', 'hunter2')]]],
    {'list': [{'Authorization': 'hunter2'}]},
    {'deep': [({'x': 'Bearer hunter2'},)]},
    b'password=hunter2',
    bytearray(b'Bearer hunter2'),
    {'k': b'Bearer hunter2'},
    {b'password': 'hunter2'},
    {'s': {'mail anne@example.nl'}},
])
def test_extra_values_at_any_depth_are_redacted(value):
    out = _render_extra(value)
    assert 'hunter2' not in out and 'anne@example.nl' not in out, out


@pytest.mark.parametrize('key', ['password', 'Authorization', 'x_api_key'])
@pytest.mark.parametrize('value', [b'hunter2', bytearray(b'hunter2'), 12345678, {'v': 'hunter2'}])
def test_sensitive_extra_keys_replace_any_value(key, value):
    out = _render_extra(value, key=key)
    assert 'hunter2' not in out and '12345678' not in out, out


@pytest.mark.parametrize('text', ['mail admin@localhost now', 'to anne@intranet', 'josé@mailhost', '"a b"@localhost'])
def test_mailbox_with_dotless_domain_is_redacted(text):
    # 4293592622 (PII): RFC 5321 permits dotless domains such as localhost.
    out = redact(text)
    for part in ('admin@', 'anne@', 'josé', '"a b"@'):
        assert part not in out, out


@pytest.mark.parametrize('text', ['password="hunter2\\', "token='hunter2\\", 'Authorization: "hunter2\\'])
def test_unterminated_quoted_secret_with_dangling_escape_is_redacted(text):
    # 4293913967
    assert 'hunter2' not in redact(text)


@pytest.mark.parametrize('text', ['to customer/department=shipping@example.com now', "from o'hara@example.com", 'x!y#z$%&*+?^`{|}~-q@example.org'])
def test_full_dot_atom_local_parts_are_redacted(text):
    # 4293913980 (PII)
    out = redact(text)
    for part in ('customer', 'department', 'shipping', "o'hara", 'hara', 'x!y', 'q@'):
        assert part not in out, out


def _filtered_message(msg, args):
    record = logging.LogRecord('x', logging.WARNING, __file__, 1, msg, None, None)
    record.args = args
    RedactingFilter().filter(record)
    return record.getMessage()


def test_non_dict_mapping_args_use_sensitive_key_redaction():
    # 4294352255
    from collections import UserDict
    assert 'opaque-secret' not in _filtered_message('%(authorization)s', UserDict({'authorization': 'opaque-secret'}))


def test_interpolation_failure_after_redaction_fails_closed():
    # 4294352269
    assert '12345678' not in _filtered_message('%(token)d', {'token': 12345678})


def test_smtputf8_local_part_with_combining_mark_is_redacted():
    # 4294352280 (PII)
    out = redact('mail jos\u0301e@example.com')
    assert 'jos' not in out


@pytest.mark.parametrize('key', ['ocp_apim_subscription_key', 'x_functions_key', 'proxy_authorization', 'set_cookie'])
def test_identifier_normalized_header_extra_keys_are_sensitive(key):
    # 4294629096
    assert 'opaque-secret' not in _render_extra('opaque-secret', key=key)


def test_nested_mapping_keys_are_redacted():
    # 4294629108
    assert 'anne@example.com' not in _render_extra({'context': {'anne@example.com': 'owner'}})


@pytest.mark.parametrize('arg', [{'value': 'opaque-secret'}, ['opaque-secret'], ('opaque-secret', 1)])
def test_positional_container_after_sensitive_placeholder_is_redacted(arg):
    # 4294629122
    assert 'opaque-secret' not in _filtered_message('password=%s', (arg,))


def test_reserved_handler_name_alone_is_not_trusted():
    # 4294985552: a host handler named metis-structured-json with a plain formatter MOET be filtered.
    import io
    from src.structured_logging_v1 import install_structured_logging, _HANDLER_NAME
    root = logging.getLogger()
    saved, level = list(root.handlers), root.level
    stream = io.StringIO()
    impostor = logging.StreamHandler(stream)
    impostor.set_name(_HANDLER_NAME)
    impostor.setFormatter(logging.Formatter('%(message)s'))
    try:
        root.handlers = [impostor]
        install_structured_logging()
        logging.getLogger('impostor.test').warning('Authorization: Bearer opaque-secret')
    finally:
        root.handlers, root.level = saved, level
    assert 'opaque-secret' not in stream.getvalue()
