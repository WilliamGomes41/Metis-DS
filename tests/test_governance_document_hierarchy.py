from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_governance_documents_exist() -> None:
    required = (
        "PROTOCOL.md",
        "ROADMAP.md",
        "docs/DEVELOPMENT_WORKFLOW.md",
        "docs/PROTOCOL_V2_2.md",
        "docs/GOVERNANCE.md",
        "data/assurance/gd_03_c3_c6_reviewer_matrix.json",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert not missing, f"missing governance documents: {missing}"


def test_protocol_has_one_versioned_norm_and_required_hierarchy() -> None:
    protocol = _read("PROTOCOL.md")
    assert protocol.count("De geldende normatieve baseline is Protocol v2.13.0") == 1
    assert "plus Protocol v2.12.0" in protocol
    assert "plus Protocol v2.11.0" in protocol
    assert "De geldende normatieve baseline is Protocol v2.12.0" not in protocol
    assert "De geldende normatieve baseline is Protocol v2.11.0" not in protocol
    assert protocol.count("docs/PROTOCOL_V2_2.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_9_CONSOLE_UX_BRAND_DELTA.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_10_CONSOLE_NAV_ACCOUNTS_DELTA.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_11_HTML_FREEZE_LOCATOR_DELTA.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_12_OBJECT_TYPE_REVIEW_PROJECTION_DELTA.md") == 1
    assert protocol.count("docs/PROTOCOL_V2_13_ATOMIC_OBJECT_SEMANTICS_DELTA.md") == 1
    assert "PROTOCOL.md → ROADMAP.md → acceptatietests → code" in protocol
    assert "probleem of failure → protocoltoets" in protocol


def test_roadmap_has_operational_controls() -> None:
    roadmap = _read("ROADMAP.md")

    for required in ("Stopvoorwaarde", "Holdout A", "FAR = 0%", "Azure DEV"):
        assert required in roadmap


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
