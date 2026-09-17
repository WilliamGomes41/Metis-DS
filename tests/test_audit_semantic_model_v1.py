"""Contract tests for the Audit-only semantic model caller.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from src.audit_llm_secret_v1 import AUDIT_SECRET_MASTER_KEY_ENV, AuditLLMSecretStore
from src.audit_semantic_model_v1 import OPENAI_RESPONSES_URL, run_audit_semantic_candidate
from src.operations_console_v1 import ConsoleError


def _item(text: str = "Bespreek samen welke behandeling het beste past.") -> dict:
    return {
        "item_id": "item-1",
        "snapshot_id": "snap-1",
        "source_hash": "a" * 64,
        "source_locator": {"page": 1},
        "source_text": text,
    }


def _configure_secret(runtime: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    master_key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv(AUDIT_SECRET_MASTER_KEY_ENV, master_key)
    AuditLLMSecretStore(runtime).set_api_key("secret-test-key")


def _response(proposal: dict) -> dict:
    return {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(proposal),
                    }
                ],
            }
        ]
    }


def test_audit_model_call_reconstructs_candidate_only_from_selected_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_secret(tmp_path, monkeypatch)
    captured: dict = {}

    def fake_post(url: str, headers: dict, payload: dict, timeout: int) -> dict:
        captured.update(url=url, headers=headers, payload=payload, timeout=timeout)
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        return _response(
            {
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": block["block_id"],
                                "start": 0,
                                "end": len(block["text"]),
                            }
                        ],
                        "proposed_object_type": "recommendation",
                    }
                ],
                "abstain_reason": None,
            }
        )

    result = run_audit_semantic_candidate(
        tmp_path,
        item=_item(),
        model="test-model",
        post_json=fake_post,
    )

    assert captured["url"] == OPENAI_RESPONSES_URL
    assert captured["headers"]["Authorization"] == "Bearer secret-test-key"
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert result["candidate_units"][0]["clean_text"] == _item()["source_text"]
    assert result["candidate_units"][0]["semantic_passage"]["source_bound"] is True


def test_audit_model_call_can_abstain_without_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_secret(tmp_path, monkeypatch)

    result = run_audit_semantic_candidate(
        tmp_path,
        item=_item(),
        model="test-model",
        post_json=lambda *_args: _response(
            {"objects": [], "abstain_reason": "insufficient_context"}
        ),
    )

    assert result["candidate_units"] == []
    assert result["proposal"]["abstain_reason"] == "insufficient_context"


def test_model_authored_candidate_text_is_rejected_after_provider_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_secret(tmp_path, monkeypatch)

    def fake_post(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        return _response(
            {
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": block["block_id"],
                                "start": 0,
                                "end": len(block["text"]),
                            }
                        ],
                        "proposed_object_type": "recommendation",
                        "candidate_text": "Niet uit de bron.",
                    }
                ],
                "abstain_reason": None,
            }
        )

    with pytest.raises(ConsoleError) as error:
        run_audit_semantic_candidate(
            tmp_path,
            item=_item(),
            model="test-model",
            post_json=fake_post,
        )

    assert error.value.code == "audit_llm_proposal_rejected"


def test_provider_refusal_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_secret(tmp_path, monkeypatch)

    with pytest.raises(ConsoleError) as error:
        run_audit_semantic_candidate(
            tmp_path,
            item=_item(),
            model="test-model",
            post_json=lambda *_args: {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "refusal", "refusal": "cannot comply"}],
                    }
                ]
            },
        )

    assert error.value.code == "audit_llm_refused"


def test_invalid_provider_json_payload_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_secret(tmp_path, monkeypatch)

    with pytest.raises(ConsoleError) as error:
        run_audit_semantic_candidate(
            tmp_path,
            item=_item(),
            model="test-model",
            post_json=lambda *_args: {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "not-json"}],
                    }
                ]
            },
        )

    assert error.value.code == "audit_llm_response_invalid"


def test_missing_model_fails_before_secret_or_provider_access(tmp_path: Path) -> None:
    with pytest.raises(ConsoleError) as error:
        run_audit_semantic_candidate(tmp_path, item=_item(), model="")

    assert error.value.code == "audit_llm_model_required"
