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
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "output/runtime/security-sandbox"
TEST_DSN = "postgresql://metis_sandbox:sandbox-only@sandbox-db:5432/metis_security_test"
# Azurite (CON-03) blob endpoint on the internal sandbox network (account
# devstoreaccount1; the public Azurite dev key is supplied by the test itself).
AZURITE_BLOB_ENDPOINT = "http://172.30.254.30:10000/devstoreaccount1"
# Build-time preloaded offline assets (runner image); passed through only if set.
OFFLINE_ASSET_ENV = ("PLAYWRIGHT_BROWSERS_PATH", "HF_HOME", "METIS_DOCLING_PYTHON",
                     "METIS_DOCLING_ARTIFACTS_PATH", "METIS_PI05_MODEL_PATH",
                     "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY")
SANDBOX_NETWORK = ipaddress.ip_network("172.30.254.0/24")
# Written on the host by devcontainer initializeCommand; mounted read-only in the runner.
ATTEST_FILE = Path("/sandbox-attest/network.json")
ATTEST_NETWORK = "metis-sandbox"
PROBE_TIMEOUT = 2
EGRESS_TARGETS = (("tcp", ("1.1.1.1", 443)), ("tcp", ("8.8.8.8", 53)), ("udp", ("8.8.8.8", 53)),
                  ("tcp6", ("2606:4700:4700::1111", 443)))
CONTROL_DIR = Path("/sandbox-control")
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
    sandbox network AND a host attestation proves Internal=true for that subnet;
    then DNS MOET falen and every egress target MOET unreachable or time out.
    Without that route every target MOET report ENETUNREACH/EHOSTUNREACH.
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
        # A timeout is only acceptable on a host-attested internal network (#653 T10).
        load_network_attestation()
        try:
            socket.getaddrinfo("example.com", 443)
        except OSError:
            pass
        else:
            raise SystemExit("External DNS resolves; refusing security execution.")
    for kind, address in EGRESS_TARGETS:
        try:
            if kind == "udp":
                _udp_reach(address)
            else:
                with socket.create_connection(address, timeout=PROBE_TIMEOUT):
                    pass
        except OSError as exc:
            if exc.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH} and not isinstance(exc, TimeoutError):
                continue
            if kind == "tcp6" and exc.errno in {errno.EAFNOSUPPORT, errno.EADDRNOTAVAIL}:
                continue  # No IPv6 stack in the namespace: the IPv6 target is unreachable.
            if internal_default and isinstance(exc, TimeoutError):
                continue
            raise SystemExit(f"Network isolation unconfirmed: probe {kind} {address} did not report unreachable.") from exc
        raise SystemExit(f"External network reachable ({kind} {address}); refusing security execution.")
    if internal_default:
        print("isolated_by_internal_network_attested", flush=True)


def _udp_reach(address: tuple[str, int]) -> bytes:
    """Send one DNS query; any answer means egress. Errors propagate to the caller."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        udp.settimeout(PROBE_TIMEOUT)
        udp.connect(address)
        udp.send(bytes.fromhex("abcd01000001000000000000076578616d706c6503636f6d0000010001"))
        return udp.recv(512)


def load_network_attestation() -> dict:
    """Host-side `docker network inspect` result (read-only mount); missing/invalid MOET weigeren."""
    try:
        data = json.loads(ATTEST_FILE.read_text())
        network = data[0] if isinstance(data, list) else data
        subnets = {entry.get("Subnet") for entry in network["IPAM"]["Config"]}
        valid = (network.get("Name") == ATTEST_NETWORK and network.get("Internal") is True
                 and str(SANDBOX_NETWORK) in subnets)
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise SystemExit("Network attestation missing or unreadable; refusing security execution.") from exc
    if not valid:
        raise SystemExit("Network attestation does not prove an internal sandbox network; refusing.")
    return network


def egress_error_is_explicit(exc: BaseException) -> bool:
    """True only for DNS failure or ENETUNREACH/EHOSTUNREACH; timeout/TLS/refused MAG NIET gelden."""
    reason = getattr(exc, "reason", None)
    if isinstance(reason, BaseException):
        exc = reason
    if isinstance(exc, socket.gaierror):
        return True
    return (isinstance(exc, OSError) and not isinstance(exc, TimeoutError)
            and exc.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH})


def mount_is_readonly(mountinfo: str, mount_point: str) -> bool:
    """Read the per-mount 'ro' flag from /proc/self/mountinfo (last entry wins)."""
    readonly = False
    found = False
    for line in mountinfo.splitlines():
        fields = line.split()
        if len(fields) > 5 and fields[4] == mount_point:
            found = True
            readonly = "ro" in fields[5].split(",")
    return found and readonly


def sandbox_environment(*, postgres: bool = False) -> dict[str, str]:
    supplied = os.environ.get("METIS_TEST_POSTGRES_DSN", "")
    if supplied and supplied != TEST_DSN:
        raise SystemExit("Refusing non-sandbox METIS_TEST_POSTGRES_DSN; unset it first.")
    supplied_blob = os.environ.get("METIS_TEST_AZURITE_BLOB_ENDPOINT", "")
    if supplied_blob and supplied_blob != AZURITE_BLOB_ENDPOINT:
        raise SystemExit("Refusing non-sandbox METIS_TEST_AZURITE_BLOB_ENDPOINT; unset it first.")
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TERM") + OFFLINE_ASSET_ENV
           if key in os.environ}
    env.update(PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
               METIS_CONSOLE_AUTH="local", CONSOLE_DATA_ROOT=str(RUNTIME),
               CONSOLE_RUNTIME=str(RUNTIME / "console"), CONSOLE_SOURCE_STORE=str(RUNTIME / "sources"),
               SEMGREP_SEND_METRICS="off", SEMGREP_ENABLE_VERSION_CHECK="0",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               METIS_TEST_AZURITE_BLOB_ENDPOINT=AZURITE_BLOB_ENDPOINT)
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


def run_redteam(rt_dir: Path) -> int:
    """Red-team pytest on the job dir; same env allowlist and isolation gate as run_tests."""
    env = sandbox_environment(postgres=True)
    env["PYTEST_ADDOPTS"] = "-p no:cacheprovider"
    assert_isolated_network()
    return subprocess.call([sys.executable, "-m", "pytest", "-q", "--rootdir", str(rt_dir), str(rt_dir)],
                           cwd=ROOT, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    commands.add_parser("scan")
    commands.add_parser("rt", help="Red-team pytest on /sandbox-control/rt (read-only; isolation gate first).")
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
    if args.command == "rt":
        return run_redteam(CONTROL_DIR / "rt")
    return run_tests(local=args.local)


if __name__ == "__main__":
    raise SystemExit(main())
