"""VSA F2 contract proof for exact semantic replay.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.llm_provider_v1 import LLM_API_KEY_ENV, LLM_MODEL_ENV
from src.operations_console_v1 import PRE_REVIEW_BLOCKED, ConsoleError, OperationsConsole
from src.pre_review_semantic_v1 import (
    PASSAGE_FORMATION_MODE_ENV,
    SEMANTIC_MODE,
    bind_pre_review_semantic_processing,
)
from src.semantic_replay_v1 import (
    EXECUTION_INFERENCE,
    EXECUTION_REPLAY,
    LOOKUP_HIT,
    LOOKUP_MISS,
    LOOKUP_REJECTED,
    REASON_PROPOSAL_HASH_MISMATCH,
    build_replay_identity,
    exact_replay_lookup,
    stable_json_hash,
    validated_inference_record,
)


TEXT = "Bespreek samen welke behandeling het beste past."


def _fragment(
    fragment_id: str,
    text: str = TEXT,
    *,
    section_path: list[str] | None = None,
) -> dict:
    return {
        "fragment_id": fragment_id,
        "fragment_hash": f"hash-{fragment_id}",
        "raw_text": text,
        "clean_text": text,
        "section_path": section_path or ["Richtlijn", "2 Aanbevelingen"],
        "source_locator": {
            "locator_type": "web_line_range",
            "locator_value": f"lines:{fragment_id[-1:]}-{fragment_id[-1:]}",
        },
    }


def _response(proposal: dict) -> dict:
    return {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps(proposal)}
                ],
            }
        ]
    }


def _full_span_proposal(payload: dict, *, proposed_type: str = "recommendation") -> dict:
    blocks = json.loads(payload["input"][1]["content"])["source_blocks"]
    return {
        "objects": [
            {
                "spans": [
                    {
                        "block_id": block["block_id"],
                        "start": 0,
                        "end": len(block["text"]),
                    }
                ],
                "proposed_object_type": proposed_type,
            }
            for block in blocks
        ],
        "abstain_reason": None,
    }


def _identity(**overrides) -> dict:
    values = {
        "snapshot_id": "snap-aaaaaaaaaaaaaaaa-bbbbbbbb",
        "source_sha256": "a" * 64,
        "document_id": "doc-1",
        "source_blocks_hash": "b" * 64,
        "extractor_version": "html-visible-text-v1.1.0",
        "reconstruction_version": "source-reconstruction-v1.0.0",
        "formation_policy_version": "passage-formation-policy-v1.0.0",
        "semantic_contract_version": "semantic-passage-v1.0.0",
        "prompt_hash": "c" * 64,
        "schema_hash": "d" * 64,
        "provider_id": "openai-responses-v1",
        "model_id": "test-model",
        "model_config_hash": "e" * 64,
    }
    values.update(overrides)
    return build_replay_identity(**values)


def _proposal() -> dict:
    return {
        "objects": [
            {
                "spans": [
                    {"block_id": "semblock-known", "start": 0, "end": 4}
                ],
                "proposed_object_type": "recommendation",
            }
        ],
        "abstain_reason": None,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_sha256", "f" * 64),
        ("source_blocks_hash", "f" * 64),
        ("extractor_version", "html-visible-text-v2"),
        ("reconstruction_version", "source-reconstruction-v2"),
        ("formation_policy_version", "passage-formation-policy-v2"),
        ("semantic_contract_version", "semantic-passage-v2"),
        ("prompt_hash", "f" * 64),
        ("schema_hash", "f" * 64),
        ("provider_id", "other-provider"),
        ("model_id", "other-model"),
        ("model_config_hash", "f" * 64),
    ],
)
def test_exact_identity_change_is_a_replay_miss(field: str, value: str) -> None:
    identity = _identity()
    record = validated_inference_record(identity=identity, proposal=_proposal())

    assert exact_replay_lookup(
        record,
        expected_identity=_identity(**{field: value}),
    ).status == LOOKUP_MISS


def test_exact_identity_and_proposal_hash_are_required_for_hit() -> None:
    identity = _identity()
    record = validated_inference_record(identity=identity, proposal=_proposal())

    hit = exact_replay_lookup(record, expected_identity=identity)
    assert hit.status == LOOKUP_HIT
    assert hit.proposal == _proposal()

    corrupt = deepcopy(record)
    corrupt["proposal"]["objects"][0]["proposed_object_type"] = "definition"
    rejected = exact_replay_lookup(corrupt, expected_identity=identity)
    assert rejected.status == LOOKUP_REJECTED
    assert rejected.reason == REASON_PROPOSAL_HASH_MISMATCH


def _console_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    return tmp_path / "root", tmp_path / "sources", tmp_path / "runtime"


def _new_console(tmp_path: Path) -> OperationsConsole:
    root, source_store, runtime = _console_paths(tmp_path)
    return OperationsConsole(root=root, source_store=source_store, runtime=runtime)


def _bind(
    console: OperationsConsole,
    *,
    env: dict[str, str],
    post_json,
    fragments: list[dict],
) -> None:
    console._extract = lambda *_args, **_kwargs: deepcopy(fragments)
    bind_pre_review_semantic_processing(
        console,
        environ=env,
        post_json=post_json,
    )


def _ingest(
    console: OperationsConsole,
    *,
    researcher_id: str,
    reviewer_id: str,
) -> dict:
    return console.ingest(
        actor_id=researcher_id,
        filename="replay.html",
        data=b"<html><body>replay</body></html>",
        content_type="text/html",
        ingest_kind="new",
        title="Replay",
        version="1.0",
        date="2026-09-24",
        live_url="",
        class_="richtlijn",
        family="kwaliteit",
        named_reviewers=[reviewer_id],
    )


def _accounts(console: OperationsConsole) -> tuple[dict, dict]:
    researcher = console.create_account(
        username="researcher-f2",
        password="researcher-secret",
        roles=("researcher",),
        display_name="Researcher F2",
    )
    reviewer = console.create_account(
        username="reviewer-f2",
        password="reviewer-secret",
        roles=("reviewer",),
        display_name="Reviewer F2",
    )
    return researcher, reviewer


def test_exact_replay_survives_restart_and_makes_zero_provider_calls(tmp_path: Path) -> None:
    fragments = [
        _fragment(
            "p1",
            section_path=["Richtlijn", "Samenvatting", "Aanbevelingen"],
        ),
        _fragment(
            "p2",
            section_path=["Richtlijn", "2 Aanbevelingen"],
        ),
    ]
    env = {
        PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        LLM_API_KEY_ENV: "product-key",
        LLM_MODEL_ENV: "test-model",
    }
    calls = 0

    def inference(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        nonlocal calls
        calls += 1
        return _response(_full_span_proposal(payload))

    console = _new_console(tmp_path)
    researcher, reviewer = _accounts(console)
    _bind(console, env=env, post_json=inference, fragments=fragments)
    receipt = _ingest(
        console,
        researcher_id=researcher["account_id"],
        reviewer_id=reviewer["account_id"],
    )

    assert calls == 1
    snapshot_id = receipt["snapshot_id"]
    first = console.snapshot_objects(snapshot_id)
    inference_record = console._envelope(snapshot_id)["semantic_replay"]
    assert inference_record["last_execution"] == EXECUTION_INFERENCE
    assert inference_record["origin_execution"] == EXECUTION_INFERENCE
    assert inference_record["identity"]["components"]["source_sha256"] == receipt["sha256"]
    candidate = next(row for row in first if row.get("object_type") != "document")
    assert candidate["metadata"]["source_occurrence_authority"]["principal_section_role"] == "primary"

    restarted = _new_console(tmp_path)
    replay_env = {
        PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        LLM_MODEL_ENV: "test-model",
    }

    def must_not_call_provider(*_args):
        raise AssertionError("exact replay must not call the semantic provider")

    _bind(
        restarted,
        env=replay_env,
        post_json=must_not_call_provider,
        fragments=fragments,
    )
    recovered = restarted.reextract_unpublished(
        actor_id=researcher["account_id"],
        snapshot_id=snapshot_id,
    )

    assert recovered["snapshot_id"] == snapshot_id
    after = restarted.snapshot_objects(snapshot_id)
    assert after == first
    replay_record = restarted._envelope(snapshot_id)["semantic_replay"]
    assert replay_record["last_execution"] == EXECUTION_REPLAY
    assert replay_record["origin_execution"] == EXECUTION_INFERENCE
    assert replay_record["replay_from_proposal_hash"] == replay_record["proposal_hash"]
    assert calls == 1


def test_model_identity_change_forces_inference_not_replay(tmp_path: Path) -> None:
    fragments = [_fragment("p1")]
    first_env = {
        PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        LLM_API_KEY_ENV: "product-key",
        LLM_MODEL_ENV: "test-model",
    }
    calls = 0

    def provider(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        nonlocal calls
        calls += 1
        return _response(_full_span_proposal(payload))

    console = _new_console(tmp_path)
    researcher, reviewer = _accounts(console)
    _bind(console, env=first_env, post_json=provider, fragments=fragments)
    receipt = _ingest(
        console,
        researcher_id=researcher["account_id"],
        reviewer_id=reviewer["account_id"],
    )
    assert calls == 1

    restarted = _new_console(tmp_path)
    changed_env = {
        PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        LLM_API_KEY_ENV: "product-key",
        LLM_MODEL_ENV: "changed-model",
    }
    _bind(restarted, env=changed_env, post_json=provider, fragments=fragments)
    restarted.reextract_unpublished(
        actor_id=researcher["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )

    assert calls == 2
    record = restarted._envelope(receipt["snapshot_id"])["semantic_replay"]
    assert record["last_execution"] == EXECUTION_INFERENCE
    assert record["identity"]["components"]["model_id"] == "changed-model"


def _persist_corrupt_but_hash_consistent_replay(
    console: OperationsConsole,
    snapshot_id: str,
) -> dict:
    envelope = deepcopy(console._envelope(snapshot_id))
    record = deepcopy(envelope["semantic_replay"])
    record["proposal"]["objects"][0]["spans"][0]["block_id"] = "semblock-does-not-exist"
    record["proposal_hash"] = stable_json_hash(record["proposal"])
    envelope["semantic_replay"] = record
    console._envelopes[snapshot_id] = envelope
    console._save_envelopes()
    return record


def test_corrupt_replay_is_revalidated_then_replaced_by_inference(tmp_path: Path) -> None:
    fragments = [_fragment("p1")]
    env = {
        PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        LLM_API_KEY_ENV: "product-key",
        LLM_MODEL_ENV: "test-model",
    }
    calls = 0

    def provider(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        nonlocal calls
        calls += 1
        return _response(_full_span_proposal(payload))

    console = _new_console(tmp_path)
    researcher, reviewer = _accounts(console)
    _bind(console, env=env, post_json=provider, fragments=fragments)
    receipt = _ingest(
        console,
        researcher_id=researcher["account_id"],
        reviewer_id=reviewer["account_id"],
    )
    _persist_corrupt_but_hash_consistent_replay(console, receipt["snapshot_id"])

    restarted = _new_console(tmp_path)
    _bind(restarted, env=env, post_json=provider, fragments=fragments)
    restarted.reextract_unpublished(
        actor_id=researcher["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )

    assert calls == 2
    repaired = restarted._envelope(receipt["snapshot_id"])["semantic_replay"]
    assert repaired["last_execution"] == EXECUTION_INFERENCE
    assert repaired["replay_rejection_reason"] == "semantic_span_unknown_block"


def test_corrupt_replay_plus_provider_failure_remains_fail_closed(tmp_path: Path) -> None:
    fragments = [_fragment("p1")]
    env = {
        PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        LLM_API_KEY_ENV: "product-key",
        LLM_MODEL_ENV: "test-model",
    }

    def provider(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        return _response(_full_span_proposal(payload))

    console = _new_console(tmp_path)
    researcher, reviewer = _accounts(console)
    _bind(console, env=env, post_json=provider, fragments=fragments)
    receipt = _ingest(
        console,
        researcher_id=researcher["account_id"],
        reviewer_id=reviewer["account_id"],
    )
    snapshot_id = receipt["snapshot_id"]
    corrupt_record = _persist_corrupt_but_hash_consistent_replay(console, snapshot_id)
    before_objects = console.snapshot_objects(snapshot_id)

    restarted = _new_console(tmp_path)

    def unavailable(*_args):
        raise ConsoleError("pre_review_llm_provider_unavailable")

    _bind(restarted, env=env, post_json=unavailable, fragments=fragments)
    with pytest.raises(ConsoleError) as error:
        restarted.reextract_unpublished(
            actor_id=researcher["account_id"],
            snapshot_id=snapshot_id,
        )

    assert error.value.code == "pre_review_llm_provider_unavailable"
    assert restarted.snapshot_objects(snapshot_id) == before_objects
    assert restarted._envelope(snapshot_id)["semantic_replay"] == corrupt_record


def test_abstention_never_creates_a_replay_artifact(tmp_path: Path) -> None:
    fragments = [_fragment("p1")]
    env = {
        PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        LLM_API_KEY_ENV: "product-key",
        LLM_MODEL_ENV: "test-model",
    }

    def abstain(*_args):
        return _response(
            {
                "objects": [],
                "abstain_reason": "insufficient_semantic_context",
            }
        )

    console = _new_console(tmp_path)
    researcher, reviewer = _accounts(console)
    _bind(console, env=env, post_json=abstain, fragments=fragments)
    receipt = _ingest(
        console,
        researcher_id=researcher["account_id"],
        reviewer_id=reviewer["account_id"],
    )

    assert receipt["publication_eligibility"] == PRE_REVIEW_BLOCKED
    assert receipt["processing_blocker"] == "pre_review_llm_abstained"
    assert "semantic_replay" not in console._envelope(receipt["snapshot_id"])
    assert console.snapshot_objects(receipt["snapshot_id"]) == []
