#!/usr/bin/env python3
"""Append-only, hash-chained review/audit event ledger."""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Protocol

from src.integrity_kernel import stable_hash


class ReviewLedgerBackend(Protocol):
    def read_events(self) -> list[dict[str, Any]]: ...
    def append_event(
        self,
        *,
        event_type: str,
        object_id: str,
        object_version: str,
        actor: str,
        details: dict[str, Any],
    ) -> dict[str, Any]: ...
    def buffered(self) -> Any: ...


_BACKENDS: dict[str, ReviewLedgerBackend] = {}


def _key(path: Path) -> str:
    # Resolve directory aliases without touching the unused PG ledger file.
    return str(Path(path).parent.resolve() / Path(path).name)


def register_backend(path: Path, backend: ReviewLedgerBackend) -> None:
    _BACKENDS[_key(path)] = backend


def unregister_backend(path: Path) -> None:
    _BACKENDS.pop(_key(path), None)


def _backend(path: Path) -> ReviewLedgerBackend | None:
    return _BACKENDS.get(_key(path))


@contextmanager
def buffer_events(path: Path) -> Iterator[None]:
    backend = _backend(path)
    if backend is None:
        yield
        return
    with backend.buffered():
        yield


def read_events(path: Path) -> list[dict[str, Any]]:
    backend = _backend(path)
    scoped = _review_command_events(path, backend)
    if scoped is not None:
        return scoped
    if backend is not None:
        return backend.read_events()
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def read_command_events(path: Path) -> list[dict[str, Any]]:
    """Explicit command-local evidence read; public audit reads stay unchanged."""
    backend = _backend(path)
    scoped = _review_command_events(path, backend)
    if scoped is not None:
        return scoped
    reader = getattr(backend, "read_command_events", None)
    return reader() if reader is not None else read_events(path)


def _review_command_events(path: Path, backend: Any) -> list[dict[str, Any]] | None:
    from src.review.review_command_state_v1 import review_command_for_ledger
    command = review_command_for_ledger(path)
    if command is None:
        return None
    reader = getattr(backend, 'read_review_command_events', None)
    if reader is None:
        from src.operations_console_v1 import ConsoleError
        raise ConsoleError('review_command_ledger_backend_required')
    return reader(command.snapshot_id, command.object_ids,
                  interaction_id=command.inputs.interaction_id)


def append_event(
    path: Path,
    *,
    event_type: str,
    object_id: str,
    object_version: str,
    actor: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    backend = _backend(path)
    if backend is not None:
        return backend.append_event(
            event_type=event_type,
            object_id=object_id,
            object_version=object_version,
            actor=actor,
            details=details,
        )
    events = read_events(path)
    prev = events[-1]["event_hash"] if events else None
    body = {
        "event_type": event_type,
        "object_id": object_id,
        "object_version": object_version,
        "actor": actor,
        "occurred_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "details": details,
        "previous_event_hash": prev,
    }
    body["event_hash"] = stable_hash(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(body, ensure_ascii=False, sort_keys=True) + "\n")
    return body


def verify_ledger(path: Path) -> list[str]:
    events = read_events(path)
    errors: list[str] = []
    prev = None
    for index, event in enumerate(events):
        body = dict(event)
        got = body.pop("event_hash", None)
        if body.get("previous_event_hash") != prev:
            errors.append(f"chain_previous_mismatch:{index}")
        if stable_hash(body) != got:
            errors.append(f"event_hash_mismatch:{index}")
        prev = got
    return errors
