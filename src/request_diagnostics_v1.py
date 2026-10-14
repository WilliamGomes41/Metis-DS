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
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable, Any

_LOGGER = logging.getLogger('metis.console.diagnostics')
_CURRENT = ContextVar('metis_request_diagnostics', default=None)
ROUTES = frozenset({'/login', '/ingest', '/tree', '/source-selection', '/review', '/publish'})
COMMAND_ROUTES = frozenset({'/source-selection/start', '/publish'})
PHASES = frozenset({'authorization', 'document_list', 'document_store_read', 'document_load',
    'selection_projection', 'processing_status', 'objects_read', 'source_read',
    'source_reconstruction', 'source_verify', 'review_bindings', 'review_render', 'review_index',
    'db_connect', 'db_execute', 'db_fetch', 'document_summary', 'review_work_items'})
HEARTBEAT_SECONDS = 15
MAX_PHASE_EVENTS = 40


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
    phase_events: int = 0

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


@contextlib.contextmanager
def diagnostic_phase(name):
    evidence = _CURRENT.get()
    if evidence is None or name not in PHASES:
        yield
        return
    started = time.perf_counter()
    previous = evidence.stack
    evidence.stack = (*previous, (name, started))
    if evidence.phase_events < MAX_PHASE_EVENTS:
        evidence.phase_events += 1
        evidence.report('phase_started', phase=name)
    try:
        yield
    finally:
        elapsed = (time.perf_counter()-started)*1000
        total = evidence.totals.setdefault(name, {'calls': 0, 'inclusive_ms': 0.0})
        total['calls'] += 1
        total['inclusive_ms'] += elapsed
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
        self.identity = identity or {'version': os.getenv('METIS_BUILD_COMMIT', 'unknown')[:64],
            'instance': os.getenv('WEBSITE_INSTANCE_ID', 'local')[:128], 'pid': os.getpid()}
        if not _LOGGER.handlers:
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
        if scope['type'] != 'http' or not (
                (scope.get('method') == 'GET' and scope.get('path') in ROUTES) or
                (scope.get('method') == 'POST' and scope.get('path') in COMMAND_ROUTES)):
            await self.app(scope, receive, send)
            return
        # Caller-controlled correlation only; never an identity or access credential.
        candidates = [value for key, value in scope.get('headers', [])
                      if key.lower() == b'x-metis-attempt-id']
        attempt = (candidates[0].decode('ascii') if len(candidates) == 1
                   and re.fullmatch(rb'[0-9a-f]{32}', candidates[0]) else None)
        evidence = RequestEvidence(uuid.uuid4().hex, scope['path'], self.emit, method=scope['method'], attempt_id=attempt)
        token = _CURRENT.set(evidence)
        status = None
        completed = False
        outcome = 'exception'
        async def observed_send(message):
            nonlocal status, completed
            if message['type'] == 'http.response.start':
                status = message['status']
                message = {**message, 'headers': [*message.get('headers', []),
                    (b'x-metis-request-id', evidence.request_id.encode('ascii'))]}
            await send(message)
            if message['type'] == 'http.response.start':
                evidence.report('response_started', status=status)
            if message['type'] == 'http.response.body' and not message.get('more_body', False):
                completed = True
                evidence.report('response_completed', status=status)
        # Export initialization is outside the request path. The SDK uses bounded
        # asynchronous queues; request processing never waits for network export.
        with self.request_span(scope['path'], scope['method']) as span:
            evidence.report('request_started')
            task = asyncio.create_task(self.heartbeat(evidence))
            try:
                await self.app(scope, receive, observed_send)
                outcome = 'completed' if completed else 'incomplete'
            except asyncio.CancelledError:
                outcome = 'cancelled'
                raise
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                evidence.report('request_finished', status=status, outcome=outcome,
                    phases={k: {'calls': v['calls'], 'inclusive_ms': round(v['inclusive_ms'], 3)}
                            for k, v in evidence.totals.items()})
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
