"""Executable sandbox boundary contract; actual Docker enforcement needs runtime proof.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import errno
import os
import socket
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import security_sandbox as sandbox


def test_application_does_not_inherit_production_credentials():
    with patch.dict(os.environ, {
        "PATH": "/usr/bin", "METIS_CANONICAL_STORE": "postgres",
        "PGHOST": "production.example", "AZURE_CLIENT_SECRET": "synthetic-secret",
        "METIS_ENTRA_CLIENT_SECRET": "synthetic-secret", "GH_TOKEN": "synthetic-secret",
    }, clear=True):
        env = sandbox.sandbox_environment(postgres=True)
    assert env["METIS_TEST_POSTGRES_DSN"] == sandbox.TEST_DSN
    assert not {"METIS_CANONICAL_STORE", "PGHOST", "AZURE_CLIENT_SECRET",
                "METIS_ENTRA_CLIENT_SECRET", "GH_TOKEN"} & env.keys()


def test_external_database_is_rejected_before_any_test_runs(monkeypatch):
    monkeypatch.setenv("METIS_TEST_POSTGRES_DSN", "postgresql://production.example/metis")
    with patch.object(subprocess, "call") as tests:
        with pytest.raises(SystemExit, match="Refusing non-sandbox"):
            sandbox.run_tests(local=True)
    tests.assert_not_called()


def routes(monkeypatch, *, ipv4="", ipv6=""):
    original_read = Path.read_text
    def read(path, *args, **kwargs):
        if str(path) == "/proc/net/route":
            return "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n" + ipv4
        if str(path) == "/proc/net/ipv6_route":
            return ipv6
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)


@pytest.mark.parametrize("mode", ["ipv4", "ipv6"])
def test_default_route_rejected_before_connecting(monkeypatch, mode):
    routes(monkeypatch,
           ipv4="eth0 00000000 0100000A 0003 0 0 0 00000000 0 0 0\n" if mode == "ipv4" else "",
           ipv6="0"*32 + " 00 " + "0"*32 + " 00 " + "0"*32 + " 00000000 00000000 00000000 00000003 eth0\n" if mode == "ipv6" else "")
    with patch.object(socket, "create_connection") as connection:
        with pytest.raises(SystemExit, match="external/default"):
            sandbox.assert_isolated_network()
    connection.assert_not_called()


def test_internal_route_and_unreachable_probe_pass(monkeypatch):
    routes(monkeypatch, ipv4="eth0 00FE1EAC 00000000 0001 0 0 0 00FFFFFF 0 0 0\n")
    with patch.object(socket, "create_connection", side_effect=OSError(errno.ENETUNREACH, "unreachable")):
        sandbox.assert_isolated_network()


INTERNAL_DEFAULT = "eth0 00000000 01FE1EAC 0003 0 0 0 00000000 0 0 0\n"


@pytest.mark.parametrize("probe", [OSError(errno.EHOSTUNREACH, "unreachable"), TimeoutError("timeout")])
def test_internal_gateway_default_route_passes_when_egress_and_dns_fail(monkeypatch, probe):
    routes(monkeypatch, ipv4=INTERNAL_DEFAULT)
    with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("no dns")), \
         patch.object(socket, "create_connection", side_effect=probe):
        sandbox.assert_isolated_network()


def test_internal_gateway_default_route_rejected_when_dns_resolves(monkeypatch):
    routes(monkeypatch, ipv4=INTERNAL_DEFAULT)
    with patch.object(socket, "getaddrinfo", return_value=[("ok",)]), \
         patch.object(socket, "create_connection") as connection:
        with pytest.raises(SystemExit, match="DNS"):
            sandbox.assert_isolated_network()
    connection.assert_not_called()


def test_internal_gateway_default_route_rejected_when_egress_connects(monkeypatch):
    routes(monkeypatch, ipv4=INTERNAL_DEFAULT)
    with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("no dns")), \
         patch.object(socket, "create_connection"):
        with pytest.raises(SystemExit, match="reachable"):
            sandbox.assert_isolated_network()


@pytest.mark.parametrize("result", [None, TimeoutError("timeout")])
def test_reachable_or_uncertain_probe_blocks_tests(monkeypatch, result):
    routes(monkeypatch)
    monkeypatch.delenv("METIS_TEST_POSTGRES_DSN", raising=False)
    with patch.object(socket, "create_connection", side_effect=result), patch.object(subprocess, "call") as tests:
        with pytest.raises(SystemExit, match="reachable|unconfirmed"):
            sandbox.run_tests(local=True)
    tests.assert_not_called()


def test_supplied_skill_preserves_observe_only_and_offline_contract():
    skill = sandbox.ROOT / ".agents/skills/metis-vuln-discovery"
    text = (skill / "SKILL.md").read_text()
    assert "Observe and propose only" in text
    assert "no production network access" in text
    assert "security_sandbox.py check" in text
    assert "Stop immediately if isolation cannot be confirmed" in text
    for name in ("domain-rules.md", "example-report.md", "static-patterns.md"):
        assert (skill / "references" / name).is_file()
