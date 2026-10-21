"""Run the Azure synchronization Bash step against disposable local repositories.

The promise is exact branch/tag synchronization, including rewrites and deletions.
This exercises the existing pipeline without another synchronization implementation.
It is repository evidence, not proof of Azure permissions or a live deployment.
"""
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

import os
from pathlib import Path
import subprocess
import textwrap


def test_azure_sync_copies_rewrites_deletes_and_reports_failures(tmp_path):
    pipeline = (Path(__file__).resolve().parents[1] / "azure-pipelines.yml").read_text()
    script = textwrap.dedent(
        pipeline.split("- bash: |\n", 1)[1].split("\n  displayName:", 1)[0]
    )
    source = tmp_path / "source"
    target = tmp_path / "target.git"
    source.mkdir()
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GIT_CONFIG_"):
            del env[key]
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Sync test",
        GIT_AUTHOR_EMAIL="sync@example.invalid",
        GIT_COMMITTER_NAME="Sync test",
        GIT_COMMITTER_EMAIL="sync@example.invalid",
        GIT_TERMINAL_PROMPT="0",
    )

    def git(*args, cwd=source):
        return subprocess.run(
            ["git", *args], cwd=cwd, env=env, check=True,
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()

    git("init", "-b", "main")
    git("commit", "--allow-empty", "-m", "initial")
    initial = git("rev-parse", "HEAD")
    git("branch", "feature")
    git("branch", "removed")
    git("tag", "-a", "release", "-m", "release")
    git("tag", "deleted-tag")
    git("clone", "--bare", str(source), str(target), cwd=tmp_path)
    git("update-ref", "refs/notes/keep", initial, cwd=target)
    git("branch", "azure-only", initial, cwd=target)
    git("tag", "azure-only", initial, cwd=target)
    script = script.replace(
        "https://github.com/WilliamGomes41/Metis-DS.git", str(source)
    )
    attempts = 0

    def sync(*, success=True):
        nonlocal attempts
        attempts += 1
        agent = tmp_path / f"agent-{attempts}"
        agent.mkdir()
        runenv = dict(
            env, AGENT_TEMPDIRECTORY=str(agent), TARGET_URL=str(target),
            AZURE_TOKEN="synthetic-test-token",
        )
        result = subprocess.run(
            ["bash", "-c", script], env=runenv,
            capture_output=True, text=True, timeout=30,
        )
        assert (result.returncode == 0) is success, result.stdout + result.stderr
        if success:
            args = ("for-each-ref", "--format=%(objectname) %(refname)",
                    "refs/heads", "refs/tags")
            assert git(*args) == git(*args, cwd=target)
            assert git("rev-parse", "refs/notes/keep", cwd=target) == initial
            assert "Controle geslaagd" in result.stdout
        return result

    git("commit", "--allow-empty", "-m", "normal update")
    sync()
    git("checkout", "feature")
    git("commit", "--allow-empty", "-m", "old feature history")
    sync()
    git("reset", "--hard", initial)
    git("commit", "--allow-empty", "-m", "rewritten feature history")
    git("tag", "-f", "-a", "release", "-m", "rewritten release")
    git("branch", "-D", "removed")
    git("tag", "-d", "deleted-tag")
    sync()
    git("tag", "-d", "release")
    sync()  # No source tags remain; target tags must also be gone.
    sync()  # Repeating the synchronization must preserve equality.

    git("checkout", "main")
    git("commit", "--allow-empty", "-m", "rejected update")
    hook = target / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    denied = sync(success=False)
    assert "Controle geslaagd" not in denied.stdout
    hook.unlink()

    # A target-only ref created after push must prevent a false success.
    hook = target / "hooks" / "post-receive"
    hook.write_text(
        "#!/bin/sh\ngit update-ref refs/heads/unexpected " + initial + "\n"
    )
    hook.chmod(0o755)
    mismatch = sync(success=False)
    assert "Controle mislukt" in mismatch.stdout
    hook.unlink()
    sync()  # The next run repairs that divergence.
