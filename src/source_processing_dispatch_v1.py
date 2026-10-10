"""Kernel delivery over existing durable attempts; memory is only a wake hint."""
import asyncio
import logging
import uuid
from copy import deepcopy
from contextlib import nullcontext
from threading import Event

from src.operations_console_v1 import ConsoleError
from src.processing_retry_v1 import assert_active, expire_running, now

LOG = logging.getLogger(__name__)


def claim(console, *, snapshot_id, attempt_id, actor_id=None, stop_event=None):
    """One short SQL row transaction chooses the only executing worker."""
    with console._reprocessing_transaction(snapshot_id):
        envelope = deepcopy(console._envelope(snapshot_id))
        attempt = assert_active(envelope, attempt_id, now())
        from src.source_selection_v1 import authorize
        authorize(console, actor_id or attempt["actor_id"], envelope)
        if actor_id is not None and attempt["actor_id"] != actor_id:
            raise ConsoleError("processing_command_conflict")
        dispatch = attempt.get("dispatch") or {}
        if dispatch.get("version") != "source-dispatch-v1" or dispatch.get("state") != "pending":
            return None
        if stop_event is not None and stop_event.is_set():
            return None
        dispatch.update(state="claimed", token=uuid.uuid4().hex, claimed_at=now().isoformat())
        console._commit_prepared_store(envelopes={snapshot_id: envelope}, snapshot_id=snapshot_id)
        result = deepcopy(attempt)
    # Configuration and authorization are checked again by preparation/activation.
    return result


def pending(console, *, limit=None, after_snapshot=None):
    """Discover authorized unclaimed work; never turn receipt into a command."""
    found = []
    if limit is not None and limit <= 0:
        return found
    rows = console.list_envelopes()
    if after_snapshot is not None:
        index = next((i for i, row in enumerate(rows) if row["snapshot_id"] == after_snapshot), -1)
        rows = rows[index + 1:] + rows[:index + 1]
    for row in rows:
        sid = row["snapshot_id"]
        envelope = console._envelope(sid)
        attempts = envelope.get("processing_attempts") or []
        if not any(a.get("dispatch") and a["state"] == "running" for a in attempts):
            continue
        with console._reprocessing_transaction(sid):
            envelope = deepcopy(console._envelope(sid))
            before = deepcopy(envelope.get("processing_attempts"))
            expire_running(envelope, now())
            if envelope.get("processing_attempts") != before:
                console._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
            for attempt in envelope.get("processing_attempts") or []:
                if (attempt["state"] == "running"
                        and (attempt.get("dispatch") or {}).get("state") == "pending"):
                    found.append((sid, deepcopy(attempt)))
                    if limit is not None and len(found) >= limit:
                        return found
    return found


class SourceProcessingDispatcher:
    def __init__(self, console, *, shutdown_grace=5):
        self.console = console
        self.workers = set()
        self.scheduled = set()
        self.poller = None
        self.max_workers = 2
        self.shutdown_grace = shutdown_grace
        self.stopping = Event()
        self.scan_after = None  # disposable fairness cursor, never command state

    def notify(self, sid, attempt):
        key = (sid, attempt["attempt_id"])
        if self.stopping.is_set() or key in self.scheduled or len(self.workers) >= self.max_workers:
            return False
        self.scheduled.add(key)
        task = asyncio.create_task(self._deliver(sid, attempt))
        self.workers.add(task)
        def finished(done):
            self.workers.discard(done)
            self.scheduled.discard(key)
        task.add_done_callback(finished)
        return True

    def _execute(self, sid, attempt):
        if self.stopping.is_set():
            return
        # Acquire the extractor's existing shared lock before the durable claim.
        # A busy slot leaves this exact command pending, without failure/retry.
        from src.docling_pdf_v1 import reserve_conversion_capacity
        uses_docling = (attempt.get("processing_configuration") or {}).get("docling")
        needs_slot = uses_docling and self.console._envelope(sid)["content_kind"] == "pdf"
        with reserve_conversion_capacity() if needs_slot else nullcontext(True) as available:
            if available and not self.stopping.is_set():
                self.console.execute_source_selection(actor_id=attempt["actor_id"],
                    snapshot_id=sid, attempt=attempt, _dispatch_stop=self.stopping)

    async def _deliver(self, sid, attempt):
        try:
            await asyncio.to_thread(self._execute, sid, attempt)
        except Exception:
            # Kernel failure evidence/expiry remains authoritative. Do not
            # print provider prose, source text or credentials.
            LOG.warning("source_dispatch_attempt_stopped")

    async def scan(self):
        room = self.max_workers - len(self.workers)
        if self.stopping.is_set() or room <= 0:
            return
        for sid, attempt in await asyncio.to_thread(pending, self.console, limit=room, after_snapshot=self.scan_after):
            self.scan_after = sid
            self.notify(sid, attempt)

    async def _poll(self):
        while True:
            await asyncio.sleep(1)
            try:
                await self.scan()
            except Exception:
                LOG.warning("source_dispatch_scan_failed")

    async def start(self):
        await self.scan()
        self.poller = asyncio.create_task(self._poll())

    async def stop(self):
        self.stopping.set()
        if self.poller:
            self.poller.cancel()
            await asyncio.gather(self.poller, return_exceptions=True)
        # Do not cancel to_thread handles: cancellation does not stop a thread.
        # After this grace, active threads still own their original expiry/fences.
        # This bounds the ASGI hook, not whole-process termination.
        if self.workers:
            _, unfinished = await asyncio.wait(tuple(self.workers), timeout=self.shutdown_grace)
            if unfinished:
                LOG.warning("source_dispatch_shutdown_execution_unresolved")


def install_dispatcher(app, console):
    dispatcher = SourceProcessingDispatcher(console)
    app.state.source_selection_workers = dispatcher.workers  # diagnostics only
    app.add_event_handler("startup", dispatcher.start)
    app.add_event_handler("shutdown", dispatcher.stop)
    return dispatcher
