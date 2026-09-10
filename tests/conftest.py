"""Shared pytest configuration.

Historical Protocol-v2 contract tests remain executable audit evidence after the
Protocol-v3 cutover. Those tests were written when ``PROTOCOL.md``,
``ROADMAP.md`` and ``docs/GOVERNANCE.md`` also acted as an accumulating history
log. During historical tests only, reads of those three paths are therefore
resolved to the frozen pre-v3 snapshots. Current/V3 tests always read the live
root documents.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]

_V2_PROTOCOL = ROOT / "docs" / "history" / "protocol-v2" / "PROTOCOL_ROOT_FINAL_2026-09-10.md"
_V2_ROADMAP = ROOT / "docs" / "history" / "protocol-v2" / "ROADMAP_PRE_V3_2026-09-10.md"
_V2_GOVERNANCE = ROOT / "docs" / "history" / "protocol-v2" / "GOVERNANCE_PRE_V3_2026-09-10.md"

_LIVE_TO_HISTORY = {
    (ROOT / "PROTOCOL.md").resolve(): _V2_PROTOCOL,
    (ROOT / "ROADMAP.md").resolve(): _V2_ROADMAP,
    (ROOT / "docs" / "GOVERNANCE.md").resolve(): _V2_GOVERNANCE,
}

_HISTORICAL_FILE_PREFIXES = (
    "tests/test_protocol_v2_",
    "tests/test_roadmap_",
)

_HISTORICAL_EXACT_NODES = {
    "tests/test_g2_azure_preflight.py::test_roadmap_and_changelog_record_readiness_not_pass",
    "tests/test_gd_03_assurance.py::test_gd03_assurance_matches_governance_bytes_and_is_established",
    "tests/test_gd_03_assurance.py::test_gd03_human_record_and_governance_keep_other_decisions_open",
    "tests/test_topology_bound.py::test_roadmap_records_remediation_5_landing_note",
    "tests/test_topology_bound.py::test_remediation_5_does_not_open_multi_writer_extend_or_protocol",
    "tests/test_wave5_gericht_vereenvoudigen.py::test_roadmap_live_norm_is_readable_and_historical_stacks_are_demoted",
}

_orig_read_text = Path.read_text
_orig_read_bytes = Path.read_bytes


def _is_historical_governance_test(nodeid: str) -> bool:
    test_file = nodeid.split("::", 1)[0]
    return test_file.startswith(_HISTORICAL_FILE_PREFIXES) or nodeid in _HISTORICAL_EXACT_NODES


@pytest.fixture(autouse=True)
def _freeze_v2_root_documents_for_historical_contracts(request, monkeypatch):  # type: ignore[no-untyped-def]
    """Make legacy document assertions read the immutable pre-v3 snapshots."""
    if not _is_historical_governance_test(request.node.nodeid):
        return

    def historical_read_text(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        archived = _LIVE_TO_HISTORY.get(self.resolve())
        if archived is not None:
            return _orig_read_text(archived, *args, **kwargs)
        return _orig_read_text(self, *args, **kwargs)

    def historical_read_bytes(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        archived = _LIVE_TO_HISTORY.get(self.resolve())
        if archived is not None:
            return _orig_read_bytes(archived, *args, **kwargs)
        return _orig_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", historical_read_text)
    monkeypatch.setattr(Path, "read_bytes", historical_read_bytes)


_orig_init = TestClient.__init__


def _https_init(self, app, base_url: str = "https://testserver", **kwargs):  # type: ignore[no-untyped-def]
    _orig_init(self, app, base_url=base_url, **kwargs)


TestClient.__init__ = _https_init  # type: ignore[method-assign]
