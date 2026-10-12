#!/usr/bin/env python3
"""Run Metis security tests/scans only after verifying the offline boundary.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import argparse
import errno
import ipaddress
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "output/runtime/security-sandbox"
TEST_DSN = "postgresql://metis_sandbox:sandbox-only@sandbox-db:5432/metis_security_test"
# Azurite (CON-03) on the internal sandbox network; well-known public dev account key.
AZURITE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://172.30.254.30:10000/devstoreaccount1;")
# Build-time preloaded offline assets (runner image); passed through only if set.
OFFLINE_ASSET_ENV = ("PLAYWRIGHT_BROWSERS_PATH", "HF_HOME", "METIS_DOCLING_PYTHON",
                     "METIS_DOCLING_ARTIFACTS_PATH", "METIS_PI05_MODEL_PATH",
                     "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY")
SANDBOX_NETWORK = ipaddress.ip_network("172.30.254.0/24")
LOCAL_TESTS = (
    "tests/test_security_sandbox.py",
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


def assert_isolated_network() -> None:
    """Reject default/external routes; then require an explicit unreachable result.

    A default route is tolerated only when its gateway lies inside the internal
    sandbox network (Docker internal-network gateway); in that case the external
    probe must fail (unreachable or timeout) AND external DNS must fail.
    This verifies the expected container namespace, not arbitrary malware containment.
    """
    internal_default = False
    for line in Path("/proc/net/route").read_text().splitlines()[1:]:
        fields = line.split()
        if not int(fields[3], 16) & 1:
            continue
        destination = ipaddress.IPv4Address(bytes.fromhex(fields[1])[::-1])
        mask = str(ipaddress.IPv4Address(bytes.fromhex(fields[7])[::-1]))
        network = ipaddress.IPv4Network((str(destination), mask), strict=False)
        if network.subnet_of(SANDBOX_NETWORK) or network.subnet_of(ipaddress.ip_network("127.0.0.0/8")):
            continue
        gateway = ipaddress.IPv4Address(bytes.fromhex(fields[2])[::-1])
        if network.prefixlen == 0 and gateway in SANDBOX_NETWORK:
            internal_default = True
            continue
        raise SystemExit("Network isolation unconfirmed: external/default IPv4 route.")
    for line in Path("/proc/net/ipv6_route").read_text().splitlines():
        fields = line.split()
        flags = int(fields[8], 16)
        if not flags & 1 or flags & 0x200:  # Down or explicitly unreachable route.
            continue
        network = ipaddress.IPv6Network((ipaddress.IPv6Address(int(fields[0], 16)), int(fields[1], 16)), strict=False)
        if not (network.subnet_of(ipaddress.ip_network("::1/128")) or network.subnet_of(ipaddress.ip_network("fe80::/10"))):
            raise SystemExit("Network isolation unconfirmed: external/default IPv6 route.")
    if internal_default:
        try:
            socket.getaddrinfo("example.com", 443)
        except OSError:
            pass
        else:
            raise SystemExit("External DNS resolves; refusing security execution.")
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=2):
            pass
    except OSError as exc:
        if exc.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
            return
        if internal_default and isinstance(exc, TimeoutError):
            return
        raise SystemExit("Network isolation unconfirmed: probe did not report unreachable.") from exc
    raise SystemExit("External network reachable; refusing security execution.")


def sandbox_environment(*, postgres: bool = False) -> dict[str, str]:
    supplied = os.environ.get("METIS_TEST_POSTGRES_DSN", "")
    if supplied and supplied != TEST_DSN:
        raise SystemExit("Refusing non-sandbox METIS_TEST_POSTGRES_DSN; unset it first.")
    supplied_blob = os.environ.get("METIS_TEST_AZURITE_CONNECTION_STRING", "")
    if supplied_blob and supplied_blob != AZURITE_CONNECTION_STRING:
        raise SystemExit("Refusing non-sandbox METIS_TEST_AZURITE_CONNECTION_STRING; unset it first.")
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TERM") + OFFLINE_ASSET_ENV
           if key in os.environ}
    env.update(PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
               METIS_CONSOLE_AUTH="local", CONSOLE_DATA_ROOT=str(RUNTIME),
               CONSOLE_RUNTIME=str(RUNTIME / "console"), CONSOLE_SOURCE_STORE=str(RUNTIME / "sources"),
               SEMGREP_SEND_METRICS="off", SEMGREP_ENABLE_VERSION_CHECK="0",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               METIS_TEST_AZURITE_CONNECTION_STRING=AZURITE_CONNECTION_STRING)
    if postgres:
        env["METIS_TEST_POSTGRES_DSN"] = TEST_DSN
    return env


def run_tests(*, local: bool) -> int:
    env = sandbox_environment(postgres=not local)
    assert_isolated_network()
    if not local:
        import psycopg
        with psycopg.connect(TEST_DSN, connect_timeout=5) as connection:
            if connection.execute("SELECT current_database()").fetchone()[0] != "metis_security_test":
                raise SystemExit("Unexpected database; refusing tests.")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    tests = LOCAL_TESTS if local else LOCAL_TESTS + POSTGRES_TESTS
    report = RUNTIME / ("security-local.xml" if local else "security-postgres.xml")
    print("Offline local tests; no PostgreSQL or live OAuth evidence." if local
          else "Offline tests plus native sandbox PostgreSQL; no live OAuth evidence.", flush=True)
    return subprocess.call([sys.executable, "-m", "pytest", "-q", *tests,
                            f"--junitxml={report}"], cwd=ROOT, env=env)


def run_scans() -> int:
    env = sandbox_environment()
    assert_isolated_network()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    results = []
    commands = (
        ["bandit", "-r", "src", "-f", "json", "-o", str(RUNTIME / "bandit.json")],
        ["semgrep", "scan", "--metrics=off", "--disable-version-check", "--error", "--json",
         "--config", str(ROOT / ".devcontainer/semgrep.yml"), "--output", str(RUNTIME / "semgrep.json"), "src"],
    )
    for command in commands:
        results.append(subprocess.call(command, cwd=ROOT, env=env))
    # Preserve nonzero results: findings/tool failures are never silently marked clean.
    return max(results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    commands.add_parser("scan")
    tests = commands.add_parser("test")
    tests.add_argument("--local", action="store_true", help="Skip PostgreSQL only; network checks still apply.")
    args = parser.parse_args()
    if args.command == "check":
        sandbox_environment()
        assert_isolated_network()
        print("Offline route/probe checks: PASS. This is not a production security verdict.")
        return 0
    if args.command == "scan":
        return run_scans()
    return run_tests(local=args.local)


if __name__ == "__main__":
    raise SystemExit(main())
