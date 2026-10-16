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
import json
from unittest.mock import MagicMock, patch

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
    # UDP-probe volgt dezelfde gepatchte create_connection als de TCP-doelen.
    monkeypatch.setattr(sandbox, "_udp_reach", lambda address: socket.create_connection(address, timeout=2))


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
def test_internal_gateway_default_route_passes_when_egress_and_dns_fail(monkeypatch, tmp_path, probe):
    routes(monkeypatch, ipv4=INTERNAL_DEFAULT)
    attest(monkeypatch, tmp_path, ATTEST_OK)  # #653: gateway-route alleen met attestatie
    with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("no dns")), \
         patch.object(socket, "create_connection", side_effect=probe):
        sandbox.assert_isolated_network()


def test_internal_gateway_default_route_rejected_when_dns_resolves(monkeypatch, tmp_path):
    routes(monkeypatch, ipv4=INTERNAL_DEFAULT)
    attest(monkeypatch, tmp_path, ATTEST_OK)  # #653: gateway-route alleen met attestatie
    with patch.object(socket, "getaddrinfo", return_value=[("ok",)]), \
         patch.object(socket, "create_connection") as connection:
        with pytest.raises(SystemExit, match="DNS"):
            sandbox.assert_isolated_network()
    connection.assert_not_called()


def test_internal_gateway_default_route_rejected_when_egress_connects(monkeypatch, tmp_path):
    routes(monkeypatch, ipv4=INTERNAL_DEFAULT)
    attest(monkeypatch, tmp_path, ATTEST_OK)  # #653: gateway-route alleen met attestatie
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


def test_offline_assets_pass_through_and_hub_is_forced_offline(monkeypatch):
    monkeypatch.delenv("METIS_TEST_POSTGRES_DSN", raising=False)
    monkeypatch.delenv("METIS_TEST_AZURITE_BLOB_ENDPOINT", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "/opt/ms-playwright")
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "prod")
    env = sandbox.sandbox_environment(postgres=True)
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == "/opt/ms-playwright"
    assert env["HF_HUB_OFFLINE"] == "1" and env["TRANSFORMERS_OFFLINE"] == "1"
    assert "172.30.254.30:10000" in env["METIS_TEST_AZURITE_BLOB_ENDPOINT"]
    assert "AZURE_STORAGE_CONNECTION_STRING" not in env


def test_external_blob_store_is_rejected(monkeypatch):
    monkeypatch.delenv("METIS_TEST_POSTGRES_DSN", raising=False)
    monkeypatch.setenv("METIS_TEST_AZURITE_BLOB_ENDPOINT", "https://prod.blob.core.windows.net/")
    with pytest.raises(SystemExit, match="Refusing non-sandbox METIS_TEST_AZURITE"):
        sandbox.sandbox_environment()


def test_redteam_job_asserts_isolation_before_pytest(monkeypatch, tmp_path):
    # Thread T6: rt MOET dezelfde netwerkpoort passeren als test/scan, in dezelfde job.
    monkeypatch.delenv("METIS_TEST_POSTGRES_DSN", raising=False)
    monkeypatch.delenv("METIS_TEST_AZURITE_BLOB_ENDPOINT", raising=False)
    with patch.object(sandbox, "assert_isolated_network", side_effect=SystemExit("egress")), \
         patch.object(subprocess, "call") as tests:
        with pytest.raises(SystemExit, match="egress"):
            sandbox.run_redteam(tmp_path)
    tests.assert_not_called()


def test_redteam_job_runs_pytest_with_allowlisted_env_after_isolation(monkeypatch, tmp_path):
    monkeypatch.delenv("METIS_TEST_POSTGRES_DSN", raising=False)
    monkeypatch.delenv("METIS_TEST_AZURITE_BLOB_ENDPOINT", raising=False)
    monkeypatch.setenv("GH_TOKEN", "synthetic-secret")
    with patch.object(sandbox, "assert_isolated_network") as gate, \
         patch.object(subprocess, "call", return_value=0) as tests:
        assert sandbox.run_redteam(tmp_path) == 0
    gate.assert_called_once()
    command, env = tests.call_args.args[0], tests.call_args.kwargs["env"]
    assert command[-1] == str(tmp_path) and "--rootdir" in command
    assert env["METIS_TEST_POSTGRES_DSN"] == sandbox.TEST_DSN and "GH_TOKEN" not in env


@pytest.mark.parametrize("error", [socket.gaierror("no dns"), OSError(errno.ENETUNREACH, "x"),
                                   OSError(errno.EHOSTUNREACH, "x")])
def test_probe_accepts_only_explicit_unreachable_errors(error):
    # Thread T4: een timeout of TLS-fout MAG NIET als isolatiebewijs gelden.
    import urllib.error
    assert sandbox.egress_error_is_explicit(error)
    assert sandbox.egress_error_is_explicit(urllib.error.URLError(error))


@pytest.mark.parametrize("error", [TimeoutError("timeout"), OSError(errno.ECONNREFUSED, "x"),
                                   ConnectionResetError("tls")])
def test_probe_rejects_timeouts_and_other_failures(error):
    import ssl
    import urllib.error
    assert not sandbox.egress_error_is_explicit(error)
    assert not sandbox.egress_error_is_explicit(urllib.error.URLError(error))
    assert not sandbox.egress_error_is_explicit(urllib.error.URLError(ssl.SSLError("cert")))


MOUNTINFO_RO = "1 0 0:1 / / ro,relatime - overlay overlay rw,lowerdir=x\n22 1 0:2 / /tmp rw - tmpfs tmpfs rw\n"
MOUNTINFO_RW = "1 0 0:1 / / rw,relatime - overlay overlay rw,lowerdir=x\n22 1 0:2 / /tmp rw - tmpfs tmpfs rw\n"


def test_root_readonly_check_uses_mount_flags_not_permissions():
    # Thread T11: EACCES als niet-root bewijst niets; de mountvlag MOET 'ro' zijn.
    assert sandbox.mount_is_readonly(MOUNTINFO_RO, "/")
    assert not sandbox.mount_is_readonly(MOUNTINFO_RW, "/")
    assert not sandbox.mount_is_readonly(MOUNTINFO_RO, "/missing")


def test_runner_routes_rt_through_security_sandbox_gate():
    runner = (sandbox.ROOT / "scripts/sandbox_runner.sh").read_text()
    assert "python scripts/security_sandbox.py $cmd" in runner
    assert "subprocess.call" not in runner


def test_probe_uses_mount_flags_and_explicit_egress_errors():
    probe = (sandbox.ROOT / "scripts/sandbox_probe.sh").read_text()
    assert "touch /.ro-probe" not in probe
    assert "mount_is_readonly" in probe and "egress_error_is_explicit" in probe


# --- #653 T10: timeout alleen met host-attestatie van een intern netwerk -------------

ATTEST_OK = [{"Name": "metis-sandbox", "Internal": True,
              "IPAM": {"Config": [{"Subnet": "172.30.254.0/24", "Gateway": "172.30.254.1"}]}}]


def attest(monkeypatch, tmp_path, payload):
    path = tmp_path / "network.json"
    if payload is not None:
        path.write_text(payload if isinstance(payload, str) else json.dumps(payload))
    monkeypatch.setattr(sandbox, "ATTEST_FILE", path)


def test_attested_internal_network_with_all_targets_timing_out_passes(monkeypatch, tmp_path, capsys):
    routes(monkeypatch, ipv4=INTERNAL_DEFAULT)
    attest(monkeypatch, tmp_path, ATTEST_OK)
    with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("no dns")), \
         patch.object(socket, "create_connection", side_effect=TimeoutError("timeout")) as connection:
        sandbox.assert_isolated_network()
    targets = {call.args[0] for call in connection.call_args_list}
    assert {("1.1.1.1", 443), ("8.8.8.8", 53), ("2606:4700:4700::1111", 443)} <= targets
    assert "isolated_by_internal_network_attested" in capsys.readouterr().out


@pytest.mark.parametrize("payload", [None, "not json", [{**ATTEST_OK[0], "Internal": False}],
                                     [{**ATTEST_OK[0], "IPAM": {"Config": [{"Subnet": "10.0.0.0/8"}]}}],
                                     [{**ATTEST_OK[0], "Name": "bridge"}]])
def test_timeout_without_valid_internal_attestation_is_refused(monkeypatch, tmp_path, payload):
    # Niet-intern netwerk met geblokkeerde route: timeout alleen MAG NOOIT volstaan.
    routes(monkeypatch, ipv4=INTERNAL_DEFAULT)
    attest(monkeypatch, tmp_path, payload)
    with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("no dns")), \
         patch.object(socket, "create_connection", side_effect=TimeoutError("timeout")):
        with pytest.raises(SystemExit, match="attest"):
            sandbox.assert_isolated_network()


def test_any_reachable_target_refuses_even_when_attested(monkeypatch, tmp_path):
    routes(monkeypatch, ipv4=INTERNAL_DEFAULT)
    attest(monkeypatch, tmp_path, ATTEST_OK)

    def connect(address, timeout=None):
        if address == ("8.8.8.8", 53):
            return MagicMock()
        raise TimeoutError("timeout")
    with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("no dns")), \
         patch.object(socket, "create_connection", side_effect=connect):
        with pytest.raises(SystemExit, match="reachable"):
            sandbox.assert_isolated_network()


def test_udp_target_is_probed(monkeypatch, tmp_path):
    routes(monkeypatch, ipv4=INTERNAL_DEFAULT)
    attest(monkeypatch, tmp_path, ATTEST_OK)
    monkeypatch.setattr(sandbox, "_udp_reach", lambda address: b"answer")
    with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("no dns")), \
         patch.object(socket, "create_connection", side_effect=TimeoutError("timeout")):
        with pytest.raises(SystemExit, match="reachable"):
            sandbox.assert_isolated_network()


def test_initialize_command_attests_internal_network_on_host():
    config = json.loads((sandbox.ROOT / ".devcontainer/devcontainer.json").read_text())
    command = config["initializeCommand"]
    assert "docker network create --internal --subnet 172.30.254.0/24 metis-sandbox" in command
    assert "docker network inspect metis-sandbox > output/runtime/sandbox-attest/network.json" in command
    compose = (sandbox.ROOT / ".devcontainer/compose.yml").read_text()
    assert "../output/runtime/sandbox-attest:/sandbox-attest:ro" in compose
    assert "name: metis-sandbox" in compose and "external: true" in compose


# --- #653 T5: verdict alleen uit het control-volume -----------------------------------

def test_runner_and_workspace_mount_control_volume_read_only():
    compose = (sandbox.ROOT / ".devcontainer/compose.yml").read_text()
    assert compose.count("sandbox_control:/sandbox-control:ro") == 2  # runner + workspace
    assert compose.count("sandbox_control:/sandbox-control:rw") == 1  # control only
    control = compose.split("  control:\n", 1)[1].split("\n  sandbox-", 1)[0]
    assert "network_mode: none" in control and "read_only: true" in control
    runner = compose.split("  runner:\n", 1)[1].split("\n  control:", 1)[0]
    assert "sandbox-requests" not in runner


def test_tested_code_cannot_overwrite_control_files(tmp_path):
    from scripts import sandbox_control as control
    jobs = tmp_path / "control" / "jobs"
    jobs.mkdir(parents=True)
    for name in ("ready", "jobs/1.exit", "jobs/1.log"):
        (tmp_path / "control" / name).write_text("x")
    control.seal_for_tests(tmp_path / "control")  # simuleert de :ro-mount in de runner
    try:
        for name in ("ready", "jobs/1.exit", "jobs/1.log", "jobs/2.exit"):
            with pytest.raises(OSError) as raised:
                (tmp_path / "control" / name).write_text("0")
            assert raised.value.errno in {errno.EROFS, errno.EACCES}
    finally:
        control.unseal_for_tests(tmp_path / "control")


@pytest.mark.parametrize("rc", ["", "0 forged", "abc", "-1x"])
def test_unparseable_runner_result_counts_as_failed(tmp_path, rc):
    from scripts import sandbox_control as control
    ctl, art = tmp_path / "control", tmp_path / "artifacts"
    (ctl / "jobs").mkdir(parents=True); art.mkdir()
    (ctl / "jobs" / "7.request").write_text("test")
    (art / "7.rc").write_text(rc); (art / "7.log").write_text("log")
    assert control.publish(ctl, art, "7") is True
    assert (ctl / "jobs" / "7.exit").read_text().strip() == "1"
    assert not (ctl / "jobs" / "7.request").exists()


def test_valid_runner_result_is_copied_and_pending_job_has_no_verdict(tmp_path):
    from scripts import sandbox_control as control
    ctl, art = tmp_path / "control", tmp_path / "artifacts"
    (ctl / "jobs").mkdir(parents=True); art.mkdir()
    assert control.publish(ctl, art, "8") is False and not (ctl / "jobs" / "8.exit").exists()
    (art / "8.rc").write_text("3\n"); (art / "8.log").write_text("hello")
    assert control.publish(ctl, art, "8") is True
    assert (ctl / "jobs" / "8.exit").read_text().strip() == "3"
    assert (ctl / "jobs" / "8.log").read_text() == "hello"


def test_ready_only_with_fresh_runner_heartbeat(tmp_path):
    from scripts import sandbox_control as control
    ctl, art = tmp_path / "control", tmp_path / "artifacts"
    ctl.mkdir(); art.mkdir()
    control.refresh_ready(ctl, art, now=1000.0)
    assert not (ctl / "ready").exists()
    (art / "heartbeat").write_text("995")
    control.refresh_ready(ctl, art, now=1000.0)
    assert (ctl / "ready").exists()
    control.refresh_ready(ctl, art, now=1100.0)
    assert not (ctl / "ready").exists()


def test_dispatch_moves_requests_and_rt_into_control_volume(tmp_path):
    from scripts import sandbox_control as control
    req, ctl = tmp_path / "requests", tmp_path / "control"
    (req / "rt").mkdir(parents=True); ctl.mkdir()
    (req / "rt" / "test_x.py").write_text("def test_x(): pass\n")
    (req / "9.request").write_text("rt")
    control.dispatch(req, ctl)
    assert (ctl / "jobs" / "9.request").read_text() == "rt"
    assert (ctl / "rt" / "test_x.py").exists() and not (req / "9.request").exists()


@pytest.mark.parametrize("code", [errno.EAFNOSUPPORT, errno.EADDRNOTAVAIL])
def test_ipv6_target_without_ipv6_stack_counts_as_unreachable(monkeypatch, code):
    routes(monkeypatch)

    def connect(address, timeout=None):
        if ":" in address[0]:
            raise OSError(code, "no ipv6")
        raise OSError(errno.ENETUNREACH, "unreachable")
    with patch.object(socket, "create_connection", side_effect=connect):
        sandbox.assert_isolated_network()


def test_ipv4_target_with_address_family_error_is_refused(monkeypatch):
    routes(monkeypatch)
    with patch.object(socket, "create_connection", side_effect=OSError(errno.EAFNOSUPPORT, "x")):
        with pytest.raises(SystemExit, match="unconfirmed"):
            sandbox.assert_isolated_network()
