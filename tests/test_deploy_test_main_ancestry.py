"""Release guard: manual test deploys must originate from main."""
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


def test_production_keeps_exact_main_sha_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-production.yml").read_text(
        encoding="utf-8"
    )

    assert "Validate exact main commit" in workflow
    assert 'test "$(git rev-parse HEAD)" = "$REQUESTED_SHA"' in workflow
    assert 'git merge-base --is-ancestor "$REQUESTED_SHA" origin/main' in workflow
