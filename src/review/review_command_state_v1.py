"""Request-owned inputs and staged changes for the existing Review kernel.

PostgreSQL remains authoritative. This context only supplies the explicitly
captured working set while the existing command/MRO validates a decision.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class GenerationPrecondition:
    snapshot_id: str
    counters: str


@dataclass(frozen=True)
class ObjectSetPrecondition:
    token: str


@dataclass(frozen=True)
class UnconditionalReview:
    """Compatibility with existing direct callers that supply no precondition."""


ReviewPrecondition = GenerationPrecondition | ObjectSetPrecondition | UnconditionalReview


@dataclass(frozen=True)
class ReviewCommandInputs:
    owner: Any
    snapshot_id: str
    envelope: dict[str, Any]
    histories: list[dict[str, Any]]
    bindings: list[dict[str, Any]]
    fragments: Any
    source_bytes: bytes | None
    source_path: Path | None
    target_object_id: str
    interaction_id: str = ''
    precondition: ReviewPrecondition = field(default_factory=UnconditionalReview)
    source_failure: str | None = None

    def __post_init__(self) -> None:
        # Frozen fields alone do not detach the mutable records from the caller.
        from src.vorming.prepared_source_views_v1 import freeze
        for name in ('envelope', 'histories', 'bindings', 'fragments'):
            object.__setattr__(self, name, freeze(deepcopy(getattr(self, name))))
        if self.source_bytes is not None:
            object.__setattr__(self, 'source_bytes', bytes(self.source_bytes))


class ReviewChangeSet:
    """One command's disposable working state; never shared console maps."""

    def __init__(self, inputs: ReviewCommandInputs) -> None:
        self.inputs = inputs
        self.envelope = deepcopy(inputs.envelope)
        self.histories = deepcopy(inputs.histories)
        self.bindings = deepcopy(inputs.bindings)
        self.commit_count = 0
        self.object_transitions = []

    @property
    def snapshot_id(self) -> str:
        return self.inputs.snapshot_id

    @property
    def object_ids(self) -> list[str]:
        return sorted({str(row['object_id']) for row in self.histories})

    @property
    def revision(self) -> str:
        # This scoped token is internal to the staged command. The outer owner
        # independently validates the caller's original generation/m2 contract.
        return self.inputs.owner.workflow_document_store.revision_for_rows(self.histories)

    def stage(self, *, envelopes=None, bindings=None, objects=None,
              expected_revision=None, ledger_fn=None, snapshot_id=None) -> None:
        from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT

        sid = snapshot_id or (objects[0] if objects is not None else self.snapshot_id)
        if sid != self.snapshot_id or (objects is not None and objects[0] != sid):
            raise ConsoleError('review_command_snapshot_mismatch')
        if expected_revision not in (None, '') and expected_revision != self.revision:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=self.revision)
        if envelopes is not None:
            if set(envelopes) - {sid} or sid not in envelopes:
                raise ConsoleError('review_command_snapshot_mismatch')
            self.envelope = deepcopy(envelopes[sid])
        if bindings is not None:
            if set(bindings) - {sid}:
                raise ConsoleError('review_command_snapshot_mismatch')
            self.bindings = deepcopy(bindings.get(sid, []))
        if objects is not None:
            from src.review.revision_workflow import validate_revision_write
            validate_revision_write(self.histories, objects[1], snapshot_id=sid)
            self.histories = deepcopy(objects[1])
            self.object_transitions.append(deepcopy(self.histories))
        if ledger_fn is not None:
            ledger_fn()
        # Even an unchanged explicit "later" commit changes form freshness.
        # A semantic duplicate returns before staging and leaves this zero.
        self.commit_count += 1

    @contextmanager
    def savepoint(self) -> Iterator[None]:
        saved = deepcopy((self.envelope, self.histories, self.bindings, self.commit_count, self.object_transitions))
        try:
            yield
        except BaseException:
            self.envelope, self.histories, self.bindings, self.commit_count, self.object_transitions = saved
            raise


_ACTIVE: ContextVar[ReviewChangeSet | None] = ContextVar('review_command_changes', default=None)


def active_review_command(owner: Any, snapshot_id: str | None = None) -> ReviewChangeSet | None:
    state = _ACTIVE.get()
    if state is None or state.inputs.owner is not owner:
        return None
    if snapshot_id is not None and snapshot_id != state.snapshot_id:
        from src.operations_console_v1 import ConsoleError
        raise ConsoleError('review_command_snapshot_mismatch')
    return state


def review_command_for_ledger(path: Path) -> ReviewChangeSet | None:
    state = _ACTIVE.get()
    if state is not None and Path(state.inputs.owner._ledger_path) == Path(path):
        return state
    return None


def review_bindings_view(owner: Any) -> dict[str, list[dict[str, Any]]]:
    state = active_review_command(owner)
    return {state.snapshot_id: state.bindings} if state is not None else owner._bindings


def review_envelopes_view(owner: Any) -> dict[str, dict[str, Any]]:
    state = active_review_command(owner)
    return {state.snapshot_id: state.envelope} if state is not None else owner._envelopes


@contextmanager
def review_command_scope(inputs: ReviewCommandInputs) -> Iterator[ReviewChangeSet]:
    if _ACTIVE.get() is not None:
        from src.operations_console_v1 import ConsoleError
        raise ConsoleError('review_command_scope_already_active')
    state = ReviewChangeSet(inputs)
    token = _ACTIVE.set(state)
    try:
        yield state
    finally:
        _ACTIVE.reset(token)
