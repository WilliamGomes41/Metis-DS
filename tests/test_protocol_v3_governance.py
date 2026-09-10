from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "PROTOCOL.md"
ROADMAP = ROOT / "ROADMAP.md"
V2_PROTOCOL_SNAPSHOT = ROOT / "docs" / "history" / "protocol-v2" / "PROTOCOL_ROOT_FINAL_2026-09-10.md"
V2_ROADMAP_SNAPSHOT = ROOT / "docs" / "history" / "protocol-v2" / "ROADMAP_PRE_V3_2026-09-10.md"
V2_GOVERNANCE_SNAPSHOT = ROOT / "docs" / "history" / "protocol-v2" / "GOVERNANCE_PRE_V3_2026-09-10.md"

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs


def test_v3_is_the_single_current_norm() -> None:
    protocol = PROTOCOL.read_text(encoding="utf-8")
    assert "# V&VN Data Services — Protocol v3" in protocol
    assert "**Versie:** 3.0.0" in protocol
    assert "`PROTOCOL.md → ROADMAP.md → acceptatietests → code`" in protocol
    assert "## 16. Protocol V2 is historie" in protocol
    assert "De geldende normatieve baseline is Protocol v2." not in protocol
    assert "docs/PROTOCOL_V3_CANDIDATE.md" not in protocol


def test_v3_keeps_hard_publication_and_review_invariants() -> None:
    protocol = PROTOCOL.read_text(encoding="utf-8")
    for required in (
        "selected_as_candidate",
        "used_as_context",
        "linked_as_support",
        "excluded_with_reason",
        "not_yet_assessed",
        "exacte objectidentiteit",
        "Four-eyes",
        "G2-publicatie is conditioneel beschikbaar **per snapshot**",
        "SHA-256 van de gezaghebbende bronbytes",
        "Een app-setting",
        "fail-closed teruggerold",
    ):
        assert required in protocol


def test_roadmap_only_contains_active_v3_work() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    assert roadmap.startswith("# Metis — Roadmap v3")
    for work_item in ("R3.1", "R3.2", "R3.3", "R3.4", "R3.7"):
        assert work_item in roadmap
    assert "Historische supersessie-index" not in roadmap
    assert "Eigenaarslock 2026-" not in roadmap
    assert "Geen keten van Protocol-v3-delta's" in roadmap


def test_roadmap_records_v3_closeout_and_next_work() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    assert "## R3.1 Governance-migratie afronden\n\n**Status:** GEREED" in roadmap
    assert "## R3.2 Governance-tests migreren\n\n**Status:** GEREED" in roadmap
    assert "Besluit: `ACTIVATE V3` — uitgevoerd via PR #149." in roadmap
    assert "## R3.3 Audit > Experiments\n\n**Status:** VOLGEND." in roadmap
    assert "| Protocol v3 activeren | GEREED — PR #149 gemerged; Protocol v3.0.0 actief; CI groen |" in roadmap
    assert "| Audit > Experiments bouwen | VOLGEND |" in roadmap


def test_v2_root_state_is_preserved_as_history() -> None:
    assert V2_PROTOCOL_SNAPSHOT.is_file()
    assert V2_ROADMAP_SNAPSHOT.is_file()
    assert V2_GOVERNANCE_SNAPSHOT.is_file()
    old_protocol = V2_PROTOCOL_SNAPSHOT.read_text(encoding="utf-8")
    old_roadmap = V2_ROADMAP_SNAPSHOT.read_text(encoding="utf-8")
    assert "Protocol v2.34.0" in old_protocol
    assert "Protocol v2.33.0" in old_protocol
    assert "Historische supersessie-index" in old_roadmap


def test_no_handoff_or_extra_root_steering_layer_is_introduced() -> None:
    assert not (ROOT / "HANDOFF.md").exists()
    assert not (ROOT / "docs" / "PROTOCOL_V3_CANDIDATE.md").exists()
    assert not (ROOT / "docs" / "ROADMAP_V3_CANDIDATE.md").exists()
    root_markdown = {path.name for path in ROOT.glob("*.md")}
    assert "PROTOCOL_V3.md" not in root_markdown
    assert "ROADMAP_V3.md" not in root_markdown
