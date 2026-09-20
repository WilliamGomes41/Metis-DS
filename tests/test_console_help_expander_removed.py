from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]

UI_FILES = (
    ROOT / "src" / "operations_console_app.py",
    ROOT / "src" / "audit_room_v1.py",
    ROOT / "src" / "publish_readiness_ui_v1.py",
    ROOT / "src" / "closed_review_loop_v1.py",
    ROOT / "src" / "review_workboard_v1.py",
    ROOT / "src" / "review_closure_v1.py",
    ROOT / "src" / "deterministic_review_repair_v1.py",
)


def test_legacy_console_help_expander_is_removed() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in UI_FILES)
    css = (ROOT / "assets" / "brand" / "console.css").read_text(encoding="utf-8")

    assert "def _help(" not in combined
    assert "_help(" not in combined
    assert "HELP_ONCE" not in combined
    assert "RESEARCHER_ROOMS" not in combined
    assert '<details class="help">' not in combined
    assert "Over deze console" not in combined
    assert ".help {" not in css
    assert ".help summary {" not in css
