"""Security harden (ROADMAP wave 3) + Post-#120 SSRF connection bind.

URL-ingest MUST fail-closed on SSRF to internal destinations and on
redirects to those destinations, while still respecting wave-2 size
limits (`CONSOLE_INGEST_MAX_BYTES`). After those destination checks,
connect MUST bind to the validated IP (Host + TLS hostname stay the
original name). Re-validate and re-bind on every redirect hop — no
silent DNS-rebinding between resolve and connect. Sessions MUST expire
with real enforcement (expired tokens rejected; still invalid after
process restart). Login Set-Cookie MUST include Secure (keep
HttpOnly/SameSite). Concurrent login/logout MUST NOT lose session data.
Session persist joins wave-1 store patterns (lock / atomic replace /
fail-closed). PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here.
publish() stays G2-BLOCKED. Wave 4 metrics/gold and wave 5 simplify
stay out of scope.

Multiuser session-store checklist: concurrency, interrupt, retry,
version-compat.

# release-control-evidence: toegang
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: beschikbaarheid
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import ipaddress
import json
import socket
import ssl
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import Request

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import COOKIE, create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole, default_url_fetcher


ROOT = Path(__file__).resolve().parents[1]
URL_DESTINATION_NOT_ALLOWED = "url_destination_not_allowed"
INGEST_PAYLOAD_TOO_LARGE = "ingest_payload_too_large"
ENV_INGEST_MAX_BYTES = "CONSOLE_INGEST_MAX_BYTES"

INTERNAL_URLS = (
    "http://127.0.0.1/latest/meta-data",
    "http://localhost/admin",
    "http://[::1]/",
    "http://10.0.0.8/internal.pdf",
    "http://172.16.5.4/doc.pdf",
    "http://192.168.1.10/doc.pdf",
    "http://169.254.169.254/latest/meta-data",
    "http://169.254.1.1/link-local",
    "http://100.100.100.200/latest/meta-data",
    "http://metadata.google.internal/computeMetadata/v1/",
    "https://127.0.0.1:8443/secret",
)

# Public-looking pins (not RFC1918/TEST-NET — those count as private
# in ipaddress). The harness never opens a real socket to them or to the
# private rebound answer; only the validated pin is rewritten to the
# local PDF server.
PDF_BODY = b"%PDF-1.4 connection-bind\n"
PUBLIC_PIN_A = "8.8.8.8"
PUBLIC_PIN_B = "1.1.1.1"
PRIVATE_REBIND = "169.254.169.254"
REBIND_HOST = "rebind.example.test"
HOP_HOST = "hop.example.test"

pytestmark = [
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_beschikbaarheid,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def _accounts(console: OperationsConsole) -> dict[str, dict]:
    researcher = console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher", "reviewer"),
        display_name="Anne Onderzoeker",
    )
    reviewer = console.create_account(
        username="reviewer.bert",
        password="bert-secret",
        roles=("reviewer",),
        display_name="Bert Reviewer",
    )
    second = console.create_account(
        username="researcher.dirk",
        password="dirk-secret",
        roles=("researcher", "reviewer"),
        display_name="Dirk Onderzoeker",
    )
    return {"researcher": researcher, "reviewer": reviewer, "second": second}


def _assert_url_destination_allowed(url: str) -> None:
    from src.ingest_limits_v1 import assert_url_destination_allowed

    assert_url_destination_allowed(url)


def _ingest_redirect_handler():
    from src.ingest_limits_v1 import IngestRedirectHandler

    return IngestRedirectHandler()


class _PdfHandler(BaseHTTPRequestHandler):
    hosts: list[str]
    paths: list[str]
    redirect_to: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        type(self).hosts.append(self.headers.get("Host") or "")
        type(self).paths.append(self.path)
        if type(self).redirect_to and self.path in {"/start", "/redir"}:
            self.send_response(302)
            self.send_header("Location", type(self).redirect_to)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(PDF_BODY)))
        self.end_headers()
        self.wfile.write(PDF_BODY)

    def log_message(self, *_args) -> None:
        return


def _serve_pdf(*, redirect_to: str | None = None) -> tuple[HTTPServer, type[_PdfHandler]]:
    location = redirect_to

    class Handler(_PdfHandler):
        hosts = []
        paths = []
        redirect_to = location

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, Handler


def _install_alternating_dns(
    monkeypatch: pytest.MonkeyPatch,
    *,
    answers: dict[str, list[str]],
    connect_log: list[str],
    local_port: int,
) -> None:
    """Alternate DNS answers. Connect to a private IP is refused here.

    A connect to a documented public pin is rewritten to the local server
    so the test never attacks a real internal network.
    """
    from src.ingest_limits_v1 import _ip_is_blocked

    remaining = {key.lower(): list(value) for key, value in answers.items()}
    real_cc = socket.create_connection

    def fake_getaddrinfo(host, port, *args, **kwargs):  # noqa: ANN001
        raw = str(host).strip("[]")
        try:
            ipaddress.ip_address(raw)
        except ValueError:
            key = raw.lower()
            if key not in remaining:
                raise socket.gaierror(socket.EAI_NONAME, "test dns")
            pool = remaining[key]
            ip = pool[0] if len(pool) == 1 else pool.pop(0)
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, int(port or 0)))]
        family = socket.AF_INET6 if ":" in raw else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (raw, int(port or 0)))]

    public_pins = {
        ip
        for seq in answers.values()
        for ip in seq
        if not _ip_is_blocked(ipaddress.ip_address(ip))
    }

    def fake_create_connection(address, timeout=None, source_address=None):  # noqa: ANN001
        host, port = address[0], address[1]
        try:
            ip = str(ipaddress.ip_address(str(host).strip("[]")))
            connect_log.append(ip)
        except ValueError:
            connect_log.append(f"hostname:{host}")
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ip = str(infos[0][4][0])
            connect_log.append(ip)
        if _ip_is_blocked(ipaddress.ip_address(ip)):
            raise OSError(f"test harness refused connect to blocked {ip}")
        if ip in public_pins:
            return real_cc(("127.0.0.1", local_port), timeout, source_address)
        return real_cc((ip, port), timeout, source_address)

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", fake_create_connection)


def test_ssrf_rejects_internal_destinations() -> None:
    for url in INTERNAL_URLS:
        with pytest.raises(ConsoleError) as caught:
            _assert_url_destination_allowed(url)
        assert caught.value.code == URL_DESTINATION_NOT_ALLOWED, url
        with pytest.raises(ConsoleError) as caught_fetch:
            default_url_fetcher(url)
        assert caught_fetch.value.code == URL_DESTINATION_NOT_ALLOWED, url


def test_ssrf_redirect_to_internal_destination_is_rejected() -> None:
    handler = _ingest_redirect_handler()
    request = Request("https://example.test/pdf")
    with pytest.raises(ConsoleError) as caught:
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://169.254.169.254/latest/meta-data",
        )
    assert caught.value.code == URL_DESTINATION_NOT_ALLOWED


def test_url_ingest_rejects_loopback_before_download(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    with pytest.raises(ConsoleError) as caught:
        console.ingest(
            actor_id=accounts["researcher"]["account_id"],
            filename=None,
            data=None,
            content_type=None,
            url="http://127.0.0.1:1/secret.pdf",
            ingest_kind="new",
            title="SSRF probe",
            version="1.0",
            date="2025-04-01",
            live_url="https://example.test/ssrf",
            class_="richtlijn",
            family="continentie",
            named_reviewers=[accounts["reviewer"]["account_id"]],
        )
    assert caught.value.code == URL_DESTINATION_NOT_ALLOWED
    assert console.list_envelopes() == []


def test_url_fetch_still_respects_wave2_max_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.ingest_limits_v1 import limited_url_fetcher

    monkeypatch.setenv(ENV_INGEST_MAX_BYTES, "32")

    def huge(_url: str) -> tuple[bytes, str, str]:
        return b"x" * 80, "application/pdf", "huge.pdf"

    wrapped = limited_url_fetcher(huge)
    with pytest.raises(ConsoleError) as caught:
        wrapped("https://example.test/huge.pdf")
    assert caught.value.code == INGEST_PAYLOAD_TOO_LARGE
    source = (ROOT / "src" / "ingest_limits_v1.py").read_text(encoding="utf-8")
    assert "assert_url_destination_allowed" in source
    assert "enforce_ingest_payload_size" in source
    assert "fetch_url_limited" in source


def test_login_cookie_is_secure_httponly_samesite(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    app = create_console_app(console)
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"username": "researcher.anne", "password": "anne-secret"},
        follow_redirects=False,
    )
    assert response.status_code in {303, 302}
    set_cookie = response.headers.get("set-cookie", "")
    assert COOKIE in set_cookie
    lowered = set_cookie.lower()
    assert "secure" in lowered
    assert "httponly" in lowered
    assert "samesite=lax" in lowered


def test_expired_session_rejected_and_stays_invalid_after_restart(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    session = console.authenticate("researcher.anne", "anne-secret")
    token = session["token"]
    assert console.session_account(token)["username"] == "researcher.anne"

    expired_at = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    console._sessions[token]["expires_at"] = expired_at
    console._save_sessions()

    with pytest.raises(ConsoleError) as caught:
        console.session_account(token)
    assert caught.value.code == "not_authenticated"

    restarted = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    with pytest.raises(ConsoleError) as restarted_caught:
        restarted.session_account(token)
    assert restarted_caught.value.code == "not_authenticated"
    stored = json.loads(restarted._sessions_path.read_text(encoding="utf-8"))
    assert token in stored
    assert stored[token]["expires_at"] == expired_at


def test_live_session_survives_process_restart(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    session = console.authenticate("reviewer.bert", "bert-secret")
    restarted = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    account = restarted.session_account(session["token"])
    assert account["username"] == "reviewer.bert"


def test_old_session_without_expires_at_is_invalid_version_compat(tmp_path: Path) -> None:
    """version-compat: pre-wave-3 session rows without expiry MUST NOT stay immortal."""
    console = _console(tmp_path)
    accounts = _accounts(console)
    token = "a" * 64
    payload = {
        token: {
            "token": token,
            "account_id": accounts["researcher"]["account_id"],
            "username": "researcher.anne",
            "roles": ["researcher", "reviewer"],
            "created_at": "2026-01-01T00:00:00Z",
        }
    }
    console._sessions_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    restarted = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    with pytest.raises(ConsoleError) as caught:
        restarted.session_account(token)
    assert caught.value.code == "not_authenticated"


def test_concurrent_login_logout_does_not_lose_sessions(tmp_path: Path) -> None:
    first = _console(tmp_path)
    _accounts(first)
    second = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []
    tokens: dict[str, str] = {}

    def login(console: OperationsConsole, username: str, password: str, key: str) -> None:
        try:
            barrier.wait(timeout=5)
            session = console.authenticate(username, password)
            tokens[key] = session["token"]
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    threads = [
        threading.Thread(target=login, args=(first, "researcher.anne", "anne-secret", "anne")),
        threading.Thread(target=login, args=(second, "researcher.dirk", "dirk-secret", "dirk")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive()
    assert errors == []
    assert set(tokens) == {"anne", "dirk"}

    third = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    assert third.session_account(tokens["anne"])["username"] == "researcher.anne"
    assert third.session_account(tokens["dirk"])["username"] == "researcher.dirk"

    logout_barrier = threading.Barrier(2)

    def logout_anne() -> None:
        try:
            logout_barrier.wait(timeout=5)
            first.logout(tokens["anne"])
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    def login_bert() -> None:
        try:
            logout_barrier.wait(timeout=5)
            session = second.authenticate("reviewer.bert", "bert-secret")
            tokens["bert"] = session["token"]
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    pair = [threading.Thread(target=logout_anne), threading.Thread(target=login_bert)]
    for thread in pair:
        thread.start()
    for thread in pair:
        thread.join(timeout=15)
        assert not thread.is_alive()
    assert errors == []

    fourth = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    with pytest.raises(ConsoleError) as caught:
        fourth.session_account(tokens["anne"])
    assert caught.value.code == "not_authenticated"
    assert fourth.session_account(tokens["dirk"])["username"] == "researcher.dirk"
    assert fourth.session_account(tokens["bert"])["username"] == "reviewer.bert"


def test_session_store_interrupt_does_not_leave_torn_or_empty_file(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    session = console.authenticate("researcher.anne", "anne-secret")
    path = console._sessions_path
    before = path.read_text(encoding="utf-8")
    assert before.strip()
    before_payload = json.loads(before)

    real_write_bytes = Path.write_bytes
    real_open = open

    def _write_kind(candidate: Path | str) -> str | None:
        try:
            resolved = Path(candidate).resolve()
        except OSError:
            return None
        if resolved == path.resolve():
            return "dest"
        if resolved.parent == path.parent and resolved.suffix == ".tmp":
            return "tmp"
        return None

    def interrupt_write_bytes(self, data):
        kind = _write_kind(self)
        if kind in {"dest", "tmp"}:
            raise OSError("interrupted")
        return real_write_bytes(self, data)

    def interrupt_open(file, mode="r", *args, **kwargs):
        writable = any(flag in str(mode) for flag in ("w", "a", "x", "+"))
        kind = _write_kind(file) if writable else None
        if kind in {"dest", "tmp"}:
            raise OSError("interrupted")
        return real_open(file, mode, *args, **kwargs)

    Path.write_bytes = interrupt_write_bytes  # type: ignore[method-assign]
    try:
        import builtins

        builtins.open = interrupt_open  # type: ignore[assignment]
        with pytest.raises(OSError, match="interrupted"):
            console.authenticate("researcher.dirk", "dirk-secret")
    finally:
        Path.write_bytes = real_write_bytes  # type: ignore[method-assign]
        import builtins

        builtins.open = real_open  # type: ignore[assignment]

    after = path.read_text(encoding="utf-8")
    assert after == before
    assert json.loads(after) == before_payload
    restarted = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    assert restarted.session_account(session["token"])["username"] == "researcher.anne"


def test_session_store_retries_after_stale_failed_write(tmp_path: Path) -> None:
    console = _console(tmp_path)
    _accounts(console)
    calls = {"n": 0}
    real_save = console._save_sessions

    def flaky_save() -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("stale handle")
        return real_save()

    console._save_sessions = flaky_save  # type: ignore[method-assign]
    session = console.authenticate("researcher.anne", "anne-secret")
    assert calls["n"] >= 2
    assert console.session_account(session["token"])["username"] == "researcher.anne"
    restarted = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    assert restarted.session_account(session["token"])["username"] == "researcher.anne"


def test_password_hashing_is_not_weakened() -> None:
    text = (ROOT / "src" / "operations_console_v1.py").read_text(encoding="utf-8")
    assert "pbkdf2_hmac" in text
    assert "compare_digest" in text
    assert "PBKDF2_ROUNDS = 80_000" in text


def test_redirect_server_hop_to_metadata_is_rejected() -> None:
    """Live hop: public-looking first URL is not required; Location is internal."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data")
            self.end_headers()

        def log_message(self, *_args) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/start"
    try:
        with pytest.raises(ConsoleError) as caught:
            default_url_fetcher(url)
        assert caught.value.code == URL_DESTINATION_NOT_ALLOWED
    finally:
        server.shutdown()
        server.server_close()


def test_ssrf_dns_rebind_pins_connect_to_validated_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve returns a public pin, later answers rebound private.

    Connect MUST use the validated IP (not the rebound private). Host
    stays the original hostname. No real internal connect is attempted.
    """
    server, handler = _serve_pdf()
    connect_log: list[str] = []
    try:
        port = server.server_port
        _install_alternating_dns(
            monkeypatch,
            answers={REBIND_HOST: [PUBLIC_PIN_A, PRIVATE_REBIND]},
            connect_log=connect_log,
            local_port=port,
        )
        data, content_type, filename = default_url_fetcher(
            f"http://{REBIND_HOST}:{port}/doc.pdf"
        )
        assert data == PDF_BODY
        assert "pdf" in content_type.lower()
        assert filename == "doc.pdf"
        assert PUBLIC_PIN_A in connect_log
        assert PRIVATE_REBIND not in connect_log
        assert any(entry.startswith("hostname:") for entry in connect_log) is False
        assert handler.hosts
        host_header = handler.hosts[0]
        assert host_header.split(":")[0] == REBIND_HOST
        assert PUBLIC_PIN_A not in host_header
    finally:
        server.shutdown()
        server.server_close()


def test_ssrf_dns_rebind_never_connects_to_private_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even if the implementation fails closed instead of pinning, the
    private rebound IP MUST NOT be the connect target.
    """
    server, _handler = _serve_pdf()
    connect_log: list[str] = []
    try:
        port = server.server_port
        _install_alternating_dns(
            monkeypatch,
            answers={REBIND_HOST: [PUBLIC_PIN_A, PRIVATE_REBIND]},
            connect_log=connect_log,
            local_port=port,
        )
        try:
            default_url_fetcher(f"http://{REBIND_HOST}:{port}/doc.pdf")
        except ConsoleError as exc:
            assert exc.code in {URL_DESTINATION_NOT_ALLOWED, "url_snapshot_failed"}
            # url_snapshot_failed is only acceptable if we never touched private.
        assert PRIVATE_REBIND not in connect_log
    finally:
        server.shutdown()
        server.server_close()


def test_ssrf_https_sni_stays_original_hostname_when_dns_rebinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TLS hostname/SNI MUST stay the original name, not the pinned IP."""
    recorded_sni: list[str | None] = []

    def spy_wrap(self, sock, *args, server_hostname=None, **kwargs):  # noqa: ANN001
        recorded_sni.append(server_hostname)
        return sock

    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", spy_wrap)
    server, handler = _serve_pdf()
    connect_log: list[str] = []
    try:
        port = server.server_port
        _install_alternating_dns(
            monkeypatch,
            answers={REBIND_HOST: [PUBLIC_PIN_A, PRIVATE_REBIND]},
            connect_log=connect_log,
            local_port=port,
        )
        data, content_type, _filename = default_url_fetcher(
            f"https://{REBIND_HOST}:{port}/doc.pdf"
        )
        assert data == PDF_BODY
        assert "pdf" in content_type.lower()
        assert recorded_sni
        assert recorded_sni[0] == REBIND_HOST
        assert PUBLIC_PIN_A not in (recorded_sni[0] or "")
        assert PRIVATE_REBIND not in connect_log
        assert handler.hosts
        assert handler.hosts[0].split(":")[0] == REBIND_HOST
    finally:
        server.shutdown()
        server.server_close()


def test_ssrf_redirect_hop_revalidates_and_rebinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each redirect hop is resolved, validated, and bound again."""
    server, handler = _serve_pdf()
    connect_log: list[str] = []
    try:
        port = server.server_port
        handler.redirect_to = f"http://{HOP_HOST}:{port}/doc.pdf"
        _install_alternating_dns(
            monkeypatch,
            answers={
                REBIND_HOST: [PUBLIC_PIN_A],
                HOP_HOST: [PUBLIC_PIN_B, PRIVATE_REBIND],
            },
            connect_log=connect_log,
            local_port=port,
        )
        data, _content_type, filename = default_url_fetcher(
            f"http://{REBIND_HOST}:{port}/start"
        )
        assert data == PDF_BODY
        assert filename == "doc.pdf"
        assert PUBLIC_PIN_A in connect_log
        assert PUBLIC_PIN_B in connect_log
        assert PRIVATE_REBIND not in connect_log
        assert any(entry.startswith("hostname:") for entry in connect_log) is False
        assert handler.hosts[0].split(":")[0] == REBIND_HOST
        assert handler.hosts[-1].split(":")[0] == HOP_HOST
        assert PUBLIC_PIN_B not in handler.hosts[-1]
    finally:
        server.shutdown()
        server.server_close()


def test_ssrf_redirect_from_pinned_public_to_metadata_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hop whose Location is metadata/private MUST fail closed."""
    server, handler = _serve_pdf()
    connect_log: list[str] = []
    try:
        port = server.server_port
        handler.redirect_to = "http://169.254.169.254/latest/meta-data"
        _install_alternating_dns(
            monkeypatch,
            answers={REBIND_HOST: [PUBLIC_PIN_A]},
            connect_log=connect_log,
            local_port=port,
        )
        with pytest.raises(ConsoleError) as caught:
            default_url_fetcher(f"http://{REBIND_HOST}:{port}/start")
        assert caught.value.code == URL_DESTINATION_NOT_ALLOWED
        assert PRIVATE_REBIND not in connect_log
    finally:
        server.shutdown()
        server.server_close()
