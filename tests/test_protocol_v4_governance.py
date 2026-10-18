"""Current governance boundaries; old V3 wording is preserved as an archive snapshot.

Storage concurrency and stale-write behavior remain covered by
`test_workflow_postgres_concurrency.py` and `test_stale_write_ux.py`.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_v4_is_current_and_v3_is_frozen() -> None:
    current, old = read("PROTOCOL.md"), read("docs/history/protocol-v3/PROTOCOL.md")
    assert current.startswith("# V&VN Data Services — Protocol v4")
    assert "**Versie:** 4.1.0" in current
    assert old.startswith("# V&VN Data Services — Protocol v3")
    assert "**Versie:** 3.0.0" in old
    assert read("ROADMAP.md").startswith("# Metis — Roadmap v4")
    assert read("docs/history/protocol-v3/ROADMAP.md").startswith("# Metis — Roadmap v3")
    assert "Protocol v4.1.0" in read("docs/GOVERNANCE.md")

def test_v4_retains_safety_and_describes_actual_modes() -> None:
    protocol = read("PROTOCOL.md")
    for required in (
        "selected_as_candidate", "exacte objectidentiteit", "Four-eyes",
        "G2-publicatie is conditioneel beschikbaar **per snapshot**",
        "SHA-256 van de gezaghebbende bronbytes", "gezaghebbende commit",
        "publication_registry", "METIS_CONSOLE_AUTH=entra",
        "Twee workers op diezelfde instance",
        "brongebonden semantische route", "geen stille terugval",
        "afgeleide, rebuildable projectie", "READY FOR IMPLEMENTATION",
    ):
        assert required in protocol

def test_new_release_records_current_protocol() -> None:
    from src.operations_console_v1 import PUBLICATION_PROTOCOL_VERSION
    assert PUBLICATION_PROTOCOL_VERSION == "4.1.0"


def test_documented_formation_roles_match_existing_policy() -> None:
    from src.candidate_eligibility_v1 import assess_candidate_eligibility
    from src.passage_formation_policy_v1 import resolve_passage_formation_strategy
    from src.pre_review_semantic_v1 import _configured_passage_formation_mode

    protocol = read("PROTOCOL.md")
    mode = _configured_passage_formation_mode({})
    assert mode == "semantic-source-bound-v2"
    assert f"`{mode}` (source-bound-fields v2) de standaardroute" in protocol
    for explicit_mode in (
        "semantic-source-bound-v1", "semantic-source-bound-v3", "deterministic-v1",
    ):
        assert f"`{explicit_mode}`" in protocol
    assert resolve_passage_formation_strategy(
        content_kind="html", deployment_mode=mode,
    ).strategy == "semantic"
    assert resolve_passage_formation_strategy(
        content_kind="boom", deployment_mode=mode,
    ).strategy == "deterministic"
    assert not assess_candidate_eligibility({
        "proposed_object_type": "recommendation",
        "text": "Bespreek de behandeling met de patiënt.",
    }).eligible
    assert "Een deterministisch typelabel vormt op zichzelf geen toegelaten kenniskandidaat" in protocol
    assert "Een geslaagde controle bewijst geen semantische of klinische volledigheid" in protocol
    assert "Inleveren → Bronselectie → Review → Publicatie → Documenten" in protocol


def test_v4_0_snapshot_is_frozen_and_formation_frame_is_current() -> None:
    old = read("docs/history/protocol-v4.0/PROTOCOL.md")
    assert "**Versie:** 4.0.0" in old
    assert "### 5.4 Vormingskader" not in old
    protocol = read("PROTOCOL.md")
    assert "### 5.4 Vormingskader en bronsoortstrategieën" in protocol
    for strategy in ("B. Richtlijn", "C. Beslisboom"):
        assert strategy in protocol
    assert "Een strategie introduceert geen parallelle kandidaatmaker." in protocol
    assert "Zij wijzigt nooit een vastgelegde of lopende route." in protocol
