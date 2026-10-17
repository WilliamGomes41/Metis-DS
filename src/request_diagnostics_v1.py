"""Bounded operational evidence for slow read pages; never domain state.

Only fixed route/phase names, bounded identities, times and counters leave this
module. The optional attempt token is strictly validated. No arbitrary headers,
query strings, user IDs, SQL, source content or exception text.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable, Any

_LOGGER = logging.getLogger('metis.console.diagnostics')
_CURRENT = ContextVar('metis_request_diagnostics', default=None)
ROUTES = frozenset({'/login', '/ingest', '/tree', '/source-selection', '/review', '/publish'})
COMMAND_ROUTES = frozenset({'/source-selection/start', '/publish'})
# Every other route is observed too (telemetry hub), except polling and static assets.
EXCLUDED_PREFIXES = ('/session/status', '/brand/', '/favicon', '/telemetry/api/', '/health')
PHASES = frozenset({'authorization', 'document_list', 'document_store_read', 'document_load',
    'selection_projection', 'processing_status', 'objects_read', 'source_read',
    'source_reconstruction', 'source_verify', 'review_bindings', 'review_render', 'review_index',
    'db_connect', 'db_execute', 'db_fetch', 'document_summary', 'review_work_items',
    'store_lock_wait', 'store_lock_hold', 'store_transaction', 'store_remirror'})
COUNTERS = frozenset({'source_reconstruction_built', 'source_reconstruction_reused',
    'source_reconstruction_unscoped', 'source_input_compared', 'source_input_hashed'})
HEARTBEAT_SECONDS = 15
MAX_PHASE_EVENTS = 40
MAX_TREE_NODES = 64
DEPLOYED_COMMIT_MARKER = Path(__file__).resolve().parents[1] / 'config' / 'deployed_commit.txt'
_COMMIT_RE = re.compile(r'[0-9a-f]{40}')
_TRACEPARENT_RE = re.compile(rb'00-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}')
_SNAPSHOT_RE = re.compile(r'snap-[0-9a-f]{8,32}-[0-9a-f]{4,32}')
_ID_SEGMENT_RE = re.compile(r'(?:snap-[0-9a-f-]+|pa_[0-9a-f]+|[0-9a-f]{12,}|[0-9a-f-]{32,36}|\d+)')


def deployed_commit():
    """Full lowercase commit written into the deployment package, else None."""
    try:
        value = DEPLOYED_COMMIT_MARKER.read_text(encoding='ascii').strip()
    except (OSError, UnicodeDecodeError):
        return None
    return value if _COMMIT_RE.fullmatch(value) else None


@dataclass
class RequestEvidence:
    request_id: str
    route: str
    emit: Callable[[dict[str, Any]], None]
    method: str = 'GET'
    attempt_id: str | None = None
    started: float = field(default_factory=time.perf_counter)
    stack: tuple = ()
    totals: dict = field(default_factory=dict)
    tree: dict = field(default_factory=dict)
    tree_truncated: bool = False
    counters: dict = field(default_factory=dict)
    phase_events: int = 0
    trace_id: str | None = None
    doc_ref: str | None = None
    error: dict | None = None
    db: dict | None = None

    def report(self, event, **fields):
        payload = {'event': event, 'request_id': self.request_id,
                   'route': self.route, 'method': self.method, 'attempt_id': self.attempt_id,
                   'timestamp': datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                   'elapsed_ms': round((time.perf_counter()-self.started)*1000, 3),
                   **fields}
        try:
            self.emit(payload)
        except Exception:
            # Logging/exporter failures may not change application behavior.
            pass


def current_request_id():
    evidence = _CURRENT.get()
    return evidence.request_id if evidence is not None else None


@contextlib.contextmanager
def detached_request_diagnostics():
    # asyncio tasks/to_thread copy ContextVars; background work is not HTTP latency.
    token = _CURRENT.set(None)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def diagnostic_count(name, amount=1):
    """Increment a fixed request-local counter; a no-op outside diagnosed requests."""
    evidence = _CURRENT.get()
    if evidence is None or name not in COUNTERS:
        return
    evidence.counters[name] = evidence.counters.get(name, 0) + amount


def note_handled_error(code):
    """Attach a handled ConsoleError code to the request in progress (no text)."""
    evidence = _CURRENT.get()
    if evidence is not None and isinstance(code, str) and re.fullmatch(r'[a-z][a-z0-9_]{1,80}', code):
        evidence.error = {'type': 'ConsoleError', 'code': code, 'handled': True}


def note_request_metrics(**values):
    """Attach bounded numeric request metrics (database counts and times)."""
    evidence = _CURRENT.get()
    if evidence is not None:
        evidence.db = {k: round(v, 3) if isinstance(v, float) else v for k, v in values.items()
                       if isinstance(v, (int, float))}


def diagnostic_record(name, elapsed_ms, *, overlapping=False):
    """Record a measured phase without a with-block.

    A leaf (a wait) counts as its parent's child time. An ``overlapping`` span
    (a lock hold that contains other phases) reports inclusive time only, so
    exclusive totals are not counted twice.
    """
    evidence = _CURRENT.get()
    if evidence is None or name not in PHASES:
        return
    previous = evidence.stack
    exclusive = 0.0 if overlapping else elapsed_ms
    _add_phase_time(evidence.totals, name, elapsed_ms, exclusive)
    path = '/'.join([entry[0] for entry in previous] + [name])
    if path in evidence.tree or len(evidence.tree) < MAX_TREE_NODES:
        _add_phase_time(evidence.tree, path, elapsed_ms, exclusive)
    else:
        evidence.tree_truncated = True
    if previous and not overlapping:
        previous[-1][2][0] += elapsed_ms


def diagnostic_clock():
    """Monotonic start mark for ``diagnostic_since`` (keeps callers free of timing code)."""
    return time.perf_counter()


def diagnostic_since(name, started, *, overlapping=False):
    """Record ``name`` as the time since ``started`` (perf_counter) and return now."""
    now = time.perf_counter()
    diagnostic_record(name, (now - started) * 1000, overlapping=overlapping)
    return now


def route_label(path):
    """Bounded route label: identifier-like path segments become {id}."""
    parts = [('{id}' if _ID_SEGMENT_RE.fullmatch(part) else part[:40]) for part in str(path).split('/')]
    return '/'.join(parts)[:120] or '/'


def _observed(scope):
    if scope['type'] != 'http':
        return False
    path = scope.get('path') or ''
    return not any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def doc_ref(snapshot_id):
    """Pseudonymous document reference: correlates requests without the document id."""
    from src.telemetry.hub import doc_ref as hub_doc_ref
    return hub_doc_ref(snapshot_id)


def _snapshot_from(scope):
    from urllib.parse import parse_qsl
    try:
        query = parse_qsl((scope.get('query_string') or b'').decode('latin-1'))
    except Exception:
        query = []
    candidates = [value for key, value in query if key in ('document', 'snapshot_id')]
    candidates += [part for part in (scope.get('path') or '').split('/') if part.startswith('snap-')]
    for value in candidates:
        if _SNAPSHOT_RE.fullmatch(value):
            return value
    return None


def _trace_from(scope):
    for key, value in scope.get('headers', []):
        if key.lower() == b'traceparent':
            match = _TRACEPARENT_RE.fullmatch(value.strip())
            if match and match.group(1) != b'0' * 32:
                return match.group(1).decode('ascii')
    return uuid.uuid4().hex


def _add_phase_time(table, key, inclusive, exclusive):
    total = table.setdefault(key, {'calls': 0, 'inclusive_ms': 0.0, 'exclusive_ms': 0.0})
    total['calls'] += 1
    total['inclusive_ms'] += inclusive
    total['exclusive_ms'] += exclusive


@contextlib.contextmanager
def diagnostic_phase(name):
    evidence = _CURRENT.get()
    if evidence is None or name not in PHASES:
        yield
        return
    started = time.perf_counter()
    previous = evidence.stack
    # Entry: (name, started, [child inclusive ms]); path is fixed phase names only.
    children = [0.0]
    evidence.stack = (*previous, (name, started, children))
    if evidence.phase_events < MAX_PHASE_EVENTS:
        evidence.phase_events += 1
        evidence.report('phase_started', phase=name, parent_phase=previous[-1][0] if previous else None)
    try:
        yield
    finally:
        elapsed = (time.perf_counter()-started)*1000
        exclusive = elapsed - children[0]
        _add_phase_time(evidence.totals, name, elapsed, exclusive)
        path = '/'.join([entry[0] for entry in previous] + [name])
        if path in evidence.tree or len(evidence.tree) < MAX_TREE_NODES:
            _add_phase_time(evidence.tree, path, elapsed, exclusive)
        else:
            evidence.tree_truncated = True
        if previous:
            previous[-1][2][0] += elapsed
        evidence.stack = previous


class AzureTelemetry:
    """Explicit SDK providers: no automatic collection of URLs/SQL/secrets."""
    def __init__(self, connection_string, identity):
        # Keep SDK self-monitoring outside this deliberately bounded rollout.
        os.environ.setdefault('APPLICATIONINSIGHTS_STATSBEAT_DISABLED_ALL', 'true')
        os.environ.setdefault('APPLICATIONINSIGHTS_OPENTELEMETRY_RESOURCE_METRIC_DISABLED', 'true')
        os.environ.setdefault('APPLICATIONINSIGHTS_CONTROLPLANE_DISABLED', 'true')
        os.environ.setdefault('APPLICATIONINSIGHTS_SDKSTATS_DISABLED', 'true')
        from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter, AzureMonitorTraceExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        resource = Resource(attributes={'service.name': 'metis-console',
            'service.version': identity['version'], 'service.instance.id': identity['instance']})
        options = dict(connection_string=connection_string, disable_offline_storage=True,
                       timeout=2, read_timeout=2, retry_total=0)
        self.traces = TracerProvider(resource=resource, sampler=ALWAYS_ON)
        self.traces.add_span_processor(BatchSpanProcessor(AzureMonitorTraceExporter(**options),
            max_queue_size=512, max_export_batch_size=64, schedule_delay_millis=1000))
        self.logs = LoggerProvider(resource=resource)
        self.logs.add_log_record_processor(BatchLogRecordProcessor(AzureMonitorLogExporter(**options),
            max_queue_size=512, max_export_batch_size=64, schedule_delay_millis=1000))
        self.handler = LoggingHandler(logger_provider=self.logs)
        self.tracer = self.traces.get_tracer('metis.read-diagnostics')

    def emit(self, payload):
        record = logging.LogRecord('metis.console.diagnostics', logging.INFO, '', 0,
                                   json.dumps(payload, separators=(',', ':')), (), None)
        # The same generated ID is queryable without parsing the message body.
        record.request_id = payload.get('request_id', '')
        record.event = payload['event']
        self.handler.handle(record)

    @contextlib.contextmanager
    def request(self, route, method='GET'):
        from opentelemetry.trace import SpanKind
        with self.tracer.start_as_current_span(method+' '+route, kind=SpanKind.SERVER,
                attributes={'http.request.method': method, 'http.route': route},
                record_exception=False, set_status_on_exception=False) as span:
            yield span

    def shutdown(self):
        self.logs.shutdown()
        self.traces.shutdown()


class RequestDiagnostics:
    def __init__(self, app, *, heartbeat_seconds=HEARTBEAT_SECONDS, telemetry=None, identity=None):
        self.app = app
        self.heartbeat_seconds = heartbeat_seconds
        self.telemetry = telemetry
        # METIS_BUILD_COMMIT stays authoritative; the packaged marker is the fallback.
        self.identity = identity or {'version': (os.getenv('METIS_BUILD_COMMIT')
                                                 or deployed_commit() or 'unknown')[:64],
            'instance': os.getenv('WEBSITE_INSTANCE_ID', 'local')[:128], 'pid': os.getpid()}
        if not any(isinstance(h, logging.StreamHandler) for h in _LOGGER.handlers):
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            _LOGGER.addHandler(handler)
        _LOGGER.setLevel(logging.INFO)
        _LOGGER.propagate = False
        connection = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING', '').strip()
        if self.telemetry is None and connection:
            try:
                self.telemetry = AzureTelemetry(connection, self.identity)
                self.emit({'event': 'telemetry_ready'})
            except Exception:
                # Do not log connection strings or SDK exception messages.
                self.emit({'event': 'telemetry_unavailable'})
        elif self.telemetry is None:
            self.emit({'event': 'telemetry_not_configured'})

    def emit(self, payload):
        payload = {**self.identity, **payload}
        try:
            _LOGGER.info('metis_diagnostic %s', json.dumps(payload, separators=(',', ':')))
        except Exception:
            pass
        if self.telemetry:
            try:
                self.telemetry.emit(payload)
            except Exception:
                pass

    @contextlib.contextmanager
    def request_span(self, route, method='GET'):
        context = None
        span = None
        if self.telemetry:
            try:
                context = (self.telemetry.request(route) if method == 'GET'
                           else self.telemetry.request(route, method=method))
                span = context.__enter__()
            except Exception:
                context = None
                self.emit({'event': 'telemetry_unavailable'})
        try:
            yield span
        finally:
            if context is not None:
                try:
                    context.__exit__(None, None, None)
                except Exception as exc:
                    self.emit({'event': 'telemetry_span_failed', 'error_type': type(exc).__name__})

    async def heartbeat(self, evidence):
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            stack = evidence.stack
            evidence.report('request_running', phase=stack[-1][0] if stack else 'request_dispatch',
                phase_elapsed_ms=round((time.perf_counter()-stack[-1][1])*1000, 3) if stack else 0)

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            try:
                await self.app(scope, receive, send)
            finally:
                if self.telemetry:
                    try:
                        await asyncio.to_thread(self.telemetry.shutdown)
                    except Exception:
                        pass
            return
        if not _observed(scope):
            await self.app(scope, receive, send)
            return
        # Caller-controlled correlation only; never an identity or access credential.
        candidates = [value for key, value in scope.get('headers', [])
                      if key.lower() == b'x-metis-attempt-id']
        attempt = (candidates[0].decode('ascii') if len(candidates) == 1
                   and re.fullmatch(rb'[0-9a-f]{32}', candidates[0]) else None)
        evidence = RequestEvidence(uuid.uuid4().hex, route_label(scope['path']), self.emit,
                                   method=scope['method'], attempt_id=attempt,
                                   trace_id=_trace_from(scope), doc_ref=doc_ref(_snapshot_from(scope)))
        token = _CURRENT.set(evidence)
        status = None
        completed = False
        outcome = 'exception'
        async def observed_send(message):
            nonlocal status, completed
            if message['type'] == 'http.response.start':
                status = message['status']
                message = {**message, 'headers': [*message.get('headers', []),
                    (b'x-metis-request-id', evidence.request_id.encode('ascii')),
                    (b'x-metis-trace-id', evidence.trace_id.encode('ascii'))]}
            await send(message)
            if message['type'] == 'http.response.start':
                evidence.report('response_started', status=status)
            if message['type'] == 'http.response.body' and not message.get('more_body', False):
                completed = True
                evidence.report('response_completed', status=status)
        # Export initialization is outside the request path. The SDK uses bounded
        # asynchronous queues; request processing never waits for network export.
        with self.request_span(evidence.route, scope['method']) as span:
            try:
                if span is not None and span.get_span_context().trace_id:
                    # One id from the browser to Azure Monitor: adopt the span's trace.
                    evidence.trace_id = format(span.get_span_context().trace_id, '032x')
            except Exception:
                pass
            evidence.report('request_started', trace_id=evidence.trace_id, doc_ref=evidence.doc_ref)
            task = asyncio.create_task(self.heartbeat(evidence))
            try:
                await self.app(scope, receive, observed_send)
                outcome = 'completed' if completed else 'incomplete'
            except asyncio.CancelledError:
                outcome = 'cancelled'
                raise
            except Exception as exc:
                try:
                    from src.telemetry.errors import exception_evidence
                    evidence.error = exception_evidence(exc)
                except Exception:
                    pass
                raise
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                def rounded(table):
                    return {k: {'calls': v['calls'], 'inclusive_ms': round(v['inclusive_ms'], 3),
                                'exclusive_ms': round(v['exclusive_ms'], 3)} for k, v in table.items()}
                extra = {'phase_tree_truncated': True} if evidence.tree_truncated else {}
                template = getattr(scope.get('route'), 'path', None)
                if isinstance(template, str) and template.startswith('/'):
                    evidence.route = template[:120]
                for key in ('error', 'db'):
                    if getattr(evidence, key):
                        extra[key] = getattr(evidence, key)
                extra.update(trace_id=evidence.trace_id, doc_ref=evidence.doc_ref)
                evidence.report('request_finished', status=status, outcome=outcome,
                    phases=rounded(evidence.totals), phase_tree=rounded(evidence.tree),
                    counters=dict(evidence.counters), **extra)
                try:
                    if span:
                        from opentelemetry.trace import Status, StatusCode
                        span.set_attribute('metis.request_id', evidence.request_id)
                        span.set_attribute('metis.outcome', outcome)
                        if status is not None:
                            span.set_attribute('http.response.status_code', status)
                        if outcome != 'completed' or (status or 0) >= 500:
                            span.set_status(Status(StatusCode.ERROR))
                except Exception:
                    pass
                _CURRENT.reset(token)
