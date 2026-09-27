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
    assert "**Versie:** 4.0.0" in current
    assert old.startswith("# V&VN Data Services — Protocol v3")
    assert "**Versie:** 3.0.0" in old
    assert read("ROADMAP.md").startswith("# Metis — Roadmap v4")
    assert read("docs/history/protocol-v3/ROADMAP.md").startswith("# Metis — Roadmap v3")
    assert "Protocol v4.0.0" in read("docs/GOVERNANCE.md")

def test_v4_retains_safety_and_describes_actual_modes() -> None:
    protocol = read("PROTOCOL.md")
    for required in (
        "selected_as_candidate", "exacte objectidentiteit", "Four-eyes",
        "G2-publicatie is conditioneel beschikbaar **per snapshot**",
        "SHA-256 van de gezaghebbende bronbytes", "gezaghebbende commit",
        "publication_registry", "METIS_CONSOLE_AUTH=entra",
        "brongebonden semantische route", "geen stille terugval",
        "afgeleide, rebuildable projectie", "READY FOR IMPLEMENTATION",
    ):
        assert required in protocol

def test_new_release_records_current_protocol() -> None:
    from src.operations_console_v1 import PUBLICATION_PROTOCOL_VERSION
    assert PUBLICATION_PROTOCOL_VERSION == "4.0.0"
