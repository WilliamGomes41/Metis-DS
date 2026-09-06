"""ROADMAP pointer tests for the post-#120 audit acceptance correction.

Locks the owner ask of 2026-09-06 (William Gomes / Metis CoS): after PR
#120 / tip ef8771a, reopen acceptance of existing reliability promises.
This is a ROADMAP acceptatiecorrectie — NOT Protocol v2.32, NOT wave 6,
NOT product code, NOT Forge GO. Markers here are CI metadata pointing
at these text checks; they are not live-release proof.

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


def test_roadmap_records_post_120_audit_acceptatiecorrectie() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Eigenaarslock 2026-09-06 — Post-#120 audit acceptatiecorrectie (ROADMAP)" in roadmap
    assert "Geen Protocol v2.32. Geen golf 6. Geen productcode in deze PR." in roadmap
    assert "ef8771a" in roadmap
    assert "019978b" in roadmap
    assert "CHANGES REQUIRED" in roadmap
    assert "acceptatiecorrectie" in roadmap
    assert "heropent/corrigeert acceptatie" in roadmap
    assert "ef8771a" in changelog
    assert "acceptance correction" in changelog
    assert "NOT Protocol v2.32" in changelog
    assert "NOT wave 6" in changelog


def test_roadmap_does_not_claim_waves_1_to_5_fully_cover_reliability() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "#113–#120" in roadmap
    assert "multiuser-betrouwbaarheid" in roadmap
    assert "onafhankelijke extractkwaliteit" in roadmap
    assert "niet volledig" in roadmap
    assert "do not claim multiuser reliability" in changelog
    assert "independent extract quality" in changelog


def test_roadmap_orders_audit_remediations_not_a_sixth_wave() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    heading = "Eigenaarslock 2026-09-06 — Post-#120 audit acceptatiecorrectie (ROADMAP)"
    lock = roadmap[roadmap.index(heading) :]
    next_lock = lock.find("\n## ", 1)
    section = lock if next_lock < 0 else lock[:next_lock]
    stale = section.index("Wave-1 stale / browserrevisie")
    failed = section.index("Failed-write process consistency")
    ssrf = section.index("Wave-3 SSRF connection bind")
    quality = section.index("Wave-4 quality claim incomplete")
    topology = section.index("Topology bound")
    assert stale < failed < ssrf < quality < topology
    assert "threading.local" in section
    assert "promote_class" in section
    assert "Gunicorn" in section
    assert "CONFIGURE" in section
    assert "EXTEND" in section
    assert "geen zesde implementatiegolf" in section
    assert "geen golf 6" in section.lower()
    assert "6. **" not in section
    assert "store consistency" in changelog or "store-consistentie" in roadmap
    assert "MUST NOT invent wave 6" in changelog or "NOT wave 6" in changelog


def test_roadmap_releasecheck_stays_outside_remediations() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Aparte releasecheck (blijft buiten de remediaties)" in roadmap
    assert "MUST NOT Azure ZIP autoriseren" in roadmap
    assert "MUST NOT G2/`publish()` openen" in roadmap
    assert "markers/comments MUST NOT als live-releasebewijs" in roadmap
    assert "buiten scope" in roadmap
    assert "Landing-page UX" in changelog or "Landing-page UX-voorkeur" in roadmap
    assert "MUST NOT authorize Azure ZIP" in changelog
    assert "MUST NOT open G2/`publish()`" in changelog


def test_acceptatiecorrectie_pr_does_not_rewrite_protocol_or_add_src() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.32.0") == 1
    assert not (ROOT / "docs" / "PROTOCOL_V2_32_RELIABILITY_EVIDENCE_BACKLOG_DELTA.md").exists()
    assert not (ROOT / "docs" / "PROTOCOL_V2_32_AUDIT_ACCEPTATIECORRECTIE_DELTA.md").exists()
    src_hits = []
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "Post-#120 audit acceptatiecorrectie" in text or "ef8771a" in text:
            src_hits.append(path.name)
    assert src_hits == [], f"docs-only PR must not add acceptatiecorrectie product code in src/: {src_hits}"
    assert not (ROOT / "HANDOFF.md").exists()
