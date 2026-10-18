"""The telemetry hub: one event model, one correlation fill, one bounded store.

Every event is a flat JSON object with bounded values. Strings are redacted and
truncated; nested values are limited to the shapes producers already emit
(phase tables, counters, frame lists). Recording MAG NOOIT raise or change the
outcome of the work it observes.
"""
from __future__ import annotations

import hashlib
import heapq
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
# A current file written to within this period counts as a live worker's file.
ACTIVE_SECONDS = 600
MAX_STRING = 240
# At least the producers' own bounds (request_diagnostics_v1: MAX_TREE_NODES = 64 and the
# phase totals), so a bounded phase tree is never cut short again here.
MAX_KEYS = 96
MAX_LIST = 32
# Per-phase starts are request-local detail; the finished event carries the tree.
TRANSIENT_EVENTS = frozenset({"phase_started", "response_started", "response_completed"})
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.:/<>{}-]{0,120}")
_SNAPSHOT = re.compile(r"snap-[0-9a-f]{8,32}-[0-9a-f]{4,32}")
# Every signed-in account reads telemetry: identifiers of documents, objects,
# releases and people MAG NIET be stored. Document ids become ``doc_ref``.
_IDENTIFIER_KEYS = frozenset({"object_id", "object_ids", "release_id", "actor", "actor_id", "actor_hmac",
                              "account_id", "user_id", "uploader_account_id", "named_reviewers"})
_RUNTIME_ID = uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def doc_ref(snapshot_id: Any) -> str | None:
    """Pseudonymous document reference: correlates events without the document id."""
    if not isinstance(snapshot_id, str) or not _SNAPSHOT.fullmatch(snapshot_id):
        return None
    return "d_" + hashlib.sha256(snapshot_id.encode("ascii")).hexdigest()[:16]


def _clean(value: Any, depth: int = 0) -> Any:
    from src.structured_logging_v1 import redact
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value if value == value and abs(value) < 1e15 else None
    if isinstance(value, str):
        text = _SNAPSHOT.sub(lambda match: doc_ref(match.group()) or "", value.replace("\r", " ").replace("\n", " "))
        return redact(text)[:MAX_STRING]
    if depth >= 4:
        return None
    if isinstance(value, dict):
        cleaned, omitted = {}, {}
        for key, item in list(value.items())[:MAX_KEYS]:
            if not isinstance(key, str) or not _KEY.fullmatch(key) or key in _IDENTIFIER_KEYS:
                continue
            if key == "snapshot_id":
                cleaned.setdefault("doc_ref", doc_ref(item))
                continue
            cleaned[key] = _clean(item, depth + 1)
            if isinstance(item, (list, tuple)) and len(item) > MAX_LIST:
                # A list cut here MAG NIET read as complete: count what was left out.
                count_key = "omitted_item_count" if key == "items" else f"{key}_omitted"
                omitted[count_key] = omitted.get(count_key, 0) + len(item) - MAX_LIST
        for count_key, extra in omitted.items():
            base = cleaned.get(count_key)
            cleaned[count_key] = (base if isinstance(base, int) else 0) + extra
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


def _is_current_name(path: Path) -> bool:
    """events-<day>-<pid>-<runtime>.jsonl; a rotated file carries one more -<epoch> part."""
    return len(path.stem.split("-")) == 4


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
        if self._handle is not None and os.fstat(self._handle.fileno()).st_nlink == 0:
            # Another worker pruned this quiet file: continue in a fresh one.
            self.close()
        if self._path != target or self._handle is None:
            self.close()
            self._path, self._handle = target, open(target, "a", encoding="utf-8")
        self._handle.write(line + "\n")
        self._handle.flush()
        if os.fstat(self._handle.fileno()).st_nlink == 0:
            # Pruned by another worker between the check and the append: replay once in a fresh file.
            self.close()
            self._path, self._handle = target, open(target, "a", encoding="utf-8")
            self._handle.write(line + "\n")
            self._handle.flush()
        if self._handle.tell() > FILE_MAX_BYTES:
            self.close()
            # Nanoseconds: two rotations within one second MAG NIET overwrite each other.
            target.rename(target.with_name(f"{target.stem}-{time.time_ns()}.jsonl"))
            self.prune(force=True)
        elif time.monotonic() - self._last_prune > 60:
            self.prune()

    def prune(self, *, force: bool = False) -> None:
        self._last_prune = time.monotonic()
        # Workers prune the same directory: a file may vanish between listing and stat.
        stats = []
        for path in self.files():
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            stats.append((stat.st_mtime, stat.st_size, path))
        stats.sort(key=lambda item: item[0])
        cutoff = time.time() - RETENTION_SECONDS
        total = sum(size for _mtime, size, _path in stats)
        active_after = time.time() - ACTIVE_SECONDS
        for mtime, size, path in stats:
            # A live worker's current file stays; a quiet or dead worker's file may go
            # (a quiet worker reopens a fresh file on its next write).
            if path == self._path or (_is_current_name(path) and mtime >= active_after):
                continue
            if mtime < cutoff or total > TOTAL_MAX_BYTES:
                total -= size
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

    def configure(self, directory: Path | None) -> bool:
        """Use ``directory`` for the store; on any I/O failure keep the in-memory ring only.

        Telemetry is observational: an unusable directory MAG NIET stop a worker from booting.
        """
        with self._lock:
            if self._sink is not None:
                self._sink.close()
            try:
                self._sink = JsonlSink(directory) if directory is not None else None
            except Exception:
                self._sink = None
                self.dropped += 1
                return False
            return True

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
                    try:
                        self._sink.write(line)
                    except Exception:
                        # Storage failed at runtime: fall back to the ring, which
                        # events() reads only while no sink is configured.
                        self._sink.close()
                        self._sink = None
                        self.dropped += 1
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


# Upper bound on events one analysis holds in memory; the most recent ones are kept.
MAX_ANALYZED_EVENTS = 50_000


def recent_events(since: float, *, window_start: float | None = None) -> tuple[list[dict[str, Any]], bool]:
    """The newest MAX_ANALYZED_EVENTS events since ``since`` (streamed, bounded memory), oldest first.

    The flag says whether events at or after ``window_start`` (default ``since``) were left out;
    a reconstruction lookback before the window does not count.
    """
    seen = 0

    def counted():
        nonlocal seen
        for event in HUB.events(since):
            seen += 1
            yield event
    newest = heapq.nlargest(MAX_ANALYZED_EVENTS, counted(), key=lambda event: str(event.get("ts") or ""))
    newest.reverse()
    if seen <= len(newest):
        return newest, False
    oldest_kept = parse_ts(newest[0].get("ts")) if newest else None
    return newest, oldest_kept is None or oldest_kept > (since if window_start is None else window_start)
