"""Release guard: manual test deploys must originate from main."""

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deploy_test_requires_main_ancestry_before_azure_or_deploy() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-test.yml").read_text(
        encoding="utf-8"
    )

    ancestry = workflow.index("git merge-base --is-ancestor")
    azure_login = workflow.index("azure/login@v2")
    deploy = workflow.index("az webapp deploy")

    assert "git fetch origin main --depth=1" in workflow
    assert '"$(git rev-parse HEAD)" origin/main' in workflow
    assert ancestry < azure_login < deploy
    assert "workflow_dispatch" in workflow
    assert "\n  push:" not in workflow


def test_production_container_keeps_exact_main_sha_gate_before_build() -> None:
    script = (ROOT / "scripts/build_azure_release_image.sh").read_text(encoding="utf-8")
    assert 'git -C "${ROOT}" fetch --quiet origin main' in script
    assert 'release_image_commit_must_be_full_sha' in script
    assert 'git -C "${ROOT}" merge-base --is-ancestor "${commit}" origin/main' in script
    assert script.index('merge-base --is-ancestor') < script.index('archive "${commit}"') < script.index('az acr build')
