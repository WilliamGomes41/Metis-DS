"""Kernel delivery over existing durable attempts; memory is only a wake hint."""
import asyncio
import logging
import uuid
from copy import deepcopy

from src.operations_console_v1 import ConsoleError
from src.processing_retry_v1 import assert_active, expire_running, now

LOG = logging.getLogger(__name__)


def claim(console, *, snapshot_id, attempt_id):
    """One short SQL row transaction chooses the only executing worker."""
    with console._reprocessing_transaction(snapshot_id):
        envelope = deepcopy(console._envelope(snapshot_id))
        attempt = assert_active(envelope, attempt_id, now())
        dispatch = attempt.get("dispatch") or {}
        if dispatch.get("version") != "source-dispatch-v1" or dispatch.get("state") != "pending":
            return None
        dispatch.update(state="claimed", token=uuid.uuid4().hex, claimed_at=now().isoformat())
        console._commit_prepared_store(envelopes={snapshot_id: envelope}, snapshot_id=snapshot_id)
        result = deepcopy(attempt)
    # Configuration and authorization are checked again by preparation/activation.
    return result


def pending(console):
    """Discover authorized unclaimed work; never turn receipt into a command."""
    found = []
    for row in console.list_envelopes():
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
    return found


class SourceProcessingDispatcher:
    def __init__(self, console):
        self.console = console
        self.workers = set()
        self.scheduled = set()
        self.poller = None
        self.capacity = asyncio.Semaphore(2)

    def notify(self, sid, attempt):
        key = (sid, attempt["attempt_id"])
        if key in self.scheduled:
            return
        self.scheduled.add(key)
        task = asyncio.create_task(self._deliver(sid, attempt))
        self.workers.add(task)
        def finished(done):
            self.workers.discard(done)
            self.scheduled.discard(key)
        task.add_done_callback(finished)

    async def _deliver(self, sid, attempt):
        async with self.capacity:
            try:
                await asyncio.to_thread(self.console.execute_source_selection,
                    actor_id=attempt["actor_id"], snapshot_id=sid, attempt=attempt)
            except Exception:
                # Kernel failure evidence/expiry remains authoritative. Do not
                # print provider prose, source text or credentials.
                LOG.warning("source_dispatch_attempt_stopped")

    async def scan(self):
        for sid, attempt in await asyncio.to_thread(pending, self.console):
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
        if self.poller:
            self.poller.cancel()
            await asyncio.gather(self.poller, return_exceptions=True)
        # Dropping a handle cannot abandon/retry durable work. Bounded workers
        # finish or expire, and another kernel discovers still-pending delivery.
        if self.workers:
            await asyncio.gather(*tuple(self.workers), return_exceptions=True)


def install_dispatcher(app, console):
    dispatcher = SourceProcessingDispatcher(console)
    app.state.source_selection_workers = dispatcher.workers  # diagnostics only
    app.add_event_handler("startup", dispatcher.start)
    app.add_event_handler("shutdown", dispatcher.stop)
    return dispatcher
