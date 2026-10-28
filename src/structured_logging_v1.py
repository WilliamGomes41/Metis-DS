"""Global structured JSON logging; operational evidence only, never domain state.

Every record MOET be one JSON object with fixed fields. Secrets MAG NOOIT leave
this formatter: known credential shapes (assignments, Authorization and other
auth headers, Cookie/Set-Cookie, emails) are redacted from the rendered message,
exceptions report their type only (no prose, no traceback), and only a fixed set
of `extra` fields is copied. The existing `metis_diagnostic` logger keeps its own
handler and format.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from datetime import datetime, timezone

EXTRA_FIELDS = ('request_id', 'trace_id', 'event', 'attempt_id', 'snapshot_id', 'phase', 'reason_code')
_ASSIGNMENT_KEYS = (r'password|passwd|pwd|secret|client_secret|token|access_token|refresh_token|id_token|'
                    r'api[_-]?key|accountkey|sharedaccesskey|sharedaccesssignature|instrumentationkey|sig')
# Header-like keys: the whole value (to line end or closing quote) is secret, e.g. "Basic x", "a=b; c=d".
_HEADER_KEYS = (r'authorization|proxy-authorization|cookie|set-cookie|x-api-key|api-key|'
                r'ocp-apim-subscription-key|x-functions-key|x-ms-client-secret')
# Escaped delimiters (\" inside JSON strings) MOETEN NIET end the quoted value (Sherlock P1);
# an unterminated quoted value is redacted to line end (fail-closed).
# Line breaks inside a quoted value MOETEN NIET end it (multiline secrets, Sherlock P1);
# without a closing quote the rest of the text is redacted.
# A dangling escape at end of input MOET be consumed too (4293913967).
_QUOTED = r'"(?:\\[\s\S]?|[^"\\])*(?:"|\Z)|\'(?:\\[\s\S]?|[^\'\\])*(?:\'|\Z)'
# bytes / bytearray reprs (b'x', bytearray(b'x')) MOETEN be treated as quoted values (Sherlock P1 4293501888).
_VALUE_PREFIX = r'(?:bytearray\(\s*)?b?'
# Header keys in every form: hyphen or underscore, any prefix (HTTP_AUTHORIZATION, x-custom-api-key).
_HEADER_KEY_ANY = r'(?:[A-Za-z0-9]+[-_])*(?:' + _HEADER_KEYS.replace('-', '[-_]') + r')'
_SECRET_PATTERNS = (
    # header keys (optionally quoted, as in dict/JSON reprs): value to quote or line end
    re.compile(r'(?i)(?<![A-Za-z0-9_-])(["\']?' + _HEADER_KEY_ANY + r'["\']?)(\s*[=:]\s*)(?:' + _VALUE_PREFIX + r'(?:' + _QUOTED + r')|[^\r\n]+)'),
    # tuple-shaped header/credential pairs, (b'authorization', b'x') as in ASGI scopes and HTTP
    # clients: the comma separator and b-prefixes MOETEN be recognised (Sherlock P1 4291899701).
    re.compile(r'(?i)([\(\[]\s*b?["\'](?:' + _HEADER_KEY_ANY + r'|' + _ASSIGNMENT_KEYS + r')["\'])(\s*,\s*)'
               r'(?:' + _VALUE_PREFIX + r'(?:' + _QUOTED + r')|[^\s)\]]+)'),  # [ pairs too (4295084753)
    # credential assignments, quoted or unquoted values (password="x", {"password":"x"})
    re.compile(r'(?i)(["\']?\b(?:' + _ASSIGNMENT_KEYS + r')\b["\']?)(\s*[=:]\s*)(?:' + _VALUE_PREFIX + r'(?:' + _QUOTED + r')|[\{\[\(][^\r\n]*|[^\s;,&"\'}]+(?:[ \t]+(?![\w.-]+\s*[=:])[^\s;,&"\'}]+)*)'),  # spaces: to end of value, stop at the next key= (#661)  # container reprs: to line end (4294629122)
    # Standalone scheme credentials. Digest-style parameter lists (k="v", k=v) are consumed
    # completely (Sherlock P1). Any-case scheme + any token MOET be redacted; casing MAG NIET
    # decide (Metis 2026-10-16, fail-closed: 'basic flow' is redacted too).
    re.compile(r'(?i)\b(?:bearer|basic|digest|negotiate)\s+'
               r'[A-Za-z0-9_-]+\*?\s*=\s*(?:' + _QUOTED + r'|[^\s,]*)'
               r'(?:\s*,\s*[A-Za-z0-9_-]+\*?\s*=\s*(?:' + _QUOTED + r'|[^\s,]*))*'),  # k*= RFC 5987/7616, any spacing
    # any spacing, an '='/':' separator and quoted tokens (Metis 12:21 complete pass)
    re.compile(r'(?i)\b(?:bearer|basic|digest|negotiate)(?:\s+|\s*[=:]\s*)(?:' + _VALUE_PREFIX + r'(?:' + _QUOTED + r')|[A-Za-z0-9._~+/=-]+)'),
    re.compile(r'(?i)\b([a-z][a-z0-9+.-]*://)[^\s/:@]+:[^\s/@]+@'),
    re.compile(r'\bsk-[A-Za-z0-9_-]{8,}'),
    # Domain literals (user@[127.0.0.1], user@[IPv6:...]) MOETEN be redacted (Sherlock P2 4291899714).
    re.compile(r'(?:"(?:\\.|[^"\\\r\n])*"|(?<![\w.!#$%&\'*+/=?^`{|}~\u0080-\U0010ffff-])[\w.!#$%&\'*+/=?^`{|}~\u0080-\U0010ffff-]+)@\[[^\]\s]+\]'),
    # Quoted local parts ("john..doe"@example.org) MOETEN be redacted too (Sherlock P2).
    re.compile(r'"(?:\\.|[^"\\\r\n])*"@[\w-]+(?:\.[\w-]+)*\b'),  # zero-dot domains (localhost) too, 4293592622
    # Unicode-aware: SMTPUTF8 addresses (josé@example.com) MOETEN be redacted too (Sherlock P2).
    # Combining marks (jos\u0301e) MOETEN NIET split the local part (4294352280); any UTF-8
    # non-ASCII is atext under RFC 6531 (\U0001F600@example.com, 4296203827).
    re.compile(r'(?<![\w.!#$%&\'*+/=?^`{|}~\u0080-\U0010ffff-])[\w.!#$%&\'*+/=?^`{|}~\u0080-\U0010ffff-]+@[\w-]+(?:\.[\w-]+)*\b'),  # zero-dot domains (localhost) too, 4293592622
)
# Third-party loggers MOETEN stay at WARNING: their INFO/DEBUG output (HTTP headers,
# request bodies, connection strings) MAG NIET reach the root JSON handler.
LIBRARY_LOGGERS = ('azure', 'urllib3', 'httpx', 'httpcore', 'openai', 'msal', 'psycopg', 'asyncio')
# Known loggers with propagate=False and their own handlers (ASGI/WSGI servers). Their
# handlers MOETEN get the RedactingFilter explicitly. The server configures its loggers
# after build_app(), so install_startup_reinstall() MOET re-run the (idempotent) install at
# application startup (Metis 638-1). A handler added after startup is NOT covered.
NON_PROPAGATING_LOGGERS = ('uvicorn', 'uvicorn.error', 'uvicorn.access', 'gunicorn', 'gunicorn.error',
                           'gunicorn.access')
# Loggers whose formatter reads record.args positionally: args MOETEN stay per-arg redacted.
PER_ARG_LOGGERS = ('uvicorn.access',)
_SAFE = re.compile(r'[A-Za-z0-9_.:-]{1,128}')
_HANDLER_NAME = 'metis-structured-json'


def redact(text):
    text = str(text)
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(lambda m: m.group(1) + m.group(2) + '[REDACTED]', text)
        elif pattern.groups == 1:
            text = pattern.sub(lambda m: m.group(1) + '[REDACTED]@', text)
        else:
            text = pattern.sub('[REDACTED]', text)
    return text


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        from src.vorming.attempt_diagnostics_v1 import deployment_identity
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        row = {'timestamp': datetime.fromtimestamp(record.created, timezone.utc)
                   .isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
               'level': record.levelname, 'logger': redact(record.name), 'message': redact(message),  # #661
               'commit': deployment_identity()}
        try:
            # Correlation ids of the request in progress, for handlers added after install.
            from src.telemetry.hub import correlation
            context = correlation()
        except Exception:
            context = {}
        for name in EXTRA_FIELDS:
            value = getattr(record, name, None)
            if value is None and name in ('request_id', 'trace_id', 'attempt_id'):
                value = context.get(name)
            if isinstance(value, str) and _SAFE.fullmatch(value):
                row[name] = value if redact(value) == value else '[REDACTED]'  # whitelisted extras too (#661)
        if record.exc_info and record.exc_info[0] is not None:
            row['exc_type'] = record.exc_info[0].__name__
        return json.dumps(row, separators=(',', ':'), ensure_ascii=False)


# A sensitive key MAG a prefix (x_api_key, http_authorization).
_SENSITIVE_KEY = re.compile(r'(?i)(?:[a-z0-9]+[_-])*(?:' + _ASSIGNMENT_KEYS + r'|' + _HEADER_KEYS.replace('-', '[-_]') + r')')  # x_functions_key (4294629096)
_MAX_DEPTH = 32


def _is_sensitive_key(key):
    if isinstance(key, (bytes, bytearray)):
        key = bytes(key).decode('utf-8', 'replace')
    return isinstance(key, str) and bool(_SENSITIVE_KEY.fullmatch(key))


def _rebuild(value, items):
    # Rebuild a container from redacted items. Subclasses with a custom constructor MOETEN fall back
    # to the plain base type; redaction MAG NOOIT raise (4296870561).
    try:
        if hasattr(value, '_fields'):
            return type(value)(*items)
        return type(value)(items)
    except Exception:
        pass
    for base in (frozenset, set, tuple, list):
        if isinstance(value, base):
            break
    else:
        base = tuple
    try:
        return base(items)
    except Exception:
        # Unhashable redacted items in a set/frozenset become their redacted text (4297911915).
        return base(_hashable(item) for item in items)


def _hashable(item):
    try:
        hash(item)
        return item
    except Exception:
        try:
            return redact(str(item))
        except Exception:
            return '[REDACTED]'


def _redact_key(key, depth):
    # A redacted key MOET stay hashable; otherwise it becomes its redacted text (4297499491).
    if isinstance(key, (str, bytes, bytearray)):
        return redact(key)
    redacted = _deep_redact(key, depth)
    try:
        hash(redacted)
        return redacted
    except Exception:
        try:
            return redact(str(redacted))
        except Exception:
            return '[REDACTED]'


def _deep_redact(value, depth=0):
    """Redact str/bytes/bytearray at any depth of dict/list/tuple/set; sensitive keys are replaced."""
    if depth > _MAX_DEPTH:
        return '[REDACTED]'  # fail-closed beyond the depth bound
    if isinstance(value, (str, bytes, bytearray)):
        return redact(value)
    if isinstance(value, Mapping):  # UserDict too (4295084759)
        # Keys MOETEN be redacted too (PII keys, 4294629108).
        # Composite keys (tuples, frozensets) are redacted too (4296203813).
        return {_redact_key(key, depth + 1):
                '[REDACTED]' if _is_sensitive_key(key) else _deep_redact(item, depth + 1)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)) and len(value) == 2 and _is_sensitive_key(value[0]):
        return _rebuild(value, [value[0], '[REDACTED]'])  # header pair
    if isinstance(value, (list, tuple, set, frozenset)):
        return _rebuild(value, [_deep_redact(item, depth + 1) for item in value])
    if value is None or isinstance(value, (bool, int, float)):
        return value
    # Unknown printable leaves (exceptions, custom objects) are rendered and redacted (4295216361).
    try:
        return redact(str(value))
    except Exception:
        return '[REDACTED]'


def _redact_mapping_value(key, value):
    # A value selected by a sensitive mapping key MOET be replaced whatever its shape (Sherlock P1).
    if _is_sensitive_key(key):
        return '[REDACTED]'
    return _deep_redact(value)


def _redact_arg(value):
    return _deep_redact(value)  # containers too (4294629122)


_STANDARD_ATTRS = frozenset(logging.LogRecord('', 0, '', 0, '', (), None).__dict__) | {'message', 'asctime'}


class RedactingFilter(logging.Filter):
    """Redacts msg and every string arg in place, so handlers we do not own MAG NIET emit secrets.

    record.args stays a tuple (or mapping) of redacted values and is NOOIT None: formatters such
    as uvicorn's AccessFormatter read record.args positionally (Sherlock 02:10 #638 F1).
    """
    def filter(self, record):
        args = record.args
        if isinstance(args, Mapping):  # UserDict etc. too (4294352255)
            redacted_args = {(redact(key) if isinstance(key, (str, bytes, bytearray)) else key): _redact_mapping_value(key, value) for key, value in args.items()}
        else:
            redacted_args = tuple(_redact_arg(value) for value in (args or ()))
        msg = record.msg if isinstance(record.msg, str) else str(record.msg)
        try:
            candidate = msg % redacted_args if redacted_args else msg
        except Exception:
            candidate = None
        if record.name in PER_ARG_LOGGERS and not isinstance(args, Mapping):
            # uvicorn.access: AccessFormatter reads 5 positional args; each arg is redacted on its own.
            record.msg, record.args = redact(msg), redacted_args
        elif candidate is not None and redact(candidate) == candidate:
            record.msg, record.args = msg, redacted_args  # positional args kept for foreign formatters
        else:
            # Render from the redacted args only; on interpolation failure fall back to the
            # template, NOOIT to the original args (fail-closed, 4294352269).
            rendered = candidate if candidate is not None else msg
            # The secret spans template and args: render, redact, keep an empty tuple (NOOIT None).
            record.msg, record.args = redact(rendered), ()
        if record.exc_info and record.exc_info[0] is not None:
            # #638 F1: the traceback MAG NIET reach a handler we do not own; keep type + redacted message.
            exc_type, exc_value = record.exc_info[0], record.exc_info[1]
            suffix = redact(f' [{exc_type.__name__}: {exc_value}]')
            record.msg += suffix.replace('%', '%%') if record.args else suffix
        record.exc_info, record.exc_text, record.stack_info = None, None, None
        # Custom `extra` fields reach foreign formatters (%(authorization)s): sensitive keys MOETEN
        # be replaced, other string fields redacted (Sherlock P1 4289472643).
        for key, value in list(record.__dict__.items()):
            if key in ('msg', 'args'):
                continue  # handled above
            if key in _STANDARD_ATTRS:
                # String metadata (name, threadName, ...) MOET be redacted too (4294985557).
                if isinstance(value, str):
                    setattr(record, key, redact(value))
                continue
            if _is_sensitive_key(key):
                setattr(record, key, '[REDACTED]')  # any value type (4292037261)
            else:
                setattr(record, key, _deep_redact(value))  # any depth (4293501908)
        return True


_REDACTING_FILTER = RedactingFilter()


def _is_owned(handler):
    # The name alone MAG NIET be trusted: only our JsonLogFormatter handler counts (4294985552).
    return getattr(handler, 'name', None) == _HANDLER_NAME and type(handler.formatter) is JsonLogFormatter  # subclasses MAG NIET be trusted (4296203798)


def install_structured_logging(level=logging.INFO):
    """Install exactly one JSON handler on the root logger; repeated calls MOETEN be no-ops."""
    root = logging.getLogger()
    if not any(_is_owned(h) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.set_name(_HANDLER_NAME)
        handler.setFormatter(JsonLogFormatter())
        root.addHandler(handler)
    root.setLevel(level)
    # Pre-existing (host/embedding) root handlers MOETEN only see redacted records.
    for handler in root.handlers:
        if not _is_owned(handler) and _REDACTING_FILTER not in handler.filters:
            handler.addFilter(_REDACTING_FILTER)
    for name in NON_PROPAGATING_LOGGERS:
        for handler in logging.getLogger(name).handlers:
            if _REDACTING_FILTER not in handler.filters:
                handler.addFilter(_REDACTING_FILTER)
    # Explicitly configured descendants (azure.core...http_logging_policy at INFO) override the
    # parent level, so every existing descendant MOET be clamped too (Sherlock P1).
    existing = list(logging.root.manager.loggerDict)
    for name in LIBRARY_LOGGERS:
        for logger_name in [name] + [n for n in existing if n.startswith(name + '.')]:
            library = logging.getLogger(logger_name)
            if library.level != logging.NOTSET and library.level < logging.WARNING:
                library.setLevel(logging.WARNING)
        if logging.getLogger(name).level == logging.NOTSET:
            logging.getLogger(name).setLevel(logging.WARNING)


def install_startup_reinstall(app) -> None:
    """Re-run install_structured_logging() at startup, AFTER the server's own log setup (idempotent)."""
    app.add_event_handler('startup', install_structured_logging)
