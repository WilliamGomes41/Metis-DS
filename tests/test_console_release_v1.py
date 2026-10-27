"""Package identity and direct login through the production-composed application.

# release-control-evidence: scope/belofte product version and one Microsoft button
# release-control-evidence: toegang public notes start no flow; protected routes stay protected
# release-control-evidence: slop package-only read projection, unchanged identity authority
# release-control-evidence: releasebewijs native PostgreSQL HTTP and immutable package identity
"""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.stamp_console_release import stamp_release
from src.console_release_v1 import BUILD_FILE, console_release
from tests.test_console_entra_v1 import app_client, login


def _definition(root, release=32):
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config/console_release.json").write_text(json.dumps({
        "generation": 1, "release": release, "changes": ["Direct aanmelden", "<script>geen HTML</script>"]
    }))


@pytest.fixture
def package(tmp_path):
    _definition(tmp_path)
    (tmp_path / BUILD_FILE).write_text(json.dumps({"version": "1.32.7", "commit": "a" * 40}))
    (tmp_path / "config/deployed_commit.txt").write_text("a" * 40)
    return tmp_path


def test_runtime_reads_the_package_without_git_or_environment_override(package, monkeypatch):
    monkeypatch.setenv("METIS_BUILD_COMMIT", "b" * 40)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("runtime must not consult Git"))
    assert console_release(package)["version"] == "1.32.7"


@pytest.mark.parametrize("fault", ["commit", "version", "missing_build", "invalid_json", "release"])
def test_missing_or_mismatched_identity_never_invents_a_version(package, fault):
    if fault == "commit":
        (package / "config/deployed_commit.txt").write_text("b" * 40)
    elif fault == "version":
        (package / BUILD_FILE).write_text(json.dumps({"version": "2.32.7", "commit": "a" * 40}))
    elif fault == "missing_build":
        (package / BUILD_FILE).unlink()
    elif fault == "invalid_json":
        (package / BUILD_FILE).write_text("{")
    else:
        _definition(package, release=33)
    assert console_release(package)["version"] is None
    assert console_release(package)["label"] == "Versie niet beschikbaar"


def test_source_checkout_is_explicitly_development(tmp_path):
    _definition(tmp_path)
    assert console_release(tmp_path)["label"] == "Ontwikkelversie"


def test_both_build_contexts_and_rollback_keep_exact_commit_identity(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    def git(*args):
        return subprocess.run(["git", *args], cwd=source, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-b", "main")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Build test")
    _definition(source)
    git("add", "config")
    git("commit", "-m", "release")
    first = git("rev-parse", "HEAD")
    old_package = tmp_path / "zip"
    shutil.copytree(source / "config", old_package / "config")
    (old_package / "config/deployed_commit.txt").write_text(first)
    stamp_release(source, old_package, first)
    assert console_release(old_package)["version"] == "1.32.1"
    _definition(source, release=33)
    git("add", "config")
    git("commit", "-m", "next release")
    second = git("rev-parse", "HEAD")
    new_package = tmp_path / "container"
    shutil.copytree(source / "config", new_package / "config")
    (new_package / "config/deployed_commit.txt").write_text(second)
    stamp_release(source, new_package, second)
    assert console_release(new_package)["version"] == "1.33.2"
    # An older package is unchanged when main advances; rebuilding it is stable.
    stamp_release(source, old_package, first)
    assert console_release(old_package)["version"] == "1.32.1"
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "--depth=1", source.as_uri(), str(shallow)], check=True, capture_output=True)
    with pytest.raises(ValueError, match="full_history"):
        stamp_release(shallow, new_package, second)


def test_public_sign_in_notes_and_authenticated_home_share_version(
        package, monkeypatch, production_app, production_console):
    monkeypatch.setattr("src.console_release_v1.ROOT", package)
    state = production_console()
    client, _ = app_client(monkeypatch, state, production_app=production_app)
    store = state.workflow_identity_store
    # These public reads do not start a handshake or require a database session.
    with store._connect() as connection:
        before = connection.execute("SELECT count(*) AS n FROM workflow.entra_flows").fetchone()["n"]
    for path in ("/", "/login"):
        response = client.get(path)
        assert response.status_code == 200
        assert 'href="/auth/microsoft"' in response.text
        assert 'href="/login" style=' not in response.text
        assert 'type="password"' not in response.text
        assert 'Versie 1.32.7' in response.text
        assert 'href="/wat-is-nieuw"' in response.text
    notes = client.get("/wat-is-nieuw", follow_redirects=False)
    assert notes.status_code == 200
    assert "Direct aanmelden" in notes.text and "Versie 1.32.7" in notes.text
    assert "&lt;script&gt;geen HTML&lt;/script&gt;" in notes.text
    assert "<script>geen HTML</script>" not in notes.text
    with store._connect() as connection:
        assert connection.execute("SELECT count(*) AS n FROM workflow.entra_flows").fetchone()["n"] == before
    assert not client.cookies
    assert client.get("/health").json()["product_version"] == "1.32.7"
    protected = client.get("/settings", follow_redirects=False)
    assert protected.status_code == 303
    assert protected.headers["location"].startswith("/auth/microsoft?")
    assert login(client, store).status_code == 303
    home = client.get("/")
    assert "Mijn werk" in home.text and "Versie 1.32.7" in home.text
    assert 'data-version="1.32.7"' in home.text


def test_local_sign_in_is_the_same_form_on_both_entry_points(production_app):
    from fastapi.testclient import TestClient
    with TestClient(production_app(), base_url="https://testserver") as client:
        for path in ("/", "/login"):
            page = client.get(path)
            assert page.status_code == 200
            assert 'action="/login"' in page.text and 'type="password"' in page.text
            assert 'href="/auth/microsoft"' not in page.text
