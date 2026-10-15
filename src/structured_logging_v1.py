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
from datetime import datetime, timezone

EXTRA_FIELDS = ('request_id', 'event', 'attempt_id', 'snapshot_id', 'phase', 'reason_code')
_ASSIGNMENT_KEYS = (r'password|passwd|pwd|secret|client_secret|token|access_token|refresh_token|id_token|'
                    r'api[_-]?key|accountkey|sharedaccesskey|sharedaccesssignature|instrumentationkey|sig')
# Header-like keys: the whole value (to line end or closing quote) is secret, e.g. "Basic x", "a=b; c=d".
_HEADER_KEYS = (r'authorization|proxy-authorization|cookie|set-cookie|x-api-key|api-key|'
                r'ocp-apim-subscription-key|x-functions-key|x-ms-client-secret')
_QUOTED = r'"[^"\r\n]*"|\'[^\'\r\n]*\''
_SECRET_PATTERNS = (
    # header keys (optionally quoted, as in dict/JSON reprs): value to quote or line end
    re.compile(r'(?i)(?<![A-Za-z0-9_-])(["\']?(?:' + _HEADER_KEYS + r')["\']?)(\s*[=:]\s*)(?:' + _QUOTED + r'|[^\r\n]+)'),
    # credential assignments, quoted or unquoted values (password="x", {"password":"x"})
    re.compile(r'(?i)(["\']?\b(?:' + _ASSIGNMENT_KEYS + r')\b["\']?)(\s*[=:]\s*)(?:' + _QUOTED + r'|[^\s;,&"\'}]+)'),
    re.compile(r'(?i)\b(?:bearer|basic|digest|negotiate)\s+[A-Za-z0-9._~+/=-]{6,}'),
    re.compile(r'(?i)\b([a-z][a-z0-9+.-]*://)[^\s/:@]+:[^\s/@]+@'),
    re.compile(r'\bsk-[A-Za-z0-9_-]{8,}'),
    re.compile(r'(?i)(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
)
# Third-party loggers MOETEN stay at WARNING: their INFO/DEBUG output (HTTP headers,
# request bodies, connection strings) MAG NIET reach the root JSON handler.
LIBRARY_LOGGERS = ('azure', 'urllib3', 'httpx', 'httpcore', 'openai', 'msal', 'psycopg', 'asyncio')
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
        from src.attempt_diagnostics_v1 import deployment_identity
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        row = {'timestamp': datetime.fromtimestamp(record.created, timezone.utc)
                   .isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
               'level': record.levelname, 'logger': record.name, 'message': redact(message),
               'commit': deployment_identity()}
        for name in EXTRA_FIELDS:
            value = getattr(record, name, None)
            if isinstance(value, str) and _SAFE.fullmatch(value):
                row[name] = value
        if record.exc_info and record.exc_info[0] is not None:
            row['exc_type'] = record.exc_info[0].__name__
        return json.dumps(row, separators=(',', ':'), ensure_ascii=False)


def install_structured_logging(level=logging.INFO):
    """Install exactly one JSON handler on the root logger; repeated calls MOETEN be no-ops."""
    root = logging.getLogger()
    if not any(getattr(h, 'name', None) == _HANDLER_NAME for h in root.handlers):
        handler = logging.StreamHandler()
        handler.set_name(_HANDLER_NAME)
        handler.setFormatter(JsonLogFormatter())
        root.addHandler(handler)
    root.setLevel(level)
    for name in LIBRARY_LOGGERS:
        library = logging.getLogger(name)
        if library.level == logging.NOTSET or library.level < logging.WARNING:
            library.setLevel(logging.WARNING)
