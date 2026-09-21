"""Stable identity helpers for researcher-facing Onderwerp labels.

Topic identity is syntactic only: Unicode normalization, whitespace collapse and
case-insensitive comparison. Semantic synonym merging is deliberately out of
scope. The deterministic topic id makes backfill and recovery replay stable.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata


def normalize_topic_label(value: str | None) -> str:
    raw = "" if value is None else str(value)
    normalized = unicodedata.normalize("NFKC", raw)
    return re.sub(r"\s+", " ", normalized).strip()


def topic_identity_key(value: str | None) -> str:
    return normalize_topic_label(value).casefold()


def topic_id_for_key(identity_key: str) -> str:
    key = str(identity_key or "")
    if not key:
        raise ValueError("topic_identity_required")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"topic-{digest}"


def topic_identity(value: str | None) -> tuple[str, str, str]:
    label = normalize_topic_label(value)
    key = topic_identity_key(label)
    if not key:
        raise ValueError("topic_identity_required")
    return topic_id_for_key(key), key, label
