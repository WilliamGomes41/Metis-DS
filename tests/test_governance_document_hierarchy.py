from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_governance_documents_exist() -> None:
    required = (
        "PROTOCOL.md",
        "ROADMAP.md",
        "HANDOFF.md",
        "docs/DEVELOPMENT_WORKFLOW.md",
        "docs/PROTOCOL_V2_2.md",
        "docs/GOVERNANCE.md",
        "data/assurance/gd_03_c3_c6_reviewer_matrix.json",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert not missing, f"missing governance documents: {missing}"


def test_protocol_has_one_versioned_norm_and_required_hierarchy() -> None:
    protocol = _read("PROTOCOL.md")
    assert protocol.count("docs/PROTOCOL_V2_2.md") == 1
    assert "PROTOCOL.md → ROADMAP.md → HANDOFF.md → acceptatietests → code" in protocol
    assert "probleem of failure → protocoltoets" in protocol


def test_roadmap_and_handoff_have_operational_controls() -> None:
    roadmap = _read("ROADMAP.md")
    handoff = _read("HANDOFF.md")

    for required in ("Stopvoorwaarde", "Holdout A", "FAR = 0%", "Azure DEV"):
        assert required in roadmap

    for required in (
        "Bijgewerkt:",
        "Geldend protocol:",
        "Authoritative remote:",
        "Open governancepunt",
        "Eerstvolgende taak",
        "BLOCKED",
    ):
        assert required in handoff


def test_operational_governance_record_is_subordinate_not_a_fifth_layer() -> None:
    governance = _read("docs/GOVERNANCE.md")
    protocol = _read("PROTOCOL.md")
    assert "geen vijfde stuurlaag" in governance
    assert "PROTOCOL.md → ROADMAP.md → HANDOFF.md → acceptatietests → code" in governance
    assert "PROTOCOL.md → ROADMAP.md → HANDOFF.md → acceptatietests → code" in protocol
    assert "docs/GOVERNANCE.md" in _read("HANDOFF.md")


def test_workflow_requires_tests_before_code_and_handoff_after_validation() -> None:
    workflow = _read("docs/DEVELOPMENT_WORKFLOW.md")
    tests_step = workflow.index("Leg vóór implementatie")
    code_step = workflow.index("Implementeer de kleinste wijziging")
    validation_step = workflow.index("Voer repository-preflight")
    final_handoff_step = workflow.index("Werk in dezelfde PR de handoff bij")
    assert tests_step < code_step < validation_step < final_handoff_step

