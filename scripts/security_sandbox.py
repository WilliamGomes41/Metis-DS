#!/usr/bin/env python3
"""Run existing Metis security boundaries with synthetic, local-only state.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "output/runtime/security-sandbox"
TEST_DSN = "postgresql://metis_sandbox:sandbox-only@sandbox-db:5432/metis_security_test"
LOCAL_TESTS = (
    "tests/test_security_harden_wave3.py",
    "tests/test_processing_authorization.py",
    "tests/test_api_access_domain_v1.py",
    "tests/test_api_access_console_v1.py",
    "tests/test_api_access_product_v1.py",
    "tests/test_console_entra_v1.py",
    "tests/test_metis_mcp_v1.py",
)
POSTGRES_TESTS = (
    "tests/test_api_access_postgres_v1.py",
    "tests/test_api_access_lifecycle_v1.py",
    "tests/test_account_retirement_v1.py",
    "tests/test_workflow_postgres_concurrency.py",
)


def sandbox_environment(*, postgres: bool = False) -> dict[str, str]:
    # Refuse an external test target rather than silently letting tests mutate it.
    supplied = os.environ.get("METIS_TEST_POSTGRES_DSN", "")
    if supplied and supplied != TEST_DSN:
        raise SystemExit("Refusing non-sandbox METIS_TEST_POSTGRES_DSN; unset it first.")
    # No inherited Azure/Entra/LLM/database credentials or .env loading.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TERM") if key in os.environ}
    env.update(PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
               METIS_CONSOLE_AUTH="local", CONSOLE_DATA_ROOT=str(RUNTIME),
               CONSOLE_RUNTIME=str(RUNTIME / "console"), CONSOLE_SOURCE_STORE=str(RUNTIME / "sources"))
    if postgres:
        env["METIS_TEST_POSTGRES_DSN"] = TEST_DSN
    return env


def serve() -> None:
    env = sandbox_environment()
    codespace = os.environ.get("CODESPACE_NAME", "")
    domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
    if not codespace:
        raise SystemExit("Start the browser sandbox inside Codespaces (HTTPS required).")
    # Use the GitHub credential only for port privacy, before clearing the app environment.
    subprocess.run(["gh", "codespace", "ports", "visibility", "8000:private", "-c", codespace], check=True)
    env["CONSOLE_PUBLIC_ORIGIN"] = f"https://{codespace}-8000.{domain}"
    os.environ.clear()
    os.environ.update(env)
    sys.path.insert(0, str(ROOT))
    from src.console_asgi import build_app
    from src.operations_console_v1 import ConsoleError
    import uvicorn

    RUNTIME.mkdir(parents=True, exist_ok=True)
    credentials = RUNTIME / "accounts.json"
    if not credentials.exists():
        accounts = [dict(username=name, password=secrets.token_urlsafe(24), roles=[role])
                    for name, role in (("researcher-a", "researcher"), ("researcher-b", "researcher"),
                                       ("reviewer", "reviewer"), ("publisher", "publisher"))]
        # Local fixture credentials are ignored by Git and readable only by their owner.
        fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(accounts, stream, indent=2)
    accounts = json.loads(credentials.read_text())
    app = build_app()
    for account in accounts:
        try:
            app.state.operations_kernel.create_account(**account)
        except ConsoleError as exc:
            if exc.code != "username_already_exists":
                raise
    print(f"Synthetic login accounts: {credentials}")
    print(f"Private browser URL: {env['CONSOLE_PUBLIC_ORIGIN']}")
    uvicorn.run(app, host="0.0.0.0", port=8000)


def run_tests(*, local: bool) -> int:
    env = sandbox_environment(postgres=not local)
    if not local:
        import psycopg
        # Stop before pytest: an unavailable database must not look like skipped evidence.
        with psycopg.connect(TEST_DSN, connect_timeout=5) as connection:
            if connection.execute("SELECT current_database()").fetchone()[0] != "metis_security_test":
                raise SystemExit("Unexpected database; refusing tests.")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    tests = LOCAL_TESTS if local else LOCAL_TESTS + POSTGRES_TESTS
    report = RUNTIME / ("security-local.xml" if local else "security-postgres.xml")
    print("Local contract tests only; no PostgreSQL or live OAuth evidence." if local
          else "Contract tests plus native sandbox PostgreSQL; no live OAuth evidence.", flush=True)
    return subprocess.call([sys.executable, "-m", "pytest", "-q", *tests,
                            f"--junitxml={report}"], cwd=ROOT, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve")
    tests = commands.add_parser("test")
    tests.add_argument("--local", action="store_true", help="Run without PostgreSQL; reduced evidence.")
    args = parser.parse_args()
    if args.command == "serve":
        serve()
        return 0
    return run_tests(local=args.local)


if __name__ == "__main__":
    raise SystemExit(main())
