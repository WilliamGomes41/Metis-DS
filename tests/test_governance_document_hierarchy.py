from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_governance_documents_exist() -> None:
    required = (
        "PROTOCOL.md",
        "ROADMAP.md",
        "docs/DEVELOPMENT_WORKFLOW.md",
        "docs/GOVERNANCE.md",
        "docs/history/protocol-v2/PROTOCOL_ROOT_FINAL_2026-09-10.md",
        "docs/history/protocol-v2/ROADMAP_PRE_V3_2026-09-10.md",
        "data/assurance/gd_03_c3_c6_reviewer_matrix.json",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert not missing, f"missing governance documents: {missing}"


def test_protocol_has_one_current_v3_norm_and_required_hierarchy() -> None:
    protocol = _read("PROTOCOL.md")
    assert protocol.count("# V&VN Data Services — Protocol v3") == 1
    assert protocol.count("**Versie:** 3.0.0") == 1
    assert "PROTOCOL.md → ROADMAP.md → acceptatietests → code" in protocol
    assert "De geldende normatieve baseline is Protocol v2." not in protocol
    assert "## 16. Protocol V2 is historie" in protocol
    assert "Om te bepalen wat Metis nu moet doen, hoeft de V2-deltaketen niet meer te worden gelezen." in protocol


def test_v2_chain_is_preserved_in_history_not_current_protocol() -> None:
    protocol = _read("PROTOCOL.md")
    historical_protocol = _read("docs/history/protocol-v2/PROTOCOL_ROOT_FINAL_2026-09-10.md")

    assert "docs/PROTOCOL_V2_34" not in protocol
    assert "Protocol v2.34.0" in historical_protocol
    assert "Protocol v2.33.0" in historical_protocol
    assert "docs/PROTOCOL_V2_2.md" in historical_protocol


def test_roadmap_has_only_active_v3_controls() -> None:
    roadmap = _read("ROADMAP.md")

    assert roadmap.startswith("# Metis — Roadmap v3")
    for required in ("R3.1", "R3.2", "R3.3", "R3.4", "R3.7", "## Stopregels"):
        assert required in roadmap
    assert "Historische supersessie-index" not in roadmap
    assert "Eigenaarslock 2026-" not in roadmap


def test_operational_governance_record_is_subordinate_not_a_fifth_layer() -> None:
    governance = _read("docs/GOVERNANCE.md")
    protocol = _read("PROTOCOL.md")
    assert "geen vijfde stuurlaag" in governance
    assert "PROTOCOL.md → ROADMAP.md → acceptatietests → code" in governance
    assert "PROTOCOL.md → ROADMAP.md → acceptatietests → code" in protocol


def test_workflow_requires_tests_before_code_and_main_as_progress_record() -> None:
    workflow = _read("docs/DEVELOPMENT_WORKFLOW.md")
    tests_step = workflow.index("Leg vóór implementatie")
    code_step = workflow.index("Implementeer de kleinste wijziging")
    validation_step = workflow.index("Voer repository-preflight")
    progress_step = workflow.index("voortgangsbewijs op `main`")
    assert tests_step < code_step < validation_step < progress_step


def test_repository_root_is_operating_surface_not_historical_reports() -> None:
    operating = {
        "PROTOCOL.md",
        "ROADMAP.md",
        "README.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "SECURITY.md",
    }
    root_mds = {path.name for path in ROOT.glob("*.md")}
    missing = sorted(operating - root_mds)
    assert not missing, f"missing operating-surface documents at repository root: {missing}"

    clutter = sorted(
        name
        for name in root_mds
        if name.startswith("STEP") or name.endswith("_REPORT.md") or "AUDIT" in name
    )
    assert not clutter, f"historical reports belong under docs/history/: {clutter}"

    history_readme = _read("docs/history/README.md")
    assert "not steering documents" in history_readme.lower()
    assert "PROTOCOL.md → ROADMAP.md → acceptatietests → code" in history_readme
    assert "docs/history/" in _read("docs/REPOSITORY_CONVENTIONS.md")
    assert (ROOT / "docs/history/STEP2_README.md").is_file()
    assert (ROOT / "docs/history/FULL_TECHNICAL_AUDIT_2026-08-19.md").is_file()
