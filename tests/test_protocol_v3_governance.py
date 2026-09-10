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


def test_roadmap_records_v3_closeout_and_current_next_work() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    assert "## R3.1 Governance-migratie afronden\n\n**Status:** GEREED" in roadmap
    assert "## R3.2 Governance-tests migreren\n\n**Status:** GEREED" in roadmap
    assert "Besluit: `ACTIVATE V3` — uitgevoerd via PR #149." in roadmap
    assert "## R3.3 Audit-kamer + experimentbasis\n\n**Status:** IN UITVOERING" in roadmap
    assert "## R3.4 Eerste experiment: passagevorming\n\n**Status:** ARCHITECTUUR HERZIEN EN LOCKED" in roadmap
    assert "| Protocol v3 activeren | GEREED — PR #149 gemerged; Protocol v3.0.0 actief; CI groen |" in roadmap


def test_audit_room_passage_experiment_and_evidence_boundary_are_locked() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    for required in (
        "de Audit-kamer is generiek; onderliggende audits blijven expliciet en lokaal",
        "**Experiment** en een minimale read-only **Documentkwaliteit**-audit",
        "geen nieuwe accountrol `auditor`",
        "geen console-rewrite, nieuw frontendframework, microservicesplitsing of generieke `AuditEngine`",
        "Beide routes lopen na kandidaatvorming door dezelfde deterministische verificatie van harde invarianten.",
        "AI is uitsluitend een experimenteel instrument binnen de Audit-kamer",
        "de Kernel blijft AI-vrij",
        "het LLM mag uitsluitend exacte bronspans selecteren of combineren",
        "Metis reconstrueert een kandidaat zelf uit de aangewezen spans van de frozen bron",
        "**Blind beoordelen**",
        "A, B, gelijkwaardig of beide onvoldoende",
        "**Menselijke correctie vastleggen**",
        "**Verbetercollectie vullen**",
        "**READY FOR IMPLEMENTATION**",
        "Metis programmeert zichzelf niet",
        "GitHub blijft de bron van waarheid voor software",
        "een individueel voorbeeld leidt niet tot een softwarewijziging of PR",
        "gate-yield/coverage",
        "nul tolerantie voor onverifieerbare toevoegingen",
    ):
        assert required in roadmap
    assert "Geen generiek auditframework voordat meerdere echte auditvormen aantoonbaar dezelfde state en persistence delen." in roadmap
    assert "Geen AI/modelroute buiten Audit zolang geen afzonderlijk architectuurbesluit dat expliciet wijzigt." in roadmap
    assert "Geen individuele fout of correctie die automatisch een softwarewijziging, branch of PR veroorzaakt." in roadmap
    assert "Geen `READY FOR IMPLEMENTATION` als impliciete autorisatie voor codewijziging, GitHub-write, merge, deploy of publicatie." in roadmap
    assert "Geen downstream-capability als werkend beschrijven zolang geen echte technische executor bestaat." in roadmap
    assert "| Audit-kamer als brede inspectiekamer | LOCKED — 2026-09-10 |" in roadmap
    assert "| Passagevormingsexperiment | LOCKED — frozen dataset, blind A/B, menselijke correctie en verbetercollectie |" in roadmap
    assert "| Audit → READY FOR IMPLEMENTATION | LOCKED — hier eindigt Metis; ontwikkeling gebeurt buiten Metis |" in roadmap
    assert "| Metis programmeert zichzelf / automatische APPLY → GitHub | AFGEWEZEN" in roadmap


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
