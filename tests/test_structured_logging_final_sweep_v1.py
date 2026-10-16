"""#638 final sweep (Metis 15:37): one complete pass over the leak classes. Each test MOET fail before its fix.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import io
import logging
from collections import UserDict

import pytest

from src.structured_logging_v1 import RedactingFilter, redact

S = 'opaque-secret'
HEADERS = ['authorization', 'Authorization', 'AUTHORIZATION', 'proxy-authorization', 'proxy_authorization',
           'cookie', 'set-cookie', 'set_cookie', 'x-api-key', 'x_api_key', 'api-key', 'X-Api-Key',
           'ocp-apim-subscription-key', 'ocp_apim_subscription_key', 'x-functions-key', 'x_functions_key',
           'x-ms-client-secret', 'http_authorization', 'HTTP_AUTHORIZATION', 'x-custom-api-key']
FORMS = ['{k}: {s}', '{k}:{s}', '{k} : {s}', '{k}={s}', '{k} = {s}', '"{k}": "{s}"', "'{k}': '{s}'",
         '"{k}":"{s}"', "{k}='{s}'", '{k}="{s}"', "('{k}', '{s}')", "(b'{k}', b'{s}')", "['{k}', '{s}']",
         "[b'{k}', b'{s}']", '["{k}", "{s}"]', '[[b\'{k}\', b\'{s}\']]', "{{'{k}': b'{s}'}}",
         "{k}: bytearray(b'{s}')", 'headers={k}: {s}', '{k}\t:\t{s}']


@pytest.mark.parametrize('form', FORMS)
@pytest.mark.parametrize('key', HEADERS)
def test_every_header_form(key, form):
    assert S not in redact(form.format(k=key, s=S))


@pytest.mark.parametrize('param', ['response', 'cnonce', 'nonce', 'opaque', 'username', 'realm', 'uri', 'nc', 'qop'])
@pytest.mark.parametrize('scheme', ['Digest', 'digest', 'DIGEST'])
@pytest.mark.parametrize('style', ['{p}="{s}"', '{p}={s}', '{p} = "{s}"', "{p}='{s}'", '{p}*=UTF-8\'\'{s}'])
def test_every_digest_param(scheme, param, style):
    lead = 'realm="r", ' if param != 'realm' else 'nonce="n", '
    text = f'{scheme} {lead}{style.format(p=param, s=S)}, algorithm=MD5'
    assert S not in redact(text)
    assert S not in redact('Authorization: ' + text)


@pytest.mark.parametrize('text', [
    '{"password":"a\\"' + S + '"}', "{'token': 'a\\'" + S + "'}", 'Authorization: "a\\"' + S + '"',
    'password="a\\\\\\"' + S + '"', "secret='\\'" + S + "'",
])
def test_escaped_quotes(text):
    assert S not in redact(text)


@pytest.mark.parametrize('value', [S.encode(), bytearray(S.encode())])
def test_bytes_values(value):
    assert S not in redact(b'password=' + bytes(value) if isinstance(value, bytes) else 'password=' + repr(value))


def _render(msg, args=None, **extra):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter('%(message)s|' + '|'.join('%(' + k + ')s' for k in extra) + '|%(args)s'))
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger('test.final.sweep')
    logger.addHandler(handler)
    logger.propagate = False
    try:
        if args is None:
            logger.warning(msg, extra=extra)
        else:
            logger.warning(msg, args, extra=extra)
    finally:
        logger.removeHandler(handler)
    return stream.getvalue()


@pytest.mark.parametrize('payload', [
    UserDict({'authorization': S}), {'a': UserDict({'token': S})}, [{'b': [{'password': S}]}],
    {'headers': [[b'authorization', S.encode()]]}, {'headers': [['cookie', 'sessionid=' + S]]},
    ValueError('password=' + S), {'e': ValueError('Authorization: Bearer ' + S)},
    {'k': {'deep': {'deeper': ('x', {'api_key': S})}}}, {'raw': b'password=' + S.encode()},
    {'anne@example.com': 'owner'}, frozenset({'token=' + S}),
])
def test_nested_extras(payload):
    out = _render('x', payload=payload)
    assert S not in out and 'anne@example.com' not in out


def test_top_level_mapping_arg_keys():
    out = _render('%(owner)s', {'owner': 'loaded', 'anne@example.com': 'admin'})
    assert 'anne@example.com' not in out


@pytest.mark.parametrize('arg', [S.encode(), bytearray(S.encode()), UserDict({'v': S}), [S]])
def test_str_and_bytes_positional_args_after_credential(arg):
    assert S not in _render('password=%s', arg)


def test_bytes_message():
    assert S not in _render(b'password=' + S.encode())
