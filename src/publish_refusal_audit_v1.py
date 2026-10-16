"""Publish-gate refusal audit event; observation only, never a gate authority.

The gate's existing verdict is passed in after it is final. This module MOET only
read it: the verdict, its reason codes, the document, the revision and a digest
of the actor. It MAG NIET change, re-evaluate or delay the verdict, and a logging or
audit-store failure MAG NOOIT reach the caller. Every such failure MOET emit one
bounded `publication_refusal_audit_failed` diagnostic (#629 F2); it MAG NIET be
silently swallowed. The diagnostic carries no exception text, actor or key. Allowed verdicts produce no event.

Logs carry the actor only as a keyed HMAC (key from app setting
METIS_AUDIT_HMAC_KEY; the key MAG NOOIT be logged; without a key the field is None).
The durable audit store is the separate append-only refusal store
(src/publication_refusal_store_v1.py), outside the review ledger hash chain; it
records the actor in clear, as review and publish events do.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
from datetime import datetime, timezone

MAX_REASON_CODES = 128
_CODE = re.compile(r'[a-z][a-z0-9_]{0,95}')
_SNAPSHOT = re.compile(r'[A-Za-z0-9_.:-]{1,128}')
HMAC_KEY_SETTING = 'METIS_AUDIT_HMAC_KEY'
MAX_FAILURE_DIAGNOSTICS = 100  # per process; bounded so a failing store MAG NIET flood the logs
_FAILURE_COUNT = [0]
_SUPPRESSED_COUNT = [0]
_CAP_LOCK = threading.Lock()  # check + increment of the cap MOETEN be one atomic step


def suppressed_failure_count():
    return _SUPPRESSED_COUNT[0]
_ERROR_CLASS = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}')


def actor_hmac(actor_id):
    key = os.environ.get(HMAC_KEY_SETTING, '')
    if not key or not isinstance(actor_id, str):
        return None
    return hmac.new(key.encode(), actor_id.encode(), hashlib.sha256).hexdigest()


def _audit_failed(stage, *, error=None, outcome=None, snapshot_id=None, error_class=None):
    """Bounded failure diagnostic: fixed fields, class name only, capped per process.

    This is the last-resort observer: if the logger itself raises, nothing more can be
    reported, and the verdict MOET still stand, so that one error is contained here.
    """
    try:
        from src.request_diagnostics_v1 import _LOGGER, current_request_id
        with _CAP_LOCK:
            allowed = _FAILURE_COUNT[0] < MAX_FAILURE_DIAGNOSTICS
            if allowed:
                _FAILURE_COUNT[0] += 1
            else:
                _SUPPRESSED_COUNT[0] += 1
            first_suppressed = not allowed and _SUPPRESSED_COUNT[0] == 1
            suppressed_now = _SUPPRESSED_COUNT[0]
        if not allowed:
            if first_suppressed:  # ONE marker so the cap MAG NIET go silent
                _LOGGER.warning('metis_diagnostic %s', json.dumps({
                    'event': 'publication_refusal_audit_failed_suppressed', 'cap': MAX_FAILURE_DIAGNOSTICS,
                    'suppressed_count': suppressed_now, 'authority': 'non_authoritative_gate_observation'},
                    separators=(',', ':')))
            return
        name = type(error).__name__ if error is not None else error_class
        payload = {
            'event': 'publication_refusal_audit_failed', 'stage': stage,
            'error_class': (name if isinstance(name, str) and _ERROR_CLASS.fullmatch(name) else 'unrecognized_error')
                           if (error is not None or error_class is not None) else None,
            'outcome': outcome,
            'snapshot_id': snapshot_id if isinstance(snapshot_id, str) and _SNAPSHOT.fullmatch(snapshot_id) else None,
            'request_id': current_request_id(),
            'authority': 'non_authoritative_gate_observation',
        }
        _LOGGER.warning('metis_diagnostic %s', json.dumps(payload, separators=(',', ':')))
    except Exception:  # noqa: BLE001 - see docstring; bounded, verdict unaffected
        return


def _append_durable(console, *, actor_id, snapshot_id, reason_codes, revision):
    # #629 F1: separate append-only store; MAG NIET use the review ledger chain.
    try:
        from src import publication_refusal_store_v1 as store
        try:
            version = str(console._envelope(snapshot_id).get('version') or '')
        except Exception as exc:  # version is optional evidence
            version = ''
            _audit_failed('envelope_read', error=exc, snapshot_id=snapshot_id)
        store.append(console, snapshot_id=str(snapshot_id), object_version=version,
                     actor=str(actor_id), reason_codes=reason_codes, revision=revision,
                     on_corrupt=lambda name: _audit_failed('corrupt_record', outcome='skipped', snapshot_id=snapshot_id,
                                                             error_class=name))
    except Exception as exc:
        _audit_failed('durable_store', error=exc, snapshot_id=snapshot_id)


def record_publish_refusal(console, *, actor_id, snapshot_id, verdict, revision=None):
    try:
        if not isinstance(verdict, dict) or verdict.get('publish_allowed') is not False:
            return
        from src.request_diagnostics_v1 import _LOGGER, current_request_id
        if revision is None and console is not None:
            try:
                revision = console.objects_revision(snapshot_id)
            except Exception as exc:  # revision is optional evidence
                revision = None
                _audit_failed('revision_read', error=exc, snapshot_id=snapshot_id)
        blockers = verdict.get('blockers') or []
        blockers = blockers if isinstance(blockers, list) else []
        payload = {
            'event': 'publication_refused', 'verdict': 'refused',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'snapshot_id': snapshot_id if isinstance(snapshot_id, str) and _SNAPSHOT.fullmatch(snapshot_id) else None,
            'actor_hmac': actor_hmac(actor_id),
            'revision_sha256': hashlib.sha256(revision.encode()).hexdigest() if isinstance(revision, str) else None,
            'reason_codes': [c if isinstance(c, str) and _CODE.fullmatch(c) else 'unrecognized_reason'
                             for c in blockers[:MAX_REASON_CODES]],
            'omitted_reason_codes': max(0, len(blockers) - MAX_REASON_CODES),
            'request_id': current_request_id(),
            'authority': 'non_authoritative_gate_observation',
        }
        try:
            _LOGGER.info('metis_diagnostic %s', json.dumps(payload, separators=(',', ':')))
        except Exception as exc:
            _audit_failed('log', error=exc, snapshot_id=snapshot_id)
        if console is not None:
            _append_durable(console, actor_id=actor_id, snapshot_id=snapshot_id,
                            reason_codes=payload['reason_codes'], revision=revision)
    except Exception as exc:
        _audit_failed('record', error=exc, snapshot_id=snapshot_id)
