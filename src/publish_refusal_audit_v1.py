"""Publish-gate refusal audit event; observation only, never a gate authority.

The gate's existing verdict is passed in after it is final. This module MOET only
read it: the verdict, its reason codes, the document, the revision and a digest
of the actor. It MAG NIET change, re-evaluate or delay the verdict, and a logging
failure MAG NOOIT reach the caller. Allowed verdicts produce no event.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

MAX_REASON_CODES = 128
_CODE = re.compile(r'[a-z][a-z0-9_]{0,95}')
_SNAPSHOT = re.compile(r'[A-Za-z0-9_.:-]{1,128}')


def record_publish_refusal(console, *, actor_id, snapshot_id, verdict, revision=None):
    try:
        if not isinstance(verdict, dict) or verdict.get('publish_allowed') is not False:
            return
        from src.request_diagnostics_v1 import _LOGGER, current_request_id
        if revision is None and console is not None:
            try:
                revision = console.objects_revision(snapshot_id)
            except Exception:
                revision = None
        blockers = verdict.get('blockers') or []
        blockers = blockers if isinstance(blockers, list) else []
        payload = {
            'event': 'publication_refused', 'verdict': 'refused',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'snapshot_id': snapshot_id if isinstance(snapshot_id, str) and _SNAPSHOT.fullmatch(snapshot_id) else None,
            'actor_sha256': hashlib.sha256(actor_id.encode()).hexdigest() if isinstance(actor_id, str) else None,
            'revision_sha256': hashlib.sha256(revision.encode()).hexdigest() if isinstance(revision, str) else None,
            'reason_codes': [c if isinstance(c, str) and _CODE.fullmatch(c) else 'unrecognized_reason'
                             for c in blockers[:MAX_REASON_CODES]],
            'omitted_reason_codes': max(0, len(blockers) - MAX_REASON_CODES),
            'request_id': current_request_id(),
            'authority': 'non_authoritative_gate_observation',
        }
        _LOGGER.info('metis_diagnostic %s', json.dumps(payload, separators=(',', ':')))
    except Exception:
        pass
