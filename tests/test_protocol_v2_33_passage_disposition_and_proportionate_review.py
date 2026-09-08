from __future__ import annotations

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_33_PASSAGE_DISPOSITION_AND_PROPORTIONATE_REVIEW_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_33_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v233_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.33.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_33_PASSAGE_DISPOSITION_AND_PROPORTIONATE_REVIEW_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-08"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v233_is_bounded_review_delta() -> None:
    delta = _read(DELTA)
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.33.0" in delta
    assert "**Extends:** Protocol v2.32.0" in delta
    assert "C3 canonical/review" in delta
    assert "bounded supersession of Protocol v2.19 and Protocol v2.30" in delta
    assert "does NOT reopen C5 publication/security" in delta


def test_v233_admission_failure_is_not_substantive_exclusion() -> None:
    delta = _read(DELTA)
    assert "`admission blocked != excluded_with_reason`" in delta
    assert "MUST NOT automatically become `excluded_with_reason`" in delta
    assert "admission reason codes MUST remain available" in delta
    assert "blocked candidate MUST still NOT be published or served" in delta


def test_v233_every_substantive_passage_has_a_disposition_route() -> None:
    delta = _read(DELTA)
    assert "Every substantive passage MUST eventually have exactly one applicable disposition" in delta
    for status in (
        "selected_as_candidate",
        "used_as_context",
        "linked_as_support",
        "excluded_with_reason",
        "not_yet_assessed",
    ):
        assert status in delta
    assert "MUST NOT be treated as a completed terminal disposition" in delta
    assert "MUST NOT silently drop substantive source content" in delta


def test_v233_human_review_is_object_level_but_interaction_may_be_batch_level() -> None:
    delta = _read(DELTA)
    assert "Every knowledge object that can become part of the usable knowledge layer MUST receive at least one human review" in delta
    assert "review completeness** is object-level and auditable" in delta
    assert "reviewer interaction** MAY be batch-level" in delta
    assert "MUST NOT require one separate click/open/save cycle for every normal-risk knowledge object" in delta
    assert "A batch action MUST write an individual review result for every included object" in delta
    assert "exact reviewed hash/version" in delta
    assert "MUST NOT convert one review decision into an untraceable envelope-level approval" in delta


def test_v233_keeps_no_2000_click_rule_and_four_eyes() -> None:
    delta = _read(DELTA)
    assert "MUST NOT be required to open 2,000 or 4,000 equal Inhoud cards one by one" in delta
    assert "high-risk four-eyes" in delta
    assert "Existing high-risk logic determines whether an independent second review is also required" in delta
    assert "requires_second_review" in delta
    assert "first review plus independent second review" in delta


def test_v233_does_not_add_duplicate_review_policy_state() -> None:
    delta = _read(DELTA)
    assert "MUST NOT add persistent `light`, `standard` or `strict` review levels" in delta
    assert "MUST NOT add a duplicate `use_scope` truth" in delta
    assert "MUST reuse the existing first review plus `requires_second_review`" in delta
    assert "MUST NOT create a researcher-facing `zwaar/licht`, `snel/langzaam`, `light/standard/strict`" in delta


def test_v233_keeps_publication_fail_closed() -> None:
    delta = _read(DELTA)
    assert "G2 remains BLOCKED" in delta
    assert "`publish()` remains G2-BLOCKED" in delta
    assert "Unreviewed, admission-blocked, rejected, conflicted or merely batch-presented content MUST NOT be served" in delta
    assert "MUST NOT be cited as G2 PASS" in delta


def test_v233_protocol_pr_separates_protocol_from_later_product_implementation() -> None:
    delta = _read(DELTA)
    assert "This protocol delta itself MUST NOT implement code." in delta
    assert "After a separate Metis GO" in delta
    assert "add a regular batch-review route" in delta
