#!/usr/bin/env python3
"""Append-only, hash-chained review/audit event ledger."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from src.integrity_kernel import stable_hash


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]


def append_event(path: Path, *, event_type: str, object_id: str, object_version: str, actor: str, details: dict[str, Any]) -> dict[str, Any]:
    events=read_events(path); prev=events[-1]['event_hash'] if events else None
    body={"event_type":event_type,"object_id":object_id,"object_version":object_version,"actor":actor,
          "occurred_at":datetime.now(timezone.utc).isoformat(timespec='seconds'),"details":details,"previous_event_hash":prev}
    body['event_hash']=stable_hash(body)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as f: f.write(json.dumps(body,ensure_ascii=False,sort_keys=True)+'\n')
    return body


def verify_ledger(path: Path) -> list[str]:
    events=read_events(path); errors=[]; prev=None
    for i,e in enumerate(events):
        x=dict(e); got=x.pop('event_hash',None)
        if x.get('previous_event_hash')!=prev: errors.append(f'chain_previous_mismatch:{i}')
        if stable_hash(x)!=got: errors.append(f'event_hash_mismatch:{i}')
        prev=got
    return errors
