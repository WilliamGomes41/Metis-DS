"""Exact semantic replay identity and validated proposal record.

Replay is an execution mode underneath semantic passage formation, never a
third formation method or a source of canonical knowledge. Records are reusable
only for the exact same frozen source and semantic contract. Candidate text is
always reconstructed again by semantic_passage_v1.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


SEMANTIC_REPLAY_VERSION = "semantic-replay-v1.0.0"
SEMANTIC_REPLAY_SPEC_KEY = "_semantic_replay"

EXECUTION_INFERENCE = "inference"
EXECUTION_REPLAY = "replay"

LOOKUP_HIT = "hit"
LOOKUP_MISS = "miss"
LOOKUP_REJECTED = "rejected"

REASON_NO_RECORD = "no_record"
REASON_IDENTITY_MISMATCH = "identity_mismatch"
REASON_RECORD_INVALID = "record_invalid"
REASON_PROPOSAL_HASH_MISMATCH = "proposal_hash_mismatch"


def stable_json_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ReplayLookup:
    status: str
    proposal: dict[str, Any] | None = None
    reason: str | None = None


def build_replay_identity(
    *,
    snapshot_id: str,
    source_sha256: str,
    document_id: str,
    source_blocks_hash: str,
    extractor_version: str,
    reconstruction_version: str,
    formation_policy_version: str,
    semantic_contract_version: str,
    prompt_hash: str,
    schema_hash: str,
    provider_id: str,
    model_id: str,
    model_config_hash: str,
) -> dict[str, Any]:
    components = {
        "snapshot_id": str(snapshot_id),
        "source_sha256": str(source_sha256),
        "document_id": str(document_id),
        "source_blocks_hash": str(source_blocks_hash),
        "extractor_version": str(extractor_version),
        "reconstruction_version": str(reconstruction_version),
        "formation_policy_version": str(formation_policy_version),
        "semantic_contract_version": str(semantic_contract_version),
        "prompt_hash": str(prompt_hash),
        "schema_hash": str(schema_hash),
        "provider_id": str(provider_id),
        "model_id": str(model_id),
        "model_config_hash": str(model_config_hash),
    }
    return {
        "version": SEMANTIC_REPLAY_VERSION,
        "hash": stable_json_hash(components),
        "components": components,
    }


def validated_inference_record(
    *,
    identity: Mapping[str, Any],
    proposal: Mapping[str, Any],
    replay_rejection_reason: str | None = None,
) -> dict[str, Any]:
    row = {
        "version": SEMANTIC_REPLAY_VERSION,
        "identity": deepcopy(dict(identity)),
        "proposal": deepcopy(dict(proposal)),
        "proposal_hash": stable_json_hash(proposal),
        "validation": "passed",
        "formation_method": "semantic",
        "origin_execution": EXECUTION_INFERENCE,
        "semantic_execution": EXECUTION_INFERENCE,
        "replay_from_proposal_hash": None,
    }
    if replay_rejection_reason:
        row["replay_rejection_reason"] = str(replay_rejection_reason)
    return row


def exact_replay_lookup(
    record: Any,
    *,
    expected_identity: Mapping[str, Any],
) -> ReplayLookup:
    if record is None:
        return ReplayLookup(LOOKUP_MISS, reason=REASON_NO_RECORD)
    if not isinstance(record, dict):
        return ReplayLookup(LOOKUP_REJECTED, reason=REASON_RECORD_INVALID)

    identity = record.get("identity")
    if not isinstance(identity, dict):
        return ReplayLookup(LOOKUP_REJECTED, reason=REASON_RECORD_INVALID)
    if identity != dict(expected_identity):
        return ReplayLookup(LOOKUP_MISS, reason=REASON_IDENTITY_MISMATCH)

    if (
        record.get("version") != SEMANTIC_REPLAY_VERSION
        or record.get("validation") != "passed"
        or record.get("formation_method") != "semantic"
        or record.get("origin_execution") != EXECUTION_INFERENCE
    ):
        return ReplayLookup(LOOKUP_REJECTED, reason=REASON_RECORD_INVALID)

    proposal = record.get("proposal")
    proposal_hash = str(record.get("proposal_hash") or "")
    if not isinstance(proposal, dict) or not proposal_hash:
        return ReplayLookup(LOOKUP_REJECTED, reason=REASON_RECORD_INVALID)
    if stable_json_hash(proposal) != proposal_hash:
        return ReplayLookup(LOOKUP_REJECTED, reason=REASON_PROPOSAL_HASH_MISMATCH)

    return ReplayLookup(LOOKUP_HIT, proposal=deepcopy(proposal))


def replayed_record(record: Mapping[str, Any]) -> dict[str, Any]:
    row = deepcopy(dict(record))
    row["semantic_execution"] = EXECUTION_REPLAY
    row["replay_from_proposal_hash"] = str(row.get("proposal_hash") or "")
    row.pop("replay_rejection_reason", None)
    return row
