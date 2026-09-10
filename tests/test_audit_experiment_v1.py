"""Evidence for the bounded Audit experiment dataset freeze."""
from __future__ import annotations

import json

import pytest

from src.audit_experiment_v1 import freeze_dataset, load_frozen_dataset
from src.operations_console_v1 import ConsoleError

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: slop
# release-control-evidence: releasebewijs


AUDIT_ID = "audit-0123456789abcdef"
BASELINE_COMMIT = "a" * 40
SOURCE_HASH = "b" * 64


def _items():
    return [
        {
            "item_id": "item-1",
            "snapshot_id": "snap-1",
            "source_hash": SOURCE_HASH,
            "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:4-5"},
            "source_text": "De werkgroep adviseert dit alleen toe te passen wanneer aan de voorwaarden is voldaan.",
        }
    ]


def test_freeze_persists_exact_reproducible_evidence(tmp_path):
    record = freeze_dataset(
        tmp_path,
        audit_id=AUDIT_ID,
        baseline_commit=BASELINE_COMMIT,
        items=_items(),
    )

    assert record["schema_version"] == 1
    assert record["audit_id"] == AUDIT_ID
    assert record["baseline_commit"] == BASELINE_COMMIT
    assert record["items"] == _items()
    assert record["frozen_at"].endswith("Z")
    assert load_frozen_dataset(tmp_path, AUDIT_ID) == record

    stored = json.loads(
        (tmp_path / "audit_experiments" / AUDIT_ID / "dataset.json").read_text(encoding="utf-8")
    )
    assert stored == record


def test_second_freeze_cannot_silently_replace_first_dataset(tmp_path):
    first = freeze_dataset(
        tmp_path,
        audit_id=AUDIT_ID,
        baseline_commit=BASELINE_COMMIT,
        items=_items(),
    )
    changed = _items()
    changed[0]["source_text"] = "Andere tekst."

    with pytest.raises(ConsoleError, match="experiment_dataset_already_frozen"):
        freeze_dataset(
            tmp_path,
            audit_id=AUDIT_ID,
            baseline_commit="c" * 40,
            items=changed,
        )

    assert load_frozen_dataset(tmp_path, AUDIT_ID) == first


def test_freeze_requires_valid_commit_hash_source_hash_locator_and_text(tmp_path):
    with pytest.raises(ConsoleError, match="experiment_baseline_commit_invalid"):
        freeze_dataset(tmp_path, audit_id=AUDIT_ID, baseline_commit="main", items=_items())

    bad_hash = _items()
    bad_hash[0]["source_hash"] = "not-a-hash"
    with pytest.raises(ConsoleError, match="experiment_dataset_source_hash_invalid"):
        freeze_dataset(tmp_path, audit_id=AUDIT_ID, baseline_commit=BASELINE_COMMIT, items=bad_hash)

    bad_locator = _items()
    bad_locator[0]["source_locator"] = {}
    with pytest.raises(ConsoleError, match="experiment_dataset_locator_invalid"):
        freeze_dataset(tmp_path, audit_id=AUDIT_ID, baseline_commit=BASELINE_COMMIT, items=bad_locator)

    bad_text = _items()
    bad_text[0]["source_text"] = ""
    with pytest.raises(ConsoleError, match="experiment_dataset_source_text_invalid"):
        freeze_dataset(tmp_path, audit_id=AUDIT_ID, baseline_commit=BASELINE_COMMIT, items=bad_text)


def test_dataset_items_must_have_unique_ids(tmp_path):
    items = _items() + _items()
    with pytest.raises(ConsoleError, match="experiment_dataset_duplicate_item"):
        freeze_dataset(tmp_path, audit_id=AUDIT_ID, baseline_commit=BASELINE_COMMIT, items=items)
