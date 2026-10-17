"""The telemetry hub: one event model, one correlation fill, one bounded store.

Every event is a flat JSON object with bounded values. Strings are redacted and
truncated; nested values are limited to the shapes producers already emit
(phase tables, counters, frame lists). Recording MAG NOOIT raise or change the
outcome of the work it observes.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

RING_SIZE = 5000
FILE_MAX_BYTES = 8 * 1024 * 1024
TOTAL_MAX_BYTES = 64 * 1024 * 1024
RETENTION_SECONDS = 7 * 24 * 3600
MAX_STRING = 240
MAX_KEYS = 48
MAX_LIST = 32
# Per-phase starts are request-local detail; the finished event carries the tree.
TRANSIENT_EVENTS = frozenset({"phase_started", "response_started", "response_completed"})
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.:/<>{}-]{0,120}")
_RUNTIME_ID = uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _clean(value: Any, depth: int = 0) -> Any:
    from src.structured_logging_v1 import redact
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value if value == value and abs(value) < 1e15 else None
    if isinstance(value, str):
        text = redact(value.replace("\r", " ").replace("\n", " "))
        return text[:MAX_STRING]
    if depth >= 4:
        return None
    if isinstance(value, dict):
        cleaned = {}
        for key, item in list(value.items())[:MAX_KEYS]:
            if isinstance(key, str) and _KEY.fullmatch(key):
                cleaned[key] = _clean(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_clean(item, depth + 1) for item in list(value)[:MAX_LIST]]
    return None


_IDENTITY: dict[int, dict[str, Any]] = {}


def identity() -> dict[str, Any]:
    """Deploy identity, read once per process (the marker file never changes at runtime)."""
    pid = os.getpid()
    cached = _IDENTITY.get(pid)
    if cached is None:
        from src.attempt_diagnostics_v1 import deployment_identity
        commit = os.getenv("METIS_BUILD_COMMIT") or deployment_identity() or "unknown"
        cached = _IDENTITY[pid] = {"commit": str(commit)[:64], "pid": pid, "runtime_id": _RUNTIME_ID,
                                   "instance": os.getenv("WEBSITE_INSTANCE_ID", "local")[:128]}
    return dict(cached)


def correlation() -> dict[str, Any]:
    """Correlation ids of the request in progress, if any."""
    try:
        from src.request_diagnostics_v1 import _CURRENT
        evidence = _CURRENT.get()
    except Exception:
        return {}
    if evidence is None:
        return {}
    return {key: value for key, value in (
        ("request_id", evidence.request_id), ("trace_id", getattr(evidence, "trace_id", None)),
        ("attempt_id", evidence.attempt_id), ("doc_ref", getattr(evidence, "doc_ref", None)),
    ) if value}


class JsonlSink:
    """Per-process append-only files with rotation, size cap and retention."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._handle = None
        self._path: Path | None = None
        self._last_prune = 0.0

    def _target(self) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        return self.directory / f"events-{day}-{os.getpid()}-{_RUNTIME_ID[:8]}.jsonl"

    def write(self, line: str) -> None:
        target = self._target()
        if self._path != target or self._handle is None:
            self.close()
            self._path, self._handle = target, open(target, "a", encoding="utf-8")
        self._handle.write(line + "\n")
        self._handle.flush()
        if self._handle.tell() > FILE_MAX_BYTES:
            self.close()
            target.rename(target.with_name(f"{target.stem}-{int(time.time())}.jsonl"))
            self.prune(force=True)
        elif time.monotonic() - self._last_prune > 60:
            self.prune()

    def prune(self, *, force: bool = False) -> None:
        self._last_prune = time.monotonic()
        files = sorted(self.files(), key=lambda path: path.stat().st_mtime)
        cutoff = time.time() - RETENTION_SECONDS
        total = sum(path.stat().st_size for path in files)
        for path in files:
            if path == self._path:
                continue
            if path.stat().st_mtime < cutoff or total > TOTAL_MAX_BYTES:
                total -= path.stat().st_size
                path.unlink(missing_ok=True)

    def files(self) -> list[Path]:
        return [path for path in self.directory.glob("events-*.jsonl") if path.is_file()]

    def close(self) -> None:
        if self._handle is not None:
            try:
                self._handle.close()
            finally:
                self._handle = None


class TelemetryHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ring: deque[dict[str, Any]] = deque(maxlen=RING_SIZE)
        self._sink: JsonlSink | None = None
        self.dropped = 0

    @property
    def directory(self) -> Path | None:
        return self._sink.directory if self._sink is not None else None

    def configure(self, directory: Path | None) -> None:
        with self._lock:
            if self._sink is not None:
                self._sink.close()
            self._sink = JsonlSink(directory) if directory is not None else None

    def record(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            if payload.get("event") in TRANSIENT_EVENTS:
                return None
            event = {"ts": _now(), **identity(), **correlation()}
            cleaned = _clean(payload) or {}
            # Producers keep their own timestamp and identity when they bring one.
            event.update({key: value for key, value in cleaned.items() if value is not None})
            event.setdefault("kind", "event")
            line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
            with self._lock:
                self._ring.append(event)
                if self._sink is not None:
                    self._sink.write(line)
            return event
        except Exception:
            self.dropped += 1
            return None

    def events(self, since_epoch: float | None = None) -> Iterator[dict[str, Any]]:
        """Stored events (all workers) when configured, else this process's ring."""
        sink = self._sink
        if sink is None:
            with self._lock:
                snapshot = list(self._ring)
            yield from (event for event in snapshot if _after(event, since_epoch))
            return
        for path in sorted(sink.files()):
            try:
                if since_epoch is not None and path.stat().st_mtime < since_epoch:
                    continue
                with open(path, encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(event, dict) and _after(event, since_epoch):
                            yield event
            except OSError:
                continue

    def flush(self) -> None:
        with self._lock:
            if self._sink is not None and self._sink._handle is not None:
                self._sink._handle.flush()


def parse_ts(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _after(event: dict[str, Any], since_epoch: float | None) -> bool:
    if since_epoch is None:
        return True
    stamp = parse_ts(event.get("ts") or event.get("timestamp"))
    return stamp is not None and stamp >= since_epoch


HUB = TelemetryHub()


def record_event(event: str, *, kind: str = "event", **fields: Any) -> None:
    """Record one bounded event; a no-op on any failure."""
    HUB.record({"event": event, "kind": kind, **fields})
