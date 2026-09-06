"""ROADMAP pointer tests for the post-v2.31 reliability & evidence backlog.

Locks the owner ask of 2026-09-06 (William / Metis CoS): ordered ROADMAP
waves after Protocol v2.31 / Forge exact-bind on main tip 019978b.
This PR is ROADMAP + CHANGELOG only. No PROTOCOL.md rewrite, no new
PROTOCOL_V2_* delta, no src/ product code, no Forge implementation.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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


def test_roadmap_only_pr_does_not_rewrite_protocol_or_add_src_product_code() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.31.0") == 1
    assert not (ROOT / "docs" / "PROTOCOL_V2_32_RELIABILITY_EVIDENCE_BACKLOG_DELTA.md").exists()
    src_hits = []
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "post-v2.31 betrouwbaarheid" in text or "019978b" in text:
            src_hits.append(path.name)
    assert src_hits == [], f"ROADMAP-only PR must not add reliability-wave product code in src/: {src_hits}"
