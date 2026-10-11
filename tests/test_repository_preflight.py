from pathlib import Path

import pytest

from scripts import repository_preflight


# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs


@pytest.mark.parametrize("text", [
    "risk-proportional-verification",
    "[risk-proportional-verification](.agents/skills/risk-proportional-verification/SKILL.md)",
])
def test_skill_names_do_not_block_repository_preflight(tmp_path: Path, monkeypatch, capsys, text: str) -> None:
    artifact = tmp_path / "AGENTS.md"
    artifact.write_text(text, encoding="utf-8")
    monkeypatch.setattr(repository_preflight, "ROOT", tmp_path)
    monkeypatch.setattr(repository_preflight, "validate_infrastructure_manifest", lambda errors: None)
    monkeypatch.setattr(repository_preflight, "validate_g2_runtime_pins", lambda errors: None)

    assert repository_preflight.main() == 0
    assert '"status": "PASS"' in capsys.readouterr().out


@pytest.mark.parametrize("wrapper", ["{}", 'OPENAI_API_KEY="{}"', '{{"api_key": "{}"}}', "Bearer {}"])
def test_openai_key_patterns_still_block_repository_preflight(tmp_path: Path, monkeypatch, capsys, wrapper: str) -> None:
    # Construct a synthetic pattern, not a credential stored in the fixture.
    synthetic_key = "sk" + "-" + "test_" + "a" * 30
    artifact = tmp_path / "config.txt"
    artifact.write_text(wrapper.format(synthetic_key), encoding="utf-8")
    monkeypatch.setattr(repository_preflight, "ROOT", tmp_path)
    monkeypatch.setattr(repository_preflight, "validate_infrastructure_manifest", lambda errors: None)
    monkeypatch.setattr(repository_preflight, "validate_g2_runtime_pins", lambda errors: None)

    assert repository_preflight.main() == 2
    assert "possible openai_key secret detected in: config.txt" in capsys.readouterr().out
