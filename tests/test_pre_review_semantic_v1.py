"""Regression proof for source-bound semantic passage formation before Review.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.passage_register_v1 import passage_register_of
from src.pre_review_semantic_v1 import (
    DETERMINISTIC_MODE,
    OPENAI_RESPONSES_URL,
    PASSAGE_FORMATION_MODE_ENV,
    PRE_REVIEW_LLM_API_KEY_ENV,
    PRE_REVIEW_LLM_MODEL_ENV,
    SEMANTIC_MODE,
    bind_pre_review_semantic_processing,
    semantic_units_before_review,
)


def _fragment(fragment_id: str, text: str, *, object_type: str | None = None) -> dict:
    row = {
        "fragment_id": fragment_id,
        "fragment_hash": f"hash-{fragment_id}",
        "raw_text": text,
        "clean_text": text,
        "section_path": ["Behandeling"],
        "source_locator": {
            "locator_type": "web_line_range",
            "locator_value": "lines:1-1",
        },
    }
    if object_type:
        row["object_type"] = object_type
    return row


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


def test_semantic_processing_runs_before_review_and_reconstructs_source_only() -> None:
    fragments = [
        _fragment("h1", "Behandeling", object_type="heading"),
        _fragment("p1", "Bespreek samen welke behandeling het beste past."),
    ]
    captured: dict = {}

    def fake_post(url: str, headers: dict, payload: dict, timeout: int) -> dict:
        captured.update(url=url, headers=headers, payload=payload, timeout=timeout)
        return _response(_full_span_proposal(payload))

    units = semantic_units_before_review(
        fragments,
        document_id="doc-1",
        api_key="product-key",
        model="test-model",
        post_json=fake_post,
    )

    assert captured["url"] == OPENAI_RESPONSES_URL
    assert captured["headers"]["Authorization"] == "Bearer product-key"
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert [row["clean_text"] for row in units] == [
        "Behandeling",
        "Bespreek samen welke behandeling het beste past.",
    ]
    content = units[1]
    assert content["proposed_object_type"] == "recommendation"
    assert content["semantic_passage"]["source_bound"] is True
    assert content["source_fragment_ids"] == ["p1"]


def test_semantic_processing_preserves_interleaved_source_order() -> None:
    fragments = [
        _fragment("h1", "Diagnostiek", object_type="heading"),
        _fragment("p1", "Bespreek eerst de diagnostiek."),
        _fragment("h2", "Behandeling", object_type="heading"),
        _fragment("p2", "Bespreek daarna de behandeling."),
    ]

    def fake_post(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        return _response(_full_span_proposal(payload))

    units = semantic_units_before_review(
        fragments,
        document_id="doc-1",
        api_key="product-key",
        model="test-model",
        post_json=fake_post,
    )

    assert [row["clean_text"] for row in units] == [
        "Diagnostiek",
        "Bespreek eerst de diagnostiek.",
        "Behandeling",
        "Bespreek daarna de behandeling.",
    ]


def test_semantic_mode_rejects_model_authored_text_instead_of_falling_back() -> None:
    fragments = [_fragment("p1", "Bespreek samen de behandeling.")]

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
                        "candidate_text": "Vrije modeltekst mag niet doorstromen.",
                    }
                ],
                "abstain_reason": None,
            }
        )

    with pytest.raises(ConsoleError) as error:
        semantic_units_before_review(
            fragments,
            document_id="doc-1",
            api_key="product-key",
            model="test-model",
            post_json=fake_post,
        )

    assert error.value.code == "pre_review_llm_proposal_rejected"


def test_provider_failure_is_fail_closed_without_deterministic_fallback() -> None:
    def unavailable(*_args):
        raise ConsoleError("pre_review_llm_provider_unavailable")

    with pytest.raises(ConsoleError) as error:
        semantic_units_before_review(
            [_fragment("p1", "Bespreek samen de behandeling.")],
            document_id="doc-1",
            api_key="product-key",
            model="test-model",
            post_json=unavailable,
        )

    assert error.value.code == "pre_review_llm_provider_unavailable"


def test_semantic_abstention_is_fail_closed_before_review() -> None:
    def abstain(*_args):
        return _response(
            {
                "objects": [],
                "abstain_reason": "insufficient_semantic_context",
            }
        )

    with pytest.raises(ConsoleError) as error:
        semantic_units_before_review(
            [_fragment("p1", "Bespreek samen de behandeling.")],
            document_id="doc-1",
            api_key="product-key",
            model="test-model",
            post_json=abstain,
        )

    assert error.value.code == "pre_review_llm_abstained"


def test_runtime_policy_is_instance_bound_and_keeps_explicit_rollback_mode(tmp_path: Path) -> None:
    fragments = [_fragment("p1", "Bespreek samen de behandeling.")]
    env = {
        PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        PRE_REVIEW_LLM_API_KEY_ENV: "product-key",
        PRE_REVIEW_LLM_MODEL_ENV: "test-model",
    }

    def fake_post(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        return _response(_full_span_proposal(payload))

    semantic_console = OperationsConsole(
        root=tmp_path / "semantic",
        source_store=tmp_path / "semantic-sources",
        runtime=tmp_path / "semantic-runtime",
    )
    deterministic_console = OperationsConsole(
        root=tmp_path / "deterministic",
        source_store=tmp_path / "deterministic-sources",
        runtime=tmp_path / "deterministic-runtime",
    )
    semantic_console._extract = lambda *_args, **_kwargs: fragments
    deterministic_console._extract = lambda *_args, **_kwargs: fragments
    bind_pre_review_semantic_processing(
        semantic_console,
        environ=env,
        post_json=fake_post,
    )

    semantic_spec = semantic_console._fragments_and_spec(
        "html",
        tmp_path / "source.html",
        data=b"source",
        document_id="doc-1",
        source_id="src-1",
        title="Titel",
        family="kwaliteit",
        class_="richtlijn",
    )[1]
    untouched_spec = deterministic_console._fragments_and_spec(
        "html",
        tmp_path / "source.html",
        data=b"source",
        document_id="doc-2",
        source_id="src-2",
        title="Titel",
        family="kwaliteit",
        class_="richtlijn",
    )[1]

    assert semantic_spec["objects"][1]["semantic_passage"]["source_bound"] is True
    assert "semantic_passage" not in untouched_spec["objects"][1]

    env[PASSAGE_FORMATION_MODE_ENV] = DETERMINISTIC_MODE
    rollback_spec = semantic_console._fragments_and_spec(
        "html",
        tmp_path / "source.html",
        data=b"source",
        document_id="doc-3",
        source_id="src-3",
        title="Titel",
        family="kwaliteit",
        class_="richtlijn",
    )[1]
    assert "semantic_passage" not in rollback_spec["objects"][1]


def test_read_only_repair_catalog_does_not_call_llm(tmp_path: Path) -> None:
    fragments = [_fragment("p1", "Bespreek samen de behandeling.")]
    calls = 0

    class RepairCatalogConsole(OperationsConsole):
        def source_fragment_catalog(self) -> list[dict]:
            self._fragments_and_spec(
                "html",
                tmp_path / "source.html",
                data=b"source",
                document_id="doc-1",
                source_id="src-1",
                title="Titel",
                family="kwaliteit",
                class_="richtlijn",
            )
            return []

    def fake_post(*_args):
        nonlocal calls
        calls += 1
        raise AssertionError("read-only repair catalog must not call the LLM")

    console = RepairCatalogConsole(
        root=tmp_path / "repair",
        source_store=tmp_path / "repair-sources",
        runtime=tmp_path / "repair-runtime",
    )
    console._extract = lambda *_args, **_kwargs: fragments
    bind_pre_review_semantic_processing(
        console,
        environ={
            PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
            PRE_REVIEW_LLM_API_KEY_ENV: "product-key",
            PRE_REVIEW_LLM_MODEL_ENV: "test-model",
        },
        post_json=fake_post,
    )

    assert console.source_fragment_catalog() == []
    assert calls == 0


def test_omitted_semantic_source_passage_remains_open_after_ingest(tmp_path: Path) -> None:
    fragments = [
        _fragment("p1", "Gebruik behandeling X."),
        _fragment("p2", "Niet gebruiken bij patiënten met nierfalen."),
        _fragment("p3", "Controleer na vier weken."),
    ]

    def select_first_and_third(
        _url: str,
        _headers: dict,
        payload: dict,
        _timeout: int,
    ) -> dict:
        blocks = json.loads(payload["input"][1]["content"])["source_blocks"]
        return _response(
            {
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": blocks[0]["block_id"],
                                "start": 0,
                                "end": len(blocks[0]["text"]),
                            }
                        ],
                        "proposed_object_type": "recommendation",
                    },
                    {
                        "spans": [
                            {
                                "block_id": blocks[2]["block_id"],
                                "start": 0,
                                "end": len(blocks[2]["text"]),
                            }
                        ],
                        "proposed_object_type": "recommendation",
                    },
                ],
                "abstain_reason": None,
            }
        )

    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
    )
    researcher = console.create_account(
        username="researcher",
        password="researcher-secret",
        roles=("researcher",),
        display_name="Researcher",
    )
    reviewer = console.create_account(
        username="reviewer",
        password="reviewer-secret",
        roles=("reviewer",),
        display_name="Reviewer",
    )
    console._extract = lambda *_args, **_kwargs: fragments
    bind_pre_review_semantic_processing(
        console,
        environ={
            PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
            PRE_REVIEW_LLM_API_KEY_ENV: "product-key",
            PRE_REVIEW_LLM_MODEL_ENV: "test-model",
        },
        post_json=select_first_and_third,
    )

    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="coverage.html",
        data=b"<html><body>coverage</body></html>",
        content_type="text/html",
        ingest_kind="new",
        title="Coverage",
        version="1.0",
        date="2026-09-18",
        live_url="",
        class_="richtlijn",
        family="kwaliteit",
        named_reviewers=[reviewer["account_id"]],
    )

    omitted = next(
        row
        for row in console.snapshot_objects(receipt["snapshot_id"])
        if (row.get("content") or {}).get("clean_text")
        == "Niet gebruiken bij patiënten met nierfalen."
    )
    assert omitted["proposed_object_type"] == "unclassified"
    assert passage_register_of(omitted)["status"] == "not_yet_assessed"
