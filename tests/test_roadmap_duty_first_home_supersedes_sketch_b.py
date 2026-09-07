"""ROADMAP pointer tests for the duty-first home lock.

Locks the owner ask of 2026-09-07 (William Gomes / Metis CoS): logged-in
`/` MUST be duty-first (Metis Design mock). PR #127 sketch B sparse
one-CTA home is SUPERSEDED as the locked home. Die Forge-golf is in
code (duty-first home). Historical lock paragraphs keep the original
«nog NIET in code» ROADMAP-only sentence.

No PROTOCOL.md rewrite, no new PROTOCOL_V2_* delta. Markers here are
CI metadata pointing at these text checks; they are not live-release
proof.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LOCK_HEADING = (
    "Eigenaarslock 2026-09-07 — Duty-first home SUPERSEDEERT sketch B (ROADMAP)"
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


def test_roadmap_records_duty_first_home_owner_lock() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert LOCK_HEADING in roadmap
    assert "William Gomes" in _lock_section()
    assert "Metis CoS" in _lock_section()
    assert "2026-09-07" in _lock_section()
    assert "ROADMAP-lock" in _lock_section()
    assert "Geen productcode" in _lock_section() or "geen productcode" in _lock_section()
    assert "Die Forge-golf is nog NIET in code" in _lock_section()
    assert "Die Forge-golf is in code" in _lock_section()
    assert "aparte Metis GO" in _lock_section()
    assert "duty-first" in changelog.lower() or "Duty-first" in changelog
    assert "Die Forge-golf is nog NIET in code" in changelog
    assert "Metis workboard" in changelog
    assert "await aparte Metis GO" in changelog
    assert "duty-first home ROADMAP 2026-09-07" in roadmap


def test_roadmap_supersedes_sketch_b_as_locked_home() -> None:
    section = _lock_section()
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    live = roadmap[roadmap.index("Wat nu de code stuurt:") : roadmap.index("### Historische supersessie-index")]
    assert "SUPERSEDES sketch B" in section or "superseded" in section.lower()
    assert "#127" in section
    assert "sketch B" in section
    assert "Bron inleveren" in section
    assert "superseded" in live.lower()
    assert "#127" in live
    assert "landing sketch b" in live.lower()
    assert "Bron inleveren" in live
    duty_live = next(
        line for line in live.splitlines() if "duty-first" in line.lower() or "sketch B" in line
    )
    assert "vier grote klikbare tegels" in duty_live
    assert "supersedes #127 sketch B" in changelog
    assert "sketch B" in changelog


def test_roadmap_locks_duty_first_home_copy_and_cards() -> None:
    section = _lock_section()
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Mijn werk" in section
    assert "Kies de volgende stap in het proces." in section
    assert "Inleveren → Review → Publiceren → Documenten" in section
    assert "Vier grote, horizontale" in section
    assert "N wachten op jou" in section
    assert "Nu doen" in section
    assert "/review" in section
    assert "Nieuwe bron toevoegen" in section
    assert "/ingest" in section
    assert "Goedgekeurde stukken publiceren" in section
    assert "/publish" in section
    assert "Zoeken, openen of beheren" in section
    assert "/tree" in section
    assert "Mijn werk" in section
    assert "MUST NOT" in section and "Inleveren" in section
    assert "Mijn werk" in changelog
    assert "Inleveren → Review → Publiceren → Documenten" in changelog
    assert "four large clickable tiles" in changelog


def test_roadmap_locks_post_auth_home_and_documenten_unchanged() -> None:
    section = _lock_section()
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    live = roadmap[roadmap.index("Wat nu de code stuurt:") : roadmap.index("### Historische supersessie-index")]
    assert "Post-auth" in section or "post-auth" in section.lower()
    assert "niet `/ingest`" in section or "niet /ingest" in section
    assert "Documenten" in section
    assert "UNCHANGED" in section
    assert "v2.32" in section
    assert "Post-auth landt op `/`" in live or "post-auth" in live.lower()
    assert "Documenten" in live
    assert "v2.32" in live
    assert "Documenten" in changelog
    assert "v2.32" in changelog
    assert "not `/ingest`" in changelog or "niet `/ingest`" in changelog


def test_roadmap_states_out_of_scope_and_does_not_open_g2() -> None:
    section = _lock_section()
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "OUT OF SCOPE" in section
    assert "Slack" in section
    assert "quiet-only" in section.lower() or "Quiet-only" in section
    assert "MUST NOT G2/`publish()` openen" in section
    assert "HANDOFF.md MUST NOT" in section
    assert "geen golf 6" in section.lower()
    assert "NOT G2/`publish()`" in changelog
    assert "NOT Protocol" in changelog or "NOT PROTOCOL" in changelog


def test_duty_first_does_not_rewrite_protocol_and_is_in_console() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.32.0") == 1
    assert not (ROOT / "docs" / "PROTOCOL_V2_33_DUTY_FIRST_HOME_DELTA.md").exists()
    assert not (ROOT / "docs" / "PROTOCOL_V2_32_DUTY_FIRST_HOME_DELTA.md").exists()
    src = _read(ROOT / "src" / "operations_console_app.py")
    assert "Mijn werk" in src
    assert "Kies de volgende stap in het proces." in src
    assert "home-tile" in src
    assert 'href="/publish"' in src
    assert not (ROOT / "HANDOFF.md").exists()
