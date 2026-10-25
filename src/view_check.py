"""Document-scoped, read-only browser investigation over the installed app.

No human cookie is copied. The worker receives one fenced capability, accepted
only on the three inspected GET routes and private brand assets.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import re
import subprocess
from time import monotonic
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from src.integrity_kernel import stable_hash
from src.operations_console_v1 import ConsoleError
from src.view_check_store import ViewCheckConflict, ViewCheckStore

COOKIE = 'metis_view_check'
SCENARIO = 'selection-review-inventory-v2'
HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
ROOT = Path(__file__).resolve().parents[1]


class ViewCheckAccessDenied(ConsoleError):
    """Authorization refusal, distinct from an unavailable scenario/context."""


@dataclass(frozen=True)
class ViewCheckConfig:
    origin: str
    module: str
    browser: str

    def __post_init__(self):
        parsed = urlsplit(self.origin)
        loopback = parsed.hostname in {'localhost', '127.0.0.1', '::1'}
        if (parsed.scheme not in ({'http', 'https'} if loopback else {'https'})
                or not parsed.netloc or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment):
            raise ValueError('view_check_origin_invalid')
        if not Path(self.module).is_absolute() or not Path(self.browser).is_file():
            raise ValueError('view_check_browser_unavailable')


class EvidenceStore:
    """A separate private Azure container; never the immutable source namespace."""
    def __init__(self, service, container, source_container):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', container) or container == source_container:
            raise ValueError('view_check_evidence_container_invalid')
        self.service, self.container = service, container

    def _blob(self, key):
        if not re.fullmatch(r'[0-9a-f]{32}/[12]/[0-9a-f]{64}\.png', key):
            raise ValueError('invalid_evidence_key')
        props = self.service.get_container_client(self.container).get_container_properties()
        if props.get('public_access'):
            raise ValueError('view_check_evidence_not_private')
        return self.service.get_blob_client(self.container, key)

    def put(self, key, data):
        if len(data) > 4 * 1024 * 1024 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('invalid_evidence')
        blob = self._blob(key)
        blob.upload_blob(data, overwrite=True)
        if sha256(bytes(blob.download_blob().readall())).hexdigest() != sha256(data).hexdigest():
            raise ValueError('evidence_readback_failed')

    def get(self, key):
        blob = self._blob(key)
        if blob.get_blob_properties().size > 4 * 1024 * 1024:
            raise ValueError('invalid_evidence')
        return bytes(blob.download_blob().readall())


def authorize(state, actor, document):
    account = state._account(actor, current=True)
    envelope = state._envelope(document)
    if (account.get('retirement') or 'reviewer' not in account.get('roles', [])
            or actor not in envelope.get('named_reviewers', [])):
        raise ViewCheckAccessDenied('reviewer_not_named_on_snapshot')
    return account, envelope


def context(state, actor, document, attempt=''):
    account, envelope = authorize(state, actor, document)
    attempts = envelope.get('processing_attempts') or []
    if attempt and not any(row['attempt_id'] == attempt for row in attempts):
        raise ValueError('unknown_attempt')
    if 'decision_graph' in envelope:
        raise ValueError('scenario_not_supported')
    objects, revision = state.snapshot_objects_and_revision(document, include_blocked=True)
    if len(objects) > 1000:
        raise ValueError('scenario_limit_exceeded')
    from src.processing_trace_v1 import runtime_identity
    return {'scenario': SCENARIO, 'snapshot_id': document, 'attempt_id': attempt,
            'source_hash': envelope['sha256'], 'source_version': envelope['version'],
            'revision': revision, 'envelope_hash': stable_hash(envelope),
            'bindings_hash': stable_hash(state.object_review_bindings(document, objects=objects)),
            'deployment': runtime_identity()['version']}


def allowed_request(method, path, params, document):
    if method != 'GET':
        return False
    if path.startswith('/brand/'):
        return '..' not in path and len(path) < 200
    permitted = {'/source-selection': {'document'}, '/review': {'document', 'task'},
                 '/inzicht/document/passages': {'document', 'format'}}
    if path not in permitted or set(params) - permitted[path]:
        return False
    # Reject duplicate query keys too; never let parser disagreement widen scope.
    if hasattr(params, 'multi_items') and len(list(params.multi_items())) != len(params):
        return False
    return (params.get('document') == document
            and (path != '/review' or params.get('task') == 'inventory')
            and (path != '/inzicht/document/passages' or params.get('format', 'json') == 'json'))


class ViewChecks:
    def __init__(self, state, store, config, evidence):
        self.state, self.store, self.config, self.evidence = state, store, config, evidence
        self.poller = None

    def browser_account(self, request):
        job = self.store.capability(request.cookies.get(COOKIE))
        if not job or not allowed_request(request.method, request.url.path, request.query_params, job['snapshot_id']):
            raise ValueError('view_check_scope_denied')
        current = context(self.state, job['owner_account_id'], job['snapshot_id'], job['context']['attempt_id'])
        if current != {k: v for k, v in job['context'].items() if k != 'origin'}:
            raise ValueError('view_check_context_changed')
        account, _ = authorize(self.state, job['owner_account_id'], job['snapshot_id'])
        return {**account, '_view_document': job['snapshot_id']}

    def execute_one(self):
        claimed = self.store.claim()
        if not claimed:
            return
        job, token = claimed
        started = monotonic()
        result = {'scenario': SCENARIO, 'reason': 'not_established', 'checks': [], 'evidence': []}
        try:
            pinned = {k: v for k, v in job['context'].items() if k != 'origin'}
            if job['context']['origin'] != self.config.origin or context(
                    self.state, job['owner_account_id'], job['snapshot_id'], pinned['attempt_id']) != pinned:
                raise ValueError('context_changed')
            payload = {'origin': self.config.origin, 'token': token, 'document': job['snapshot_id'],
                       'revision': pinned['revision']}
            from src.source_accountability_v1 import is_source_record
            payload['source_ids'] = [obj['object_id'] for obj in
                self.state.snapshot_objects(job['snapshot_id']) if is_source_record(obj)]
            env = {key: value for key, value in os.environ.items() if key in {'PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT'}}
            env.update(METIS_PLAYWRIGHT_MODULE=self.config.module, METIS_BROWSER_EXECUTABLE=self.config.browser)
            # Node subprocess has no DB/Azure credentials or user's login session.
            run = subprocess.run(['node', str(ROOT / 'scripts/view_check.cjs')], input=json.dumps(payload),
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 timeout=45, env=env, cwd=ROOT)
            if run.returncode or len(run.stdout) > 6 * 1024 * 1024:
                raise ValueError('browser_failed')
            raw = json.loads(run.stdout)
            result['checks'] = validate_checks(raw.get('checks'))
            result['browser_version'] = str(raw.get('browser_version', ''))[:80]
            result['scenario_sha256'] = sha256((ROOT / 'scripts/view_check.cjs').read_bytes()).hexdigest()
            result['diagnosis'] = validate_diagnosis(raw.get('diagnosis'))
            result['coverage'] = {
                'inventory': 'all_rows' if not raw.get('incomplete') else 'not_established',
                'normalization': 'HTML_ASCII_whitespace', 'fields': ['content.clean_text', 'source_label_hint.label'],
                'unchecked_fields': ['structured_conditions', 'structured_exceptions', 'source_locators', 'source_context'],
                'object_order': 'knowledge_rows_only_source_groups_not_checked',
                'objects_checked': [str(oid)[:200] for oid in raw.get('coverage', {}).get('objects_checked', [])[:1000]],
                'objects_unchecked': [str(oid)[:200] for oid in raw.get('coverage', {}).get('objects_unchecked', [])[:1000]],
                'clinical': 'not_established', 'source_extraction': 'not_established'}
            if raw.get('incomplete'):
                raise ValueError('browser_failed')
            if context(self.state, job['owner_account_id'], job['snapshot_id'], pinned['attempt_id']) != pinned:
                raise ValueError('context_changed')
            # Recheck fence/cancellation before uploading source-bearing evidence.
            if not self.store.capability(token):
                return
            image = base64.b64decode(raw['screenshot'], validate=True)
            checksum = sha256(image).hexdigest()
            key = f"{job['id']}/{job['attempt']}/{checksum}.png"
            self.evidence.put(key, image)
            result.update(reason='completed', evidence=[{'key': key, 'sha256': checksum,
                'expires_at': (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()}])
            # Revocation and context are validated again at activation.
            if context(self.state, job['owner_account_id'], job['snapshot_id'], pinned['attempt_id']) != pinned:
                raise ValueError('context_changed')
            self.store.finish(job['id'], job['attempt'], token, result)
        except Exception as error:
            reason = ('browser_timeout' if isinstance(error, subprocess.TimeoutExpired)
                      else str(error) if isinstance(error, ValueError) and str(error) in
                      {'context_changed', 'browser_failed', 'invalid_checks'} else 'investigation_unavailable')
            # Observed differences remain visible, but none of the passes certifies
            # a stable context when preparation/activation did not complete.
            result.update(reason=reason, evidence=[])
            result.setdefault('diagnosis', {'step': 'worker_execution', 'expected': 'stable_authorized_context_and_browser_result',
                                         'observed': reason, 'elapsed_ms': round((monotonic()-started)*1000), 'requests': []})
            if reason == 'context_changed':
                result['diagnosis']['observed'] = 'context_changed'
            for check in result['checks']:
                if check['verdict'] == 'pass':
                    check['verdict'] = 'not_established'
            self.store.finish(job['id'], job['attempt'], token, result, failed=True)

    async def start(self):
        async def poll():
            while True:
                try:
                    await asyncio.to_thread(self.execute_one)
                except Exception:
                    pass  # Durable lease is the recovery authority; no private error prose.
                await asyncio.sleep(2)
        self.poller = asyncio.create_task(poll())

    async def stop(self):
        if self.poller:
            self.poller.cancel()
            await asyncio.gather(self.poller, return_exceptions=True)


CHECK_IDS = {'inventory_identity', 'source_partition', 'review_links', 'source_selection', 'browser_errors', 'rendered_text', 'rendered_order', 'rendered_context'}


def validate_checks(raw):
    if not isinstance(raw, list) or len(raw) != len(CHECK_IDS):
        raise ValueError('invalid_checks')
    result = []
    for row in raw:
        if not isinstance(row, dict) or row.get('id') not in CHECK_IDS or row.get('verdict') not in {'pass', 'fail', 'not_established'}:
            raise ValueError('invalid_checks')
        # Bounded counts only: no page text, exception messages or copied source.
        item = {'id': row['id'], 'verdict': row['verdict']}
        for key in ('expected', 'observed'):
            if type(row.get(key)) is not int or not 0 <= row[key] <= 10000:
                raise ValueError('invalid_checks')
            item[key] = row[key]
        result.append(item)
    if {row['id'] for row in result} != CHECK_IDS:
        raise ValueError('invalid_checks')
    return result


def validate_diagnosis(raw):
    if not isinstance(raw, dict):
        return {'observed': 'not_recorded'}
    choices = {
        'step': {'browser_setup', 'source_selection', 'stored_inventory', 'review_inventory', 'rendered_content', 'screen_evidence'},
        'expected': {'restricted_context', 'selected_document_and_controls', 'same_document_revision_and_bounded_export', 'visible_inventory_with_stored_text', 'visible_stored_fields', 'bounded_screenshot'},
        'observed': {'matched', 'difference', 'not_established', 'timeout'},
    }
    result = {key: raw.get(key) if raw.get(key) in allowed else 'unknown' for key, allowed in choices.items()}
    elapsed = raw.get('elapsed_ms')
    result['elapsed_ms'] = elapsed if type(elapsed) is int and 0 <= elapsed <= 60000 else None
    result['requests'] = []
    for row in raw.get('requests', [])[:12]:
        if not isinstance(row, dict) or row.get('route') not in {'/source-selection', '/review', '/inzicht/document/passages'}:
            continue
        reference = row.get('reference')
        result['requests'].append({'route': row['route'],
            'state': row.get('state') if row.get('state') in {'pending', 'response_started', 'completed', 'failed'} else 'unknown',
            'status': row.get('status') if type(row.get('status')) is int and 100 <= row['status'] <= 599 else None,
            'reference': reference if isinstance(reference, str) and re.fullmatch('[0-9a-f]{32}', reference) else None})
    return result


def install(app, state, require, render_page, nav):
    app.state.view_checks = None

    @app.exception_handler(ViewCheckAccessDenied)
    async def access_denied(request, error):
        return JSONResponse({'error': 'view_check_access_denied'}, status_code=403, headers=HEADERS)

    origin = os.environ.get('METIS_VIEW_CHECK_ORIGIN', '').rstrip('/')
    if origin:
        owner = getattr(state, 'workflow_document_store', None)
        source = getattr(state, 'immutable_source_store', None)
        if owner is None or source is None or not hasattr(source, '_service'):
            raise ValueError('view_check_postgres_and_private_evidence_required')
        config = ViewCheckConfig(origin, os.environ.get('METIS_PLAYWRIGHT_MODULE', ''),
                                 os.environ.get('METIS_BROWSER_EXECUTABLE', ''))
        store = ViewCheckStore(getattr(owner, '_metis_workflow_original_connect', owner._connect))
        store.verify()
        evidence = EvidenceStore(source._service, os.environ.get('METIS_VIEW_CHECK_EVIDENCE_CONTAINER', ''), source.container)
        app.state.view_checks = ViewChecks(state, store, config, evidence)

    @app.middleware("http")
    async def restricted_browser(request, call_next):
        if COOKIE in request.cookies:
            service = app.state.view_checks
            try:
                if service is None:
                    raise ValueError('unavailable')
                request.state.view_check_account = await asyncio.to_thread(service.browser_account, request)
            except Exception:
                return JSONResponse({'error': 'view_check_denied'}, status_code=403, headers=HEADERS)
            # Nested read scopes must retain this prohibition on native extraction.
            with state.document_read_operation(retained_only=True):
                return await call_next(request)
        return await call_next(request)

    async def start_worker():
        if app.state.view_checks:
            await app.state.view_checks.start()

    async def stop_worker():
        if app.state.view_checks:
            await app.state.view_checks.stop()
    app.add_event_handler('startup', start_worker)
    app.add_event_handler('shutdown', stop_worker)

    def service():
        if app.state.view_checks is None:
            from fastapi import HTTPException
            raise HTTPException(503, 'view_check_not_configured')
        return app.state.view_checks

    def record(request, identifier):
        account = require(request)
        row = service().store.get(identifier)
        if row is None:
            raise ConsoleError('unknown_document')
        authorize(state, account['account_id'], row['snapshot_id'])
        return row, account

    @app.post('/inzicht/document/weergavecontrole')
    async def request_check(request: Request):
        account = require(request)
        form = await request.form()
        # These commands require the same origin even in a local console.
        origin_header = request.headers.get('origin', '')
        expected = service().config.origin
        if origin_header != expected:
            return JSONResponse({'error': 'origin_denied'}, status_code=403, headers=HEADERS)
        document, attempt, key = str(form.get('document', '')), str(form.get('attempt', '')), str(form.get('request_key', ''))
        if not re.fullmatch(r'[0-9a-f]{32}', key):
            return JSONResponse({'error': 'invalid_request_key'}, status_code=400, headers=HEADERS)
        try:
            pinned = await asyncio.to_thread(context, state, account['account_id'], document, attempt)
            if pinned['revision'] != str(form.get('expected_revision', '')):
                raise ValueError('context_changed')
            pinned['origin'] = expected
            row = await asyncio.to_thread(service().store.register, account['account_id'], document, key, pinned)
        except ViewCheckAccessDenied:
            raise
        except (ValueError, ViewCheckConflict):
            return JSONResponse({'error': 'view_check_context_unavailable'}, status_code=409, headers=HEADERS)
        return RedirectResponse('/inzicht/document?' + urlencode({'document': document, 'attempt': attempt,
                                'view_check': row['id']}) + '#weergavecontrole', status_code=303, headers=HEADERS)

    @app.get('/inzicht/weergavecontrole/{identifier}')
    def get_check(request: Request, identifier: str):
        row, _ = record(request, identifier)
        return JSONResponse(jsonable_encoder(row), headers=HEADERS)

    @app.post('/inzicht/weergavecontrole/{identifier}/annuleren')
    def cancel_check(request: Request, identifier: str):
        row, account = record(request, identifier)
        if request.headers.get('origin') != service().config.origin:
            return JSONResponse({'error': 'origin_denied'}, status_code=403, headers=HEADERS)
        service().store.cancel(identifier, account['account_id'])
        return RedirectResponse('/inzicht/document?' + urlencode({'document': row['snapshot_id'],
                                'attempt': row['context']['attempt_id']}) + '#weergavecontrole', status_code=303, headers=HEADERS)

    @app.get('/inzicht/weergavecontrole/{identifier}/bewijs')
    def get_evidence(request: Request, identifier: str):
        row, _ = record(request, identifier)
        evidence = (row.get('result') or {}).get('evidence') or []
        if not evidence:
            return JSONResponse({'error': 'evidence_missing'}, status_code=404, headers=HEADERS)
        item = evidence[0]
        if datetime.fromisoformat(item['expires_at']) <= datetime.now(timezone.utc):
            return JSONResponse({'error': 'evidence_expired'}, status_code=410, headers=HEADERS)
        try:
            data = service().evidence.get(item['key'])
            if sha256(data).hexdigest() != item['sha256']:
                raise ValueError('evidence_changed')
        except Exception:
            return JSONResponse({'error': 'evidence_unavailable'}, status_code=503, headers=HEADERS)
        # Recheck permissions after storage I/O too.
        authorize(state, require(request)['account_id'], row['snapshot_id'])
        return Response(data, media_type='image/png', headers={**HEADERS, 'Content-Disposition': 'inline; filename="weergavecontrole.png"'})


def panel(app, state, account, document, attempt=''):
    title = '<section id="weergavecontrole"><h2>Weergavecontrole</h2>'
    try:
        authorize(state, account['account_id'], document)
    except ConsoleError:
        return title + '<p>Deze controle vereist toegang als toegewezen reviewer.</p></section>'
    service = getattr(app.state, 'view_checks', None)
    if service is None:
        return title + '<p>De weergavecontrole is nog niet ingericht voor deze omgeving.</p></section>'
    body = title + '<p>Vergelijkt de schermweergave met vastgelegde gegevens. Dit is geen inhoudelijke documentbeoordeling.</p>'
    body += '<p>De controle van weergavetrouwheid vergelijkt passage-identiteit, opgeslagen tekst en kennisregelvolgorde, bronregels en reviewlinks. Alleen HTML-witruimte wordt genormaliseerd. Los opgeslagen voorwaarden, uitzonderingen, bronlocators en contextvelden worden nog niet gecontroleerd; voorwaarden in de passage-tekst wel. Dit bewijst geen klinische juistheid of volledige bronextractie.</p>'
    try:
        pinned = context(state, account['account_id'], document, attempt)
    except ValueError:
        body += '<p>Deze controle is niet beschikbaar voor dit document of deze verwerkingspoging.</p>'
    else:
        body += ('<form method="post" action="/inzicht/document/weergavecontrole">'
             f'<input type="hidden" name="document" value="{escape(document, quote=True)}">'
             f'<input type="hidden" name="attempt" value="{escape(attempt, quote=True)}">'
             f'<input type="hidden" name="expected_revision" value="{escape(pinned["revision"], quote=True)}">'
             f'<input type="hidden" name="request_key" value="{uuid4().hex}">'
             '<button type="submit">Controleer weergave</button></form>')
    states = {'queued': 'In wachtrij', 'running': 'Weergave wordt gecontroleerd',
              'completed': 'Uitkomst weergavecontrole', 'failed': 'Niet vastgesteld', 'cancelled': 'Geannuleerd'}
    body += '<p>De laatste twintig onderzoeken staan hieronder. Eerdere onderzoeken blijven via hun onderzoeks-ID opvraagbaar.</p>'
    for row in service.store.history(document):
        body += f'<article><h3>{states[row["state"]]}</h3><p>{escape(str(row["created_at"]))}</p>'
        body += '<p>Scenario: ' + escape(row['context']['scenario']) + ' · Poging: ' + escape(row['context']['attempt_id'] or 'niet gekozen') + '</p>'
        for check in (row.get('result') or {}).get('checks', []):
            label = {'pass': 'Geslaagd', 'fail': 'Afwijking', 'not_established': 'Niet vastgesteld'}[check['verdict']]
            body += f'<p>{escape(check["id"])}: {label} · verwacht {check["expected"]}, waargenomen {check["observed"]}</p>'
        result = row.get('result') or {}
        if result.get('reason'):
            body += '<p>Uitvoeringscode: ' + escape(result['reason']) + '</p>'
        body += f'<p><a href="/inzicht/weergavecontrole/{row["id"]}">Onderzoeksgegevens</a></p>'
        if result.get('evidence'):
            expired = datetime.fromisoformat(result['evidence'][0]['expires_at']) <= datetime.now(timezone.utc)
            body += ('<p>Bewijs verlopen.</p>' if expired else f'<a href="/inzicht/weergavecontrole/{row["id"]}/bewijs">Bekijk schermbewijs</a>')
        if row['state'] in {'queued', 'running'} and row['owner_account_id'] == account['account_id']:
            body += '<p><a href="/inzicht/document?' + escape(urlencode({'document': document, 'attempt': attempt}), quote=True) + '#weergavecontrole">Vernieuw resultaat</a></p>'
            body += f'<form method="post" action="/inzicht/weergavecontrole/{row["id"]}/annuleren"><button>Annuleren</button></form>'
        body += '</article>'
    return body + '</section>'
