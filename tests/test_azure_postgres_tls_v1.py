"""#1074: Azure adapters verify the peer; local PostgreSQL DSNs stay compatible.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag toegang
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
from types import SimpleNamespace

import psycopg
import pytest

from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig


ADAPTERS = (
    ("src.publication.canonical_publication_postgres_v1", "PostgresCanonicalPublicationStore", "canonical_postgres_unavailable"),
    ("src.workflows.workflow_identity_postgres_v1", "PostgresWorkflowIdentityStore", "workflow_postgres_unavailable"),
    ("src.workflows.workflow_documents_postgres_v1", "PostgresWorkflowDocumentStore", "workflow_postgres_unavailable"),
    ("src.workflows.workflow_review_postgres_v1", "PostgresWorkflowReviewStore", "workflow_postgres_unavailable"),
    ("src.workflows.workflow_remaining_postgres_v1", "PostgresWorkflowRemainingStore", "workflow_postgres_unavailable"),
    ("src.settings.api_access_v1", "PostgresApiAccessStore", "api_access_postgres_unavailable"),
)


@pytest.fixture
def trust_root(tmp_path, monkeypatch):
    root = tmp_path / "trusted-ca.pem"
    root.write_text("adapter test trust root; no TLS handshake in parameter tests")
    monkeypatch.setenv("PGSSLROOTCERT", str(root))
    return root


def _store(module_name, class_name, config):
    module = importlib.import_module(module_name)
    credential = SimpleNamespace(get_token=lambda *a: SimpleNamespace(token="synthetic-test-token"))
    return getattr(module, class_name)(config=config, credential=credential)


@pytest.mark.parametrize("module_name,class_name,error", ADAPTERS)
def test_managed_identity_adapters_require_hostname_verification(monkeypatch, trust_root, module_name, class_name, error):
    captured = {}
    marker = object()
    def connect(*args, **kwargs):
        captured.update(kwargs)
        return marker
    monkeypatch.setattr(psycopg, "connect", connect)
    config = PostgresCanonicalConfig(host="metis.postgres.database.azure.com", database="metis", user="runtime")
    assert _store(module_name, class_name, config)._connect() is marker
    assert captured["sslmode"] == "verify-full"
    assert captured["sslrootcert"] == str(trust_root)
    assert captured["connect_timeout"] == 10


@pytest.mark.parametrize("module_name,class_name,error", ADAPTERS)
@pytest.mark.parametrize("host", ["metis.postgres.database.azure.com", "localhost,metis.postgres.database.azure.com"])
def test_azure_dsn_cannot_downgrade_verification(monkeypatch, trust_root, module_name, class_name, error, host):
    captured = {}
    def connect(*args, **kwargs):
        captured.update(kwargs)
        return object()
    monkeypatch.setattr(psycopg, "connect", connect)
    config = PostgresCanonicalConfig(dsn=f"host={host} dbname=metis user=runtime sslmode=require")
    _store(module_name, class_name, config)._connect()
    assert captured["sslmode"] == "verify-full"
    assert captured["sslrootcert"] == str(trust_root)


@pytest.mark.parametrize("module_name,class_name,error", ADAPTERS)
def test_local_dsn_keeps_its_connection_configuration(monkeypatch, module_name, class_name, error):
    captured = {}
    dsn = "host=127.0.0.1 dbname=test user=postgres sslmode=disable"
    def connect(*args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return object()
    monkeypatch.setattr(psycopg, "connect", connect)
    monkeypatch.setenv("PGSSLROOTCERT", "/not-present/local-tests-need-no-ca")
    _store(module_name, class_name, PostgresCanonicalConfig(dsn=dsn))._connect()
    assert captured["args"] == (dsn,)
    assert "sslmode" not in captured["kwargs"]
    assert "sslrootcert" not in captured["kwargs"]


def test_migration_entra_connection_uses_the_same_tls_policy(monkeypatch, trust_root):
    from src.workflows.workflow_postgres_migration_v1 import connect_entra
    captured = {}
    monkeypatch.setattr(psycopg, "connect", lambda **kw: captured.update(kw))
    credential = SimpleNamespace(get_token=lambda *a: SimpleNamespace(token="synthetic-test-token"))
    connect_entra(host="metis.postgres.database.azure.com", database="metis", user="admin", credential=credential)
    assert captured["sslmode"] == "verify-full"
    assert captured["sslrootcert"] == str(trust_root)


@pytest.mark.parametrize("module_name,class_name,error", ADAPTERS)
def test_missing_explicit_root_fails_before_connect_and_preserves_safe_error(monkeypatch, module_name, class_name, error):
    monkeypatch.setenv("PGSSLROOTCERT", "/not-present/azure-ca.pem")
    attempted = []
    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: attempted.append(kw))
    config = PostgresCanonicalConfig(host="metis.postgres.database.azure.com", database="metis", user="runtime")
    with pytest.raises(RuntimeError, match=f"^{error}$"):
        _store(module_name, class_name, config)._connect()
    assert attempted == []


def test_system_ca_bundle_is_used_when_no_explicit_root(monkeypatch, trust_root):
    from src.azure_postgres_credential_v1 import azure_postgres_tls_options
    monkeypatch.delenv("PGSSLROOTCERT")
    monkeypatch.setattr("ssl.get_default_verify_paths", lambda: SimpleNamespace(cafile=str(trust_root)))
    assert azure_postgres_tls_options() == {"sslmode": "verify-full", "sslrootcert": str(trust_root)}


def test_missing_system_trust_fails_closed(monkeypatch):
    from src.azure_postgres_credential_v1 import azure_postgres_tls_options
    monkeypatch.delenv("PGSSLROOTCERT", raising=False)
    monkeypatch.setattr("ssl.get_default_verify_paths", lambda: SimpleNamespace(cafile=None))
    with pytest.raises(ValueError, match="azure_postgres_trust_root_unavailable"):
        azure_postgres_tls_options()


@pytest.mark.parametrize("dsn", [
    "postgresql://runtime@METIS.POSTGRES.DATABASE.AZURE.COM./metis?sslmode=disable",
    "host=localhost,metis.postgres.database.azure.com dbname=metis sslmode=prefer",
])
def test_azure_dsn_host_forms_and_explicit_root(monkeypatch, trust_root, dsn):
    from src.azure_postgres_credential_v1 import postgres_dsn_tls_options
    assert postgres_dsn_tls_options(dsn) == {"sslmode": "verify-full", "sslrootcert": str(trust_root)}


def test_azure_host_from_libpq_environment_cannot_bypass_policy(monkeypatch, trust_root):
    from src.azure_postgres_credential_v1 import postgres_dsn_tls_options
    monkeypatch.setenv("PGHOST", "metis.postgres.database.azure.com")
    assert postgres_dsn_tls_options("dbname=metis sslmode=disable")["sslmode"] == "verify-full"
    assert postgres_dsn_tls_options("host=localhost dbname=test sslmode=disable") == {}


def test_dsn_root_is_preserved_and_not_silently_replaced(monkeypatch, trust_root):
    from src.azure_postgres_credential_v1 import postgres_dsn_tls_options
    monkeypatch.setenv("PGSSLROOTCERT", "/not-present/environment.pem")
    dsn = f"host=metis.postgres.database.azure.com sslrootcert='{trust_root}' sslmode=require"
    assert postgres_dsn_tls_options(dsn)["sslrootcert"] == str(trust_root)
    with pytest.raises(ValueError, match="azure_postgres_trust_root_unavailable"):
        postgres_dsn_tls_options("host=metis.postgres.database.azure.com sslrootcert=/not-present/explicit.pem")


@pytest.fixture(scope="module")
def tls_postgres(tmp_path_factory):
    """Own cluster: never enable TLS or restart the supplied test server."""
    candidates = [os.environ.get("PGBIN", ""), "/usr/lib/postgresql/16/bin", "/workspace/.postgres/usr/lib/postgresql/17/bin"]
    pgbin = next((Path(p) for p in candidates if p and (Path(p) / "initdb").is_file()), None)
    if pgbin is None:
        pytest.fail("TLS proof needs installed PostgreSQL binaries; it must not be skipped")
    if shutil.which("openssl") is None:
        pytest.fail("TLS proof needs openssl; it must not be skipped")
    root = tmp_path_factory.mktemp("azure-tls")
    data = root / "data"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    def run(args):
        result = subprocess.run([str(x) for x in args], capture_output=True, text=True)
        if result.returncode:
            pytest.fail(f"TLS fixture {Path(args[0]).name} failed: {result.stderr[-2000:]}")
    run([pgbin / "initdb", "-D", data, "-U", "postgres", "--encoding=UTF8", "--no-locale", "--auth-local=trust", "--auth-host=trust"])
    for stem, name in [("server", "localhost"), ("other", "untrusted")]:
        run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
             "-keyout", root / f"{stem}.key", "-out", root / f"{stem}.crt", "-subj", f"/CN={name}",
             "-addext", f"subjectAltName=DNS:{name}", "-addext", "basicConstraints=critical,CA:TRUE"])
        (root / f"{stem}.key").chmod(0o600)
    options = shlex.join(["-h", "127.0.0.1", "-p", str(port), "-k", str(root), "-c", "ssl=on",
                         "-c", f"ssl_cert_file={root / 'server.crt'}", "-c", f"ssl_key_file={root / 'server.key'}"])
    run([pgbin / "pg_ctl", "-D", data, "-l", root / "server.log", "-o", options, "-w", "start"])
    try:
        yield dict(hostaddr="127.0.0.1", port=port, dbname="postgres", user="postgres", connect_timeout=3), root
    finally:
        run([pgbin / "pg_ctl", "-D", data, "-m", "fast", "-w", "stop"])


def test_real_tls_accepts_correct_hostname_and_rejects_wrong_hostname_and_ca(tls_postgres, monkeypatch):
    from src.azure_postgres_credential_v1 import azure_postgres_tls_options
    connection, root = tls_postgres
    monkeypatch.setenv("PGSSLROOTCERT", str(root / "server.crt"))
    options = azure_postgres_tls_options()
    with psycopg.connect(**connection, host="localhost", **options) as con:
        assert con.execute("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()").fetchone()[0]
    with pytest.raises(psycopg.OperationalError, match="does not match host name"):
        psycopg.connect(**connection, host="wrong-host.invalid", **options)
    monkeypatch.setenv("PGSSLROOTCERT", str(root / "other.crt"))
    with pytest.raises(psycopg.OperationalError, match="certificate verify failed"):
        psycopg.connect(**connection, host="localhost", **azure_postgres_tls_options())


def test_token_cache_refresh_is_unchanged_by_tls(monkeypatch):
    from src.azure_postgres_credential_v1 import CachedAzurePostgresCredential
    clock = [1000]
    monkeypatch.setattr("src.azure_postgres_credential_v1.time.time", lambda: clock[0])
    requested = []
    def token(*scopes):
        requested.append(scopes)
        return SimpleNamespace(token=f"synthetic-{len(requested)}", expires_on=clock[0] + 600)
    cache = CachedAzurePostgresCredential(SimpleNamespace(get_token=token))
    assert cache.get_token("scope").token == "synthetic-1"
    assert cache.get_token("scope").token == "synthetic-1"
    clock[0] += 500
    assert cache.get_token("scope").token == "synthetic-2"
    assert len(requested) == 2
