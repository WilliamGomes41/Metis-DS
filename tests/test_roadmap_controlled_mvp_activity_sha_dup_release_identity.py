"""ROADMAP pointer tests for the controlled-MVP backlog lock.

Locks the owner ask of 2026-09-06 (William Gomes / Metis CoS): three
small controlled-MVP items on ROADMAP only — (A) Review «Recent
activity» read-only sidebar, (B) exact SHA-256 duplicate ingest guard,
(C) release identity + GitHub→Azure deploy authorization.

This PR is ROADMAP + CHANGELOG + pointer tests only. No PROTOCOL.md
rewrite, no new PROTOCOL_V2_* delta, no src/ product code, no Forge
implementation. Die Forge-golf is nog NIET in code — await aparte
Metis GO. Markers here are CI metadata pointing at these text checks;
they are not live-release proof.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LOCK_HEADING = (
    "Eigenaarslock 2026-09-06 — Controlled-MVP Recent activity, "
    "SHA-256-dup-guard en release-identity (ROADMAP)"
)

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lock_section() -> str:
    roadmap = _read(ROOT / "ROADMAP.md")
    start = roadmap.index(LOCK_HEADING)
    rest = roadmap[start:]
    next_lock = rest.find("\n## ", 1)
    return rest if next_lock < 0 else rest[:next_lock]


def test_roadmap_records_controlled_mvp_owner_lock() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert LOCK_HEADING in roadmap
    assert "William Gomes" in _lock_section()
    assert "Metis CoS" in _lock_section()
    assert "2026-09-06" in _lock_section()
    assert "ROADMAP-lock" in _lock_section()
    assert "Geen productcode" in _lock_section() or "geen productcode" in _lock_section()
    assert "Die Forge-golf is nog NIET in code" in _lock_section()
    assert "aparte Metis GO" in _lock_section()
    assert "controlled-MVP" in changelog
    assert "Die Forge-golf is nog NIET in code" in changelog
    assert "await aparte Metis GO" in changelog


def test_roadmap_locks_item_a_recent_activity_readonly() -> None:
    section = _lock_section()
    changelog = _read(ROOT / "CHANGELOG.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    live = roadmap[roadmap.index("Wat nu de code stuurt:") : roadmap.index("### Historische supersessie-index")]
    assert "Item A" in section
    assert "Recent activity" in section
    assert "read-only" in section
    assert "document-scoped" in section or "alleen document-scoped" in section
    assert "newest first" in section.lower() or "nieuwste eerst" in section.lower()
    assert "append-only" in section
    assert "hash-chained" in section
    assert "event_type" in section
    assert "object_id" in section
    assert "object_version" in section
    assert "proposed correction" in section or "proposed_correction" in section
    assert "MUST NOT" in section and "presence" in section.lower()
    assert "Slack" in section
    assert "geen nieuw write-pad" in section.lower() or "no new write path" in section.lower()
    assert "Die Forge-golf is in code" in section
    assert "Item A" in section and "in code" in section
    item_a_live = next(line for line in live.splitlines() if "Recent activity" in line)
    assert "in code" in item_a_live
    assert "Recent activity" in changelog
    assert "presence" in changelog.lower()
    assert "test_review_recent_activity.py" in changelog


def test_roadmap_locks_item_b_exact_sha256_duplicate_guard() -> None:
    section = _lock_section()
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Item B" in section
    assert "SHA-256" in section
    assert "BLOCK" in section
    assert "snap-{digest[:16]}-{uuid}" in section
    assert "Open existing document" in section
    assert "title" in section.lower()
    assert "fuzzy" in section.lower()
    assert "OUT OF SCOPE" in section
    assert "single-writer" in section
    assert "Open existing document" in changelog
    assert "SHA-256" in changelog
    assert "fuzzy" in changelog.lower()


def test_roadmap_locks_item_c_release_identity_and_oidc() -> None:
    section = _lock_section()
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Item C" in section
    assert "No subscriptions found" in section
    assert "metis-deploy-production" in section
    assert "OIDC" in section
    assert "workflow_dispatch" in section
    assert "B2 is compute" in section
    assert "vvn-metis-console" in section
    assert "tested commit SHA" in section or "geteste commit SHA" in section
    assert "--clean true" in section
    assert "/home/data" in section
    assert "GO-with-constraints" in section
    assert "No subscriptions found" in changelog
    assert "metis-deploy-production" in changelog
    assert "B2 is compute" in changelog
    assert "workflow_dispatch" in changelog
    assert "--clean true" in changelog


def test_roadmap_states_out_of_scope_and_does_not_open_g2() -> None:
    section = _lock_section()
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "OUT OF SCOPE" in section
    assert "auto-deploy" in section.lower() or "auto main→Azure" in section
    assert "SKU" in section
    assert "MUST NOT G2/`publish()` openen" in section
    assert "HANDOFF.md MUST NOT" in section
    assert "geen golf 6" in section.lower()
    assert "MUST NOT open G2/`publish()`" in changelog or "NOT G2/`publish()`" in changelog
    assert "HANDOFF" in changelog
    assert "NOT Protocol" in changelog or "NOT PROTOCOL" in changelog


def test_controlled_mvp_pr_does_not_rewrite_protocol_or_add_src() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.32.0") == 1
    assert not (ROOT / "docs" / "PROTOCOL_V2_33_CONTROLLED_MVP_ACTIVITY_SHA_DUP_DELTA.md").exists()
    assert not (ROOT / "docs" / "PROTOCOL_V2_32_CONTROLLED_MVP_BACKLOG_DELTA.md").exists()
    src_hits = []
    needles = (
        "Controlled-MVP Recent activity",
        "SHA-256-dup-guard en release-identity",
        "Open existing document",
        "No subscriptions found",
    )
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(needle in text for needle in needles):
            src_hits.append(path.name)
    assert src_hits == [], f"docs-only PR must not add controlled-MVP product code in src/: {src_hits}"
    assert not (ROOT / "HANDOFF.md").exists()
