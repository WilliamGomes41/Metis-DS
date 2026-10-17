"""Storeopdracht: one owner per durable command (#678, decision B1).

The outermost store boundary of a console owns the command. It reloads once,
owns the PostgreSQL transaction and, only after the commit or rollback,
rebuilds the disposable disk mirrors as their single writer. Nested boundaries
of the same console join the command; another console MAG NIET join.

This module holds only the command state and the mirror deferral. The review
mixin (``workflow_review_cutover_v1``) owns the boundary itself.
"""
from __future__ import annotations

from contextvars import ContextVar, Token
from copy import deepcopy
from typing import Any


class StoreCommand:
    """Deferred mirror work of one open command. NOOIT a second authority."""

    __slots__ = ("owner", "fresh", "poisoned", "snapshot_ids", "bindings", "envelopes", "objects", "events")

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.fresh = False
        # A participant whose state refresh failed: the owner MAG NIET commit.
        self.poisoned = False
        self.snapshot_ids: set[str] = set()
        self.bindings = False
        self.envelopes = False
        self.objects: set[str] = set()
        self.events: list[dict[str, Any]] = []


_ACTIVE: ContextVar[StoreCommand | None] = ContextVar("metis_store_command", default=None)


def active_store_command() -> StoreCommand | None:
    return _ACTIVE.get()


def owned_store_command(owner: Any) -> StoreCommand | None:
    """The open command when ``owner`` owns it, else None."""
    command = _ACTIVE.get()
    return command if command is not None and command.owner is owner else None


def open_store_command(owner: Any) -> tuple[StoreCommand, Token]:
    command = StoreCommand(owner)
    return command, _ACTIVE.set(command)


def close_store_command(token: Token) -> None:
    _ACTIVE.reset(token)


def defer_mirror_events(store: Any, events: list[dict[str, Any]]) -> bool:
    """Hold ledger mirror lines until the owning command has committed."""
    command = _ACTIVE.get()
    if command is None or getattr(command.owner, "workflow_review_store", None) is not store:
        return False
    command.events.extend(deepcopy(events))
    return True
