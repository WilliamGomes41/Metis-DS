"""ROADMAP pointer tests for the post-v2.31 reliability & evidence backlog.

Locks the owner ask of 2026-09-06 (William / Metis CoS): ordered ROADMAP
waves after Protocol v2.31 / Forge exact-bind on main tip 019978b, plus
the same-day sharpened acceptance on those five waves (no sixth wave).
This PR is ROADMAP + CHANGELOG only. No PROTOCOL.md rewrite, no new
PROTOCOL_V2_* delta, no src/ product code, no Forge implementation.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_roadmap_records_audit_tip_019978b_and_verdict() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "019978b" in roadmap
    assert "fundament aanwezig" in roadmap
    assert "geen brede betrouwbaarheids- of extractkwaliteitsclaim" in roadmap
    assert "begeleid intern gebruik" in roadmap
    assert "019978b" in changelog
    assert "guided internal use" in changelog or "begeleid intern" in changelog


def test_roadmap_publish_g2_blocked_remains_intentional() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "intentioneel, geen bug" in roadmap
    assert "`publish()` blijft G2-BLOCKED" in roadmap
    assert "G2 blijft BLOCKED" in roadmap
    assert "intentional, not a bug" in changelog
    assert "G2-BLOCKED" in changelog


def test_roadmap_next_code_is_ordered_reliability_waves_after_separate_go() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Reviewopslag betrouwbaarheid" in roadmap
    assert "Ingest beschikbaarheid" in roadmap
    assert "Security harden" in roadmap
    assert "Onafhankelijke kwaliteitsmeting (was PR2)" in roadmap
    assert "Gericht vereenvoudigen" in roadmap
    assert "atomic read-modify-write" in roadmap
    assert "torn JSONL" in roadmap
    assert "async event loop" in roadmap
    assert "SSRF" in roadmap
    assert "extract_metrics_v1" in roadmap
    assert "false positives" in roadmap
    assert "context_scan_done" in roadmap
    assert "context_completeness" in roadmap
    assert "onafhankelijk/representatief goud" in roadmap
    assert "geen volledige herschrijving" in roadmap
    review = roadmap.index("Reviewopslag betrouwbaarheid")
    ingest = roadmap.index("Ingest beschikbaarheid")
    security = roadmap.index("Security harden")
    quality = roadmap.index("Onafhankelijke kwaliteitsmeting (was PR2)")
    simplify = roadmap.index("Gericht vereenvoudigen")
    assert review < ingest < security < quality < simplify
    assert "aparte Metis GO per golf" in roadmap
    assert "start golf 1" in roadmap
    assert "Reviewopslag betrouwbaarheid" in changelog
    assert "extract_metrics_v1" in changelog
    assert "start wave 1" in changelog or "start golf 1" in changelog


def test_roadmap_waves_are_backlog_not_protocol_law_and_not_this_pr() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "ROADMAP-backlog" in roadmap
    assert "geen nieuwe PROTOCOL-wet" in roadmap
    assert "MUST NOT G2/`publish()` openen" in roadmap
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in roadmap
    assert "MUST NOT extractkwaliteit claimen uit groene CI of Phase-4 fixture-goud" in roadmap
    assert "Fase-4 hooks ≠ dit bewijs" in roadmap or "Phase-4 hooks ≠ dit bewijs" in roadmap
    assert "Auditor blijft aparte judge-seat" in roadmap
    assert "Forge MUST NOT self-certify" in roadmap
    assert "MUST NOT implementeren in deze PR" in roadmap
    assert "not new PROTOCOL law" in changelog
    assert "MUST NOT open G2/`publish()`" in changelog
    assert "MUST NOT recreate HANDOFF.md" in changelog
    assert "MUST NOT claim extract quality from green CI or Phase 4 fixture gold" in changelog
    assert "Forge must not self-certify" in changelog
    assert not (ROOT / "HANDOFF.md").exists()


def test_roadmap_sharpens_existing_five_waves_without_inventing_a_sixth() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "verscherpte acceptatiecriteria op dezelfde vijf golven" in roadmap
    assert "geen nieuwe golven" in roadmap
    assert "Aparte releasecheck (buiten de vijf golven)" in roadmap
    assert "Herleidbare release en herstel" in roadmap
    assert "echte gebruikershandeling" in roadmap
    assert "MUST NOT Azure ZIP autoriseren" in roadmap
    assert "scripts/release_control_preflight.py" in roadmap
    assert "geen zesde implementatiegolf" in roadmap
    assert "Per-golf afsluiting" in roadmap
    assert "concreet testbewijs" in roadmap
    assert "claim geen incident-proof zonder tests" in roadmap
    assert "geen succesmelding" in roadmap
    assert "Fail-closed op store alleen is onvoldoende" in roadmap
    assert "nog niet in UI bewezen" in roadmap
    assert "4d569f3" in roadmap
    assert "PR #113" in roadmap
    assert "9436e99" in roadmap
    assert "PR #115" in roadmap
    assert "gelijktijdig inloggen/uitloggen MUST NOT sessiegegevens verliezen" in roadmap
    assert "verlopen sessies MUST ongeldig blijven na herstart" in roadmap
    assert "taalvariatie" in roadmap
    assert "onterecht toegelaten" in roadmap
    assert "MUST NOT een zesde implementatiegolf verzinnen" in roadmap
    assert "NO new waves" in changelog
    assert "not a sixth implementation wave" in changelog
    assert "MUST NOT invent wave 6" in changelog
    assert "golf 6" not in roadmap.lower() or "geen golf 6" in roadmap
    wave_6_as_backlog = "6. **" in roadmap[roadmap.index("Geordende volgende implementatiegolven") : roadmap.index("**Aparte releasecheck")]
    assert not wave_6_as_backlog


def test_roadmap_only_pr_does_not_rewrite_protocol_or_add_src_product_code() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.32.0") == 1
    assert not (ROOT / "docs" / "PROTOCOL_V2_32_RELIABILITY_EVIDENCE_BACKLOG_DELTA.md").exists()
    src_hits = []
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "post-v2.31 betrouwbaarheid" in text or "019978b" in text:
            src_hits.append(path.name)
    assert src_hits == [], f"ROADMAP-only PR must not add reliability-wave product code in src/: {src_hits}"
