"""Current governance boundaries; old V3 wording is preserved as an archive snapshot.

Storage concurrency and stale-write behavior remain covered by
`test_workflow_postgres_concurrency.py` and `test_stale_write_ux.py`.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_v4_is_current_and_v3_is_frozen() -> None:
    current, old = read("PROTOCOL.md"), read("docs/history/protocol-v3/PROTOCOL.md")
    assert current.startswith("# V&VN Data Services — Protocol v4")
    assert "**Versie:** 4.3.1" in current
    assert old.startswith("# V&VN Data Services — Protocol v3")
    assert "**Versie:** 3.0.0" in old
    assert read("ROADMAP.md").startswith("# Metis — Roadmap v4")
    assert read("docs/history/protocol-v3/ROADMAP.md").startswith("# Metis — Roadmap v3")
    assert "Protocol v4.3.1" in read("docs/GOVERNANCE.md")

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

def test_runtime_declares_current_protocol() -> None:
    from src.operations_console_v1 import PUBLICATION_PROTOCOL_VERSION
    assert PUBLICATION_PROTOCOL_VERSION == "4.3.1"


def test_documented_formation_roles_match_existing_policy() -> None:
    from src.vorming.candidate_eligibility_v1 import assess_candidate_eligibility
    from src.vorming.passage_formation_policy_v1 import resolve_passage_formation_strategy
    from src.vorming.pre_review_semantic_v1 import _configured_passage_formation_mode

    protocol = read("PROTOCOL.md")
    mode = _configured_passage_formation_mode({})
    assert mode == "semantic-source-bound-v2"
    assert f"`{mode}` (source-bound-fields v2) de standaardroute" in protocol
    for explicit_mode in ("semantic-source-bound-v1", "semantic-source-bound-v3"):
        assert f"`{explicit_mode}`" in protocol
        assert resolve_passage_formation_strategy(deployment_mode=explicit_mode).strategy == "semantic"
    assert resolve_passage_formation_strategy(deployment_mode=mode).strategy == "semantic"
    assert "`deterministic-v1` is vervallen" in protocol
    from src.vorming.passage_formation_policy_v1 import PassageFormationPolicyError
    with pytest.raises(PassageFormationPolicyError, match="passage_formation_mode_invalid"):
        resolve_passage_formation_strategy(deployment_mode="deterministic-v1")
    assert not assess_candidate_eligibility({
        "proposed_object_type": "recommendation",
        "text": "Bespreek de behandeling met de patiënt.",
    }).eligible
    assert "Een deterministisch typelabel vormt op zichzelf geen toegelaten kenniskandidaat" in protocol
    assert "Een geslaagde controle bewijst geen semantische of klinische volledigheid" in protocol
    assert "Inleveren → Vorming → Review → Publicatie → Documenten" in protocol


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


def test_previous_protocols_are_archived_without_breaking_approval_evidence() -> None:
    archive = ROOT / "docs/history/protocol-v2"
    protocols = sorted(archive.glob("PROTOCOL_V2_*.md"))
    assert protocols, "historical protocol bytes must live under history"
    assert {p.name for p in protocols} == {
        p.name for p in (ROOT / "docs").glob("PROTOCOL_V2_*.md")
    }
    for archived in protocols:
        assert archived.is_file() and not archived.is_symlink()
        legacy = ROOT / "docs" / archived.name
        assert legacy.is_symlink(), "old paths are compatibility links only"
        assert legacy.readlink() == Path("history/protocol-v2") / archived.name
        assert legacy.resolve() == archived.resolve()

    for manifest_path in (ROOT / "data/assurance").glob("protocol_v2_*_approval.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        legacy = ROOT / manifest["protocol_path"]
        assert legacy.resolve().parent == archive.resolve()
        assert hashlib.sha256(legacy.read_bytes()).hexdigest() == manifest["protocol_sha256"]


def test_v4_3_is_vigerend_while_implementation_gaps_remain_explicit() -> None:
    protocol = read("PROTOCOL.md")
    assert protocol.startswith("# V&VN Data Services — Protocol v4.3.1\n")
    assert "**Status:** Vigerend — enige actuele protocolnorm" in protocol
    assert "**Versie:** 4.3.1" in protocol
    assert "## R4.6 Vormingskader per bron invoeren" in read("ROADMAP.md")
    assert "norm vastgelegd; implementatie open" in read("ROADMAP.md")
    workflow = read("docs/DEVELOPMENT_WORKFLOW.md")
    assert "product- en veiligheidsregels staan uitsluitend in `PROTOCOL.md` (v4.3.1)" in workflow
    assert "Alle v2.6–v2.11-regels blijven van kracht" not in workflow
    assert "Alle v2.6–v2.11-regels blijven van kracht" in read(
        "docs/history/protocol-v2/DEVELOPMENT_WORKFLOW_PRE_V4_1_2026-10-18.md"
    )


def test_v4_1_snapshot_is_frozen_and_decision_trees_have_one_route() -> None:
    old = read("docs/history/protocol-v4.1/PROTOCOL.md")
    assert "**Versie:** 4.1.0" in old
    assert "Beslisbomen behouden hun bestaande structurele route" in old
    protocol = read("PROTOCOL.md")
    assert "Beslisbomen behouden hun bestaande structurele route" not in protocol
    assert "`decision-tree-source-bound-v1` (enige toegelaten route)" in protocol
    assert "alleen menselijke graafreview bevestigt de interpretatie" in protocol
    from src.vorming.decision_tree_construction_v1 import FORMATION_MODE
    assert FORMATION_MODE == "decision-tree-source-bound-v1"


def test_v4_2_snapshot_is_frozen_and_semantic_formation_is_the_only_route() -> None:
    old = read("docs/history/protocol-v4.2/PROTOCOL.md")
    assert "**Versie:** 4.2.0" in old
    assert "JSON-export: deterministisch uit de expliciete exportrecords" in old
    protocol = read("PROTOCOL.md")
    assert "JSON-export: deterministisch" not in protocol
    assert "er bestaat geen deterministische vormingsroute meer" in protocol
    assert "Operationele rollback is uitsluitend een gecontroleerde softwareterugzetting." in protocol
    assert "faalt gesloten)" in protocol


def test_alignment_versions_current_norm_and_preserves_prior_protocol_bytes() -> None:
    """The current norm and runtime identifier agree; the prior protocol stays frozen."""
    import re
    from src.operations_console_v1 import PUBLICATION_PROTOCOL_VERSION

    previous_path = "docs/history/protocol-v4.3/PROTOCOL_BEFORE_ALIGNMENT_2026-11-01.md"
    previous_bytes = (ROOT / previous_path).read_bytes()
    assert hashlib.sha256(previous_bytes).hexdigest() == (
        "1eaeae0da519c90c09375eb67809bdac5f73d000a790d3e740308b51f1ca003d"
    )
    current_version = re.search(r"^\*\*Versie:\*\* (\S+)", read("PROTOCOL.md"), re.MULTILINE)
    assert current_version is not None
    assert current_version.group(1) == PUBLICATION_PROTOCOL_VERSION == "4.3.1"
    assert "**Versie:** 4.3.0" in previous_bytes.decode("utf-8")
    assert previous_path in read("PROTOCOL.md")
