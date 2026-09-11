"""Generated-project runtime smoke test.

Validates that a generated project with an embedded auth module can boot,
migrate, and serve an HTTP route with a successful outcome (2xx/3xx) —
proving generator fidelity without requiring Docker or browser automation.
Requires a running PostgreSQL instance (see AF13 roadmap note).

This test is marked ``@pytest.mark.e2e`` so it is excluded from
``pytest quickscale_core/tests/ -m "not e2e"`` and ``make test-unit``.

Phase 14.3 of the roadmap (Finding 14 — generator-runtime test coverage).
"""

import http.client
import hashlib
import json
import os
import secrets
import shutil
import socket
import ssl
import struct
import subprocess
import textwrap
import threading
import time
import urllib.error
import urllib.request
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator, cast
from urllib.parse import urljoin, urlsplit

import pytest

from quickscale_core.utils.poetry_env import build_isolated_poetry_env

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_LOCAL_ARTIFACT_NAMES = frozenset(
    {
        ".mypy_cache",
        ".pnpm-store",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "coverage.json",
        "coverage.xml",
        "dist",
        "htmlcov",
        "node_modules",
    }
)
REPO_LOCAL_ARTIFACT_SUFFIXES = (".egg-info", ".pyc", ".pyo")


def _is_repo_local_artifact(entry_name: str) -> bool:
    """Return whether a copied repo entry is a local-only artifact."""
    return (
        entry_name in REPO_LOCAL_ARTIFACT_NAMES
        or entry_name == ".coverage"
        or entry_name.startswith(".coverage.")
        or entry_name.endswith(REPO_LOCAL_ARTIFACT_SUFFIXES)
    )


def _ignore_repo_local_artifacts(_directory: str, entries: list[str]) -> list[str]:
    """Filter repo-local caches and coverage artifacts out of smoke-test copies."""
    return [entry for entry in entries if _is_repo_local_artifact(entry)]


def _copytree_for_generated_project_smoke(source: Path, destination: Path) -> None:
    """Copy shipped module content without repo-local test and cache artifacts."""
    shutil.copytree(
        source,
        destination,
        ignore=_ignore_repo_local_artifacts,
    )


def _is_poetry_network_failure(output: str) -> bool:
    """Detect Poetry/PyPI connectivity failures."""
    lowered = output.lower()
    markers = [
        "all attempts to connect to pypi.org failed",
        "hostname cannot be resolved by your dns",
        "your network is not connected to the internet",
        "nameresolutionerror",
        "connection error",
    ]
    return any(marker in lowered for marker in markers)


def _find_free_port() -> int:
    """Find a free port by binding to port 0 and letting the OS assign one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = int(s.getsockname()[1])
    return port


_PROXY_HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "expect",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "proxy-connection",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
_PROXY_MAX_REQUEST_BODY_BYTES = 16 * 1024 * 1024
_PROXY_SOCKET_TIMEOUT_SECONDS = 10
_PROXY_UPSTREAM_TIMEOUT_SECONDS = 10
_PROXY_SHUTDOWN_TIMEOUT_SECONDS = 15


class _TrackedThreadingHTTPServer(ThreadingHTTPServer):
    """Threaded server whose handler threads can be joined deterministically."""

    daemon_threads = True
    block_on_close = False
    request_queue_size = 64

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.handler_threads: set[threading.Thread] = set()
        self.handler_threads_lock = threading.Lock()

    def process_request_thread(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        current_thread = threading.current_thread()
        with self.handler_threads_lock:
            self.handler_threads.add(current_thread)
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.handler_threads_lock:
                self.handler_threads.discard(current_thread)


def _generate_localhost_tls_certificate(tmp_path: Path) -> tuple[Path, Path]:
    """Generate an ephemeral localhost certificate with the reviewed OpenSSL argv."""
    openssl = shutil.which("openssl")
    assert openssl is not None, "OpenSSL is required for the genuine HTTPS proof"

    help_result = subprocess.run(
        [openssl, "req", "-help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    help_output = f"{help_result.stdout}\n{help_result.stderr}"
    required_capabilities = (
        "req",
        "-x509",
        "-newkey",
        "-nodes",
        "-keyout",
        "-out",
        "-days",
        "-subj",
        "-addext",
    )
    missing_capabilities = [
        capability
        for capability in required_capabilities
        if capability not in help_output
    ]
    assert help_result.returncode == 0, (
        f"OpenSSL req capability preflight failed: {help_output}"
    )
    assert not missing_capabilities, (
        "OpenSSL req capability preflight is missing: "
        f"{missing_capabilities!r}\n{help_output}"
    )

    key_path = tmp_path / "localhost.key"
    certificate_path = tmp_path / "localhost.crt"
    result = subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(certificate_path),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        "OpenSSL localhost certificate generation failed:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert key_path.is_file(), "OpenSSL did not create the ephemeral private key"
    assert certificate_path.is_file(), (
        "OpenSSL did not create the ephemeral certificate"
    )
    return key_path, certificate_path


def _certificate_fingerprint(certificate_path: Path) -> str:
    """Return the stable SHA-256 fingerprint for one generated certificate."""
    certificate_der = ssl.PEM_cert_to_DER_cert(certificate_path.read_text())
    return hashlib.sha256(certificate_der).hexdigest()


def _make_https_proxy_handler(
    upstream_host: str,
    upstream_port: int,
    observed_requests: list[dict[str, Any]],
    observed_requests_lock: threading.Lock,
    diagnostics: dict[str, Any] | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Build a handler with a frozen loopback destination for the test proxy."""
    proxy_diagnostics = diagnostics if diagnostics is not None else {}
    proxy_diagnostics.setdefault("expected_peer_departures", 0)
    proxy_diagnostics.setdefault("peer_departure_types", [])
    proxy_diagnostics.setdefault("handler_timeouts", 0)
    proxy_diagnostics.setdefault("unexpected_handler_errors", [])
    proxy_diagnostics.setdefault("upstream_errors", [])
    proxy_diagnostics.setdefault("responses", [])

    class HTTPSProxyHandler(BaseHTTPRequestHandler):
        """Forward browser-origin requests to the already-running HTTP server."""

        # Every downstream response is self-delimiting and closes the connection.
        # Keeping this at HTTP/1.0 avoids an HTTP/1.1 keep-alive/retry race when a
        # browser receives a response after the upstream connection is closed.
        protocol_version = "HTTP/1.0"
        server_version = "QuickScaleSA160Proxy/1.0"
        sys_version = ""

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(_PROXY_SOCKET_TIMEOUT_SECONDS)

        def handle(self) -> None:
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError) as exc:
                self._record_peer_departure(exc)
            except TimeoutError:
                with observed_requests_lock:
                    proxy_diagnostics["handler_timeouts"] += 1
                self.close_connection = True
            except Exception as exc:  # pragma: no cover - defensive server boundary
                with observed_requests_lock:
                    proxy_diagnostics["unexpected_handler_errors"].append(
                        f"{type(exc).__name__}: {exc}"
                    )
                self.close_connection = True

        def do_GET(self) -> None:
            self._run_proxy_request()

        def do_POST(self) -> None:
            self._run_proxy_request()

        def do_HEAD(self) -> None:
            self._reject_request(405, "HEAD is not supported by the test proxy")

        def do_OPTIONS(self) -> None:
            self._reject_request(405, "OPTIONS is not supported by the test proxy")

        def do_PUT(self) -> None:
            self._reject_request(405, "PUT is not supported by the test proxy")

        def do_PATCH(self) -> None:
            self._reject_request(405, "PATCH is not supported by the test proxy")

        def do_DELETE(self) -> None:
            self._reject_request(405, "DELETE is not supported by the test proxy")

        def do_TRACE(self) -> None:
            self._reject_request(405, "TRACE is not supported by the test proxy")

        def do_CONNECT(self) -> None:
            self._reject_request(405, "CONNECT is not supported by the test proxy")

        def _run_proxy_request(self) -> None:
            try:
                self._proxy_request()
            except (BrokenPipeError, ConnectionResetError) as exc:
                self._record_peer_departure(exc)
            except TimeoutError:
                with observed_requests_lock:
                    proxy_diagnostics["handler_timeouts"] += 1
                self.close_connection = True

        def _record_peer_departure(self, exc: BaseException) -> None:
            if getattr(self, "_peer_departure_recorded", False):
                return
            self._peer_departure_recorded = True
            with observed_requests_lock:
                proxy_diagnostics["expected_peer_departures"] += 1
                cast(list[str], proxy_diagnostics["peer_departure_types"]).append(
                    type(exc).__name__
                )
            self.close_connection = True

        def _reject_request(self, status: int, message: str) -> None:
            body = f"{message}\n".encode("utf-8")
            self.close_connection = True
            try:
                self.send_response(status)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError) as exc:
                self._record_peer_departure(exc)

        @staticmethod
        def _connection_tokens(headers: Any) -> set[str]:
            return {
                token.strip().lower()
                for value in headers.get_all("Connection", [])
                for token in value.split(",")
                if token.strip()
            }

        def _read_request_body(self) -> bytes | None:
            transfer_encoding = self.headers.get_all("Transfer-Encoding", [])
            if transfer_encoding:
                self._reject_request(
                    400,
                    "Transfer-Encoding is not supported by the test proxy",
                )
                return None

            content_lengths = self.headers.get_all("Content-Length", [])
            if len(content_lengths) > 1 or (
                content_lengths
                and len({value.strip() for value in content_lengths}) != 1
            ):
                self._reject_request(400, "Conflicting Content-Length headers")
                return None
            if not content_lengths:
                return b""

            try:
                content_length = int(content_lengths[0])
            except ValueError:
                self._reject_request(400, "Invalid Content-Length header")
                return None
            if not 0 <= content_length <= _PROXY_MAX_REQUEST_BODY_BYTES:
                self._reject_request(413, "Request body exceeds the proxy limit")
                return None
            body = self.rfile.read(content_length)
            if len(body) != content_length:
                self._reject_request(400, "Request body was truncated")
                return None
            return body

        def _proxy_request(self) -> None:
            self.close_connection = True
            request_target = self.path
            parsed_target = urlsplit(request_target)
            if (
                not request_target.startswith("/")
                or request_target.startswith("//")
                or parsed_target.scheme
                or parsed_target.netloc
            ):
                self._reject_request(
                    400, "Only origin-form request targets are supported"
                )
                return

            body = self._read_request_body()
            if body is None:
                return

            incoming_headers = {
                name.lower(): value for name, value in self.headers.items()
            }
            with observed_requests_lock:
                observed_requests.append(
                    {
                        "body": body,
                        "headers": incoming_headers,
                        "method": self.command,
                        "target": request_target,
                    }
                )

            connection_tokens = self._connection_tokens(self.headers)
            forwarded_headers: dict[str, str] = {}
            for name, value in self.headers.items():
                lowered_name = name.lower()
                if (
                    lowered_name in _PROXY_HOP_BY_HOP_HEADERS
                    or lowered_name in connection_tokens
                    or lowered_name == "forwarded"
                    or lowered_name.startswith("x-forwarded-")
                ):
                    continue
                forwarded_headers[name] = value
            forwarded_headers["X-Forwarded-Proto"] = "https"

            upstream_connection = http.client.HTTPConnection(
                upstream_host,
                upstream_port,
                timeout=_PROXY_UPSTREAM_TIMEOUT_SECONDS,
            )
            try:
                upstream_connection.request(
                    self.command,
                    request_target,
                    body=body if body or self.headers.get("Content-Length") else None,
                    headers=forwarded_headers,
                )
                upstream_response = upstream_connection.getresponse()
                response_body = upstream_response.read()
                response_headers = upstream_response.getheaders()
            except (http.client.HTTPException, OSError) as exc:
                with observed_requests_lock:
                    cast(list[str], proxy_diagnostics["upstream_errors"]).append(
                        f"{request_target}: {type(exc).__name__}: {exc}"
                    )
                self._reject_request(
                    502, f"Upstream request failed: {type(exc).__name__}"
                )
                return
            finally:
                upstream_connection.close()

            with observed_requests_lock:
                cast(list[dict[str, Any]], proxy_diagnostics["responses"]).append(
                    {
                        "body_length": len(response_body),
                        "header_names": [
                            name.lower() for name, _value in response_headers
                        ],
                        "status": upstream_response.status,
                        "target": request_target,
                    }
                )
            response_connection_tokens = {
                token.strip().lower()
                for name, value in response_headers
                if name.lower() == "connection"
                for token in value.split(",")
                if token.strip()
            }
            self.send_response(upstream_response.status, upstream_response.reason)
            for name, value in response_headers:
                lowered_name = name.lower()
                if (
                    lowered_name in _PROXY_HOP_BY_HOP_HEADERS
                    or lowered_name in response_connection_tokens
                    or lowered_name == "content-length"
                ):
                    continue
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(response_body)))
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                self.wfile.write(response_body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError) as exc:
                self._record_peer_departure(exc)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return HTTPSProxyHandler


@contextmanager
def _https_reverse_proxy(
    tmp_path: Path,
    upstream_url: str,
    observed_requests: list[dict[str, Any]],
    diagnostics: dict[str, Any] | None = None,
) -> Iterator[str]:
    """Serve one bounded genuine-HTTPS session in front of a fixed loopback server."""
    parsed_upstream = urlsplit(upstream_url)
    assert parsed_upstream.scheme == "http"
    assert parsed_upstream.hostname == "127.0.0.1"
    assert parsed_upstream.port is not None
    assert not parsed_upstream.username and not parsed_upstream.password
    assert not parsed_upstream.path and not parsed_upstream.query

    key_path = tmp_path / "localhost.key"
    certificate_path = tmp_path / "localhost.crt"
    observed_requests_lock = threading.Lock()
    proxy_diagnostics = diagnostics if diagnostics is not None else {}
    server: _TrackedThreadingHTTPServer | None = None
    server_thread: threading.Thread | None = None
    server_thread_started = False
    try:
        generated_key_path, generated_certificate_path = (
            _generate_localhost_tls_certificate(tmp_path)
        )
        assert generated_key_path == key_path
        assert generated_certificate_path == certificate_path
        handler = _make_https_proxy_handler(
            parsed_upstream.hostname,
            parsed_upstream.port,
            observed_requests,
            observed_requests_lock,
            proxy_diagnostics,
        )
        server = _TrackedThreadingHTTPServer(("127.0.0.1", 0), handler)
        try:
            # The certificate and context are created once for this proxy session,
            # then reused by every accepted TLS connection.
            tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls_context.load_cert_chain(certificate_path, key_path)
            proxy_diagnostics["certificate_fingerprint_sha256"] = (
                _certificate_fingerprint(certificate_path)
            )
            proxy_diagnostics["certificate_generation_count"] = 1
            proxy_diagnostics["tls_context"] = tls_context
            server.socket = tls_context.wrap_socket(server.socket, server_side=True)
            server_address = cast(tuple[str, int], server.server_address)
            proxy_port = server_address[1]
            server_thread = threading.Thread(
                target=server.serve_forever,
                name="quickscale-sa160-https-proxy",
                daemon=True,
            )
            try:
                server_thread.start()
                server_thread_started = True
                proxy_diagnostics["server_thread"] = server_thread
                yield f"https://localhost:{proxy_port}"
            finally:
                try:
                    if server_thread_started:
                        # Stop accepting first; then close the listening TLS socket,
                        # join the accept loop, and finally join active handlers.
                        server.shutdown()
                finally:
                    try:
                        server.server_close()
                    finally:
                        if server_thread_started and server_thread is not None:
                            server_thread.join(timeout=_PROXY_SHUTDOWN_TIMEOUT_SECONDS)
                            assert not server_thread.is_alive(), (
                                "HTTPS test proxy accept thread did not terminate"
                            )
                        if server is not None:
                            deadline = (
                                time.monotonic() + _PROXY_SHUTDOWN_TIMEOUT_SECONDS
                            )
                            while True:
                                with server.handler_threads_lock:
                                    active_handlers = tuple(server.handler_threads)
                                if not active_handlers:
                                    break
                                remaining = deadline - time.monotonic()
                                if remaining <= 0:
                                    break
                                for handler_thread in active_handlers:
                                    handler_thread.join(timeout=remaining)
                            with server.handler_threads_lock:
                                assert not server.handler_threads, (
                                    "HTTPS test proxy handler threads did not terminate"
                                )
        finally:
            if server is not None and not server_thread_started:
                server.server_close()
    finally:
        key_path.unlink(missing_ok=True)
        certificate_path.unlink(missing_ok=True)


@contextmanager
def _loopback_http_server(
    handler: type[BaseHTTPRequestHandler],
) -> Iterator[str]:
    """Serve a deterministic local upstream and join all of its handlers."""
    server = _TrackedThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="quickscale-sa160-http-upstream",
        daemon=True,
    )
    thread.start()
    try:
        address = cast(tuple[str, int], server.server_address)
        yield f"http://127.0.0.1:{address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=_PROXY_SHUTDOWN_TIMEOUT_SECONDS)
        assert not thread.is_alive(), "Loopback upstream thread did not terminate"
        deadline = time.monotonic() + _PROXY_SHUTDOWN_TIMEOUT_SECONDS
        while True:
            with server.handler_threads_lock:
                active_handlers = tuple(server.handler_threads)
            if not active_handlers:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            for handler_thread in active_handlers:
                handler_thread.join(timeout=remaining)
        with server.handler_threads_lock:
            assert not server.handler_threads, (
                "Loopback upstream handler threads did not terminate"
            )


def test_https_reverse_proxy_uses_bounded_close_framing_and_strips_hop_headers(
    tmp_path: Path,
) -> None:
    """The real TLS proxy emits one close-delimited HTTP/1.0 response."""
    request_data: dict[str, Any] = {}
    response_body = b"framed upstream response"

    class UpstreamHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def _respond(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0"))
            request_data["headers"] = {
                name.lower(): value for name, value in self.headers.items()
            }
            request_data["body"] = self.rfile.read(content_length)
            self.send_response(200)
            self.send_header("Content-Length", str(len(response_body)))
            self.send_header("Connection", "close, X-Upstream-Nominated")
            self.send_header("X-Upstream-Nominated", "must-not-cross")
            self.send_header("Keep-Alive", "timeout=30")
            self.end_headers()
            self.wfile.write(response_body)

        def do_GET(self) -> None:
            self._respond()

        def do_POST(self) -> None:
            self._respond()

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    observed_requests: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    with _loopback_http_server(UpstreamHandler) as upstream_url:
        with _https_reverse_proxy(
            tmp_path,
            upstream_url,
            observed_requests,
            diagnostics,
        ) as proxy_url:
            parsed_proxy = urlsplit(proxy_url)
            assert parsed_proxy.port is not None
            client_context = ssl._create_unverified_context()
            connection = http.client.HTTPSConnection(
                parsed_proxy.hostname,
                parsed_proxy.port,
                context=client_context,
                timeout=_PROXY_SOCKET_TIMEOUT_SECONDS,
            )
            try:
                connection.request(
                    "POST",
                    "/framing",
                    body=b"request body",
                    headers={
                        "Connection": "keep-alive, X-Request-Nominated",
                        "X-Request-Nominated": "must-not-cross",
                        "Keep-Alive": "timeout=30",
                        "TE": "trailers",
                    },
                )
                response = connection.getresponse()
                assert response.version == 10
                response_headers = response.getheaders()
                lowered_response_names = [
                    name.lower() for name, _value in response_headers
                ]
                assert lowered_response_names.count("content-length") == 1
                assert response.getheader("Content-Length") == str(len(response_body))
                assert response.getheader("Connection") == "close"
                assert response.getheader("X-Upstream-Nominated") is None
                assert response.getheader("Keep-Alive") is None
                assert response.getheader("Transfer-Encoding") is None
                assert response.read() == response_body
                assert response.will_close
            finally:
                connection.close()

            assert request_data["body"] == b"request body"
            upstream_headers = request_data["headers"]
            assert "connection" not in upstream_headers
            assert "x-request-nominated" not in upstream_headers
            assert "keep-alive" not in upstream_headers
            assert "te" not in upstream_headers
            assert upstream_headers["x-forwarded-proto"] == "https"
            assert len(observed_requests) == 1
            assert diagnostics["certificate_generation_count"] == 1
            assert len(diagnostics["certificate_fingerprint_sha256"]) == 64

            # A second real TLS connection reuses the same certificate/context and
            # proves the downstream close is observable as EOF, not a retry.
            raw_socket = socket.create_connection(
                (parsed_proxy.hostname, parsed_proxy.port),
                timeout=_PROXY_SOCKET_TIMEOUT_SECONDS,
            )
            tls_socket = client_context.wrap_socket(
                raw_socket,
                server_hostname=parsed_proxy.hostname,
            )
            try:
                tls_socket.sendall(b"GET /eof HTTP/1.1\r\nHost: localhost\r\n\r\n")
                raw_response = bytearray()
                while b"\r\n\r\n" not in raw_response:
                    raw_response.extend(tls_socket.recv(4096))
                assert b"HTTP/1.0 200" in raw_response
                while len(raw_response) < len(
                    response_body
                ) or not raw_response.endswith(response_body):
                    chunk = tls_socket.recv(4096)
                    if not chunk:
                        break
                    raw_response.extend(chunk)
                assert raw_response.endswith(response_body)
                assert tls_socket.recv(1) == b""
            finally:
                tls_socket.close()

        assert not (tmp_path / "localhost.key").exists()
        assert not (tmp_path / "localhost.crt").exists()
        assert not diagnostics["server_thread"].is_alive()
        assert diagnostics["unexpected_handler_errors"] == []


def test_https_reverse_proxy_handles_expected_peer_disconnect_deterministically(
    tmp_path: Path,
) -> None:
    """A client departure after upstream receipt is expected proxy cleanup."""
    request_received = threading.Event()
    release_response = threading.Event()
    upstream_finished = threading.Event()

    class BlockingUpstreamHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_GET(self) -> None:
            request_received.set()
            try:
                assert release_response.wait(_PROXY_SOCKET_TIMEOUT_SECONDS)
                body = b"response after peer departure"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            finally:
                upstream_finished.set()

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    observed_requests: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    try:
        with _loopback_http_server(BlockingUpstreamHandler) as upstream_url:
            started = time.monotonic()
            with _https_reverse_proxy(
                tmp_path,
                upstream_url,
                observed_requests,
                diagnostics,
            ) as proxy_url:
                parsed_proxy = urlsplit(proxy_url)
                assert parsed_proxy.port is not None
                client_context = ssl._create_unverified_context()
                raw_socket = socket.create_connection(
                    (parsed_proxy.hostname, parsed_proxy.port),
                    timeout=_PROXY_SOCKET_TIMEOUT_SECONDS,
                )
                tls_socket = client_context.wrap_socket(
                    raw_socket,
                    server_hostname=parsed_proxy.hostname,
                )
                tls_socket.sendall(
                    b"GET /disconnect HTTP/1.1\r\nHost: localhost\r\n\r\n"
                )
                assert request_received.wait(_PROXY_SOCKET_TIMEOUT_SECONDS)
                # RST makes the peer departure deterministic while the upstream
                # response is still blocked behind the explicit synchronization
                # barrier above.
                tls_socket.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_LINGER,
                    struct.pack("ii", 1, 0),
                )
                tls_socket.close()
                release_response.set()
                assert upstream_finished.wait(_PROXY_SOCKET_TIMEOUT_SECONDS)

            elapsed = time.monotonic() - started
            assert elapsed < _PROXY_SHUTDOWN_TIMEOUT_SECONDS
            assert len(observed_requests) == 1
            assert diagnostics["expected_peer_departures"] >= 1
            assert set(diagnostics["peer_departure_types"]) <= {
                "BrokenPipeError",
                "ConnectionResetError",
            }
            assert diagnostics["unexpected_handler_errors"] == []
            assert not diagnostics["server_thread"].is_alive()
    finally:
        release_response.set()

    assert not (tmp_path / "localhost.key").exists()
    assert not (tmp_path / "localhost.crt").exists()


def _standalone_generated_env(
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a generated-project environment without maintainer provenance."""
    environment = build_isolated_poetry_env()
    for variable in (
        "PYTHONPATH",
        "MYPYPATH",
        "PWD",
        "OLDPWD",
        "DJANGO_SETTINGS_MODULE",
        "QUICKSCALE_PRIVILEGED_COMMAND",
        "QUICKSCALE_ALLOW_BYPASSRLS",
        "QUICKSCALE_LOCAL_WHEELHOUSE",
    ):
        environment.pop(variable, None)
    if overrides:
        environment.update(overrides)
    return environment


def _install_project_dependencies(
    project_path: Path,
    *,
    strict: bool = False,
) -> None:
    """Install dependencies in the generated project using poetry.

    Skips the test when PyPI is unreachable so CI does not fail on
    transient network issues unless ``strict`` is requested by the
    standalone all-module runtime proof.
    """
    poetry_env = _standalone_generated_env() if strict else build_isolated_poetry_env()
    lock_result = subprocess.run(
        ["poetry", "lock"],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=120,
        env=poetry_env,
    )
    lock_output = f"{lock_result.stdout}\n{lock_result.stderr}"
    if (
        not strict
        and lock_result.returncode != 0
        and _is_poetry_network_failure(lock_output)
    ):
        pytest.skip("PyPI is unreachable in this environment")
    assert lock_result.returncode == 0, f"Poetry lock failed: {lock_result.stderr}"

    install_result = subprocess.run(
        ["poetry", "install", "--no-interaction"],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=180,
        env=poetry_env,
    )
    install_output = f"{install_result.stdout}\n{install_result.stderr}"
    if (
        not strict
        and install_result.returncode != 0
        and _is_poetry_network_failure(install_output)
    ):
        pytest.skip("PyPI is unreachable in this environment")
    assert install_result.returncode == 0, (
        f"Poetry install failed: {install_result.stderr}"
    )


def _write_postgres_test_settings(
    project_path: Path,
    project_name: str,
    postgres_url: str,
    cache_database: bool = False,
) -> None:
    """Write a test settings module that uses PostgreSQL.

    Requires a running PostgreSQL instance reachable via *postgres_url*.
    The connection details are embedded directly into the generated
    settings file so that subprocesses do not depend on ambient
    QS_SMOKE_DB_* environment variables.

    When *cache_database* is True, uses DatabaseCache instead of
    LocMemCache so that ``createcachetable`` can be exercised (SA63).
    """
    from urllib.parse import urlparse

    parsed = urlparse(postgres_url)
    db_name = parsed.path.lstrip("/") if parsed.path else "test_db"
    db_user = parsed.username or "test_user"
    db_password = parsed.password or "test_password"
    db_host = parsed.hostname or "localhost"
    db_port = str(parsed.port or 5432)

    cache_backend = (
        "django.core.cache.backends.db.DatabaseCache"
        if cache_database
        else "django.core.cache.backends.locmem.LocMemCache"
    )
    cache_location_line = (
        '        "LOCATION": "django_cache_table",\n' if cache_database else ""
    )

    settings_content = (
        '"""Runtime smoke test settings — uses PostgreSQL."""\n'
        "\n"
        "from .base import *  # noqa: F401, F403\n"
        "\n"
        "DATABASES = {\n"
        '    "default": {\n'
        '        "ENGINE": "django.db.backends.postgresql",\n'
        f'        "NAME": "{db_name}",\n'
        f'        "USER": "{db_user}",\n'
        f'        "PASSWORD": "{db_password}",\n'
        f'        "HOST": "{db_host}",\n'
        f'        "PORT": "{db_port}",\n'
        "    }\n"
        "}\n"
        "\n"
        "DEBUG = False\n"
        'ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]\n'
        "\n"
        "CACHES = {\n"
        '    "default": {\n'
        f'        "BACKEND": "{cache_backend}",\n'
        f"{cache_location_line}"
        "    }\n"
        "}\n"
        "\n"
        "# Override the base settings' manifest-based staticfiles storage\n"
        "# (whitenoise.storage.CompressedManifestStaticFilesStorage) with the simple\n"
        "# in-place backend.  The smoke test does not run ``collectstatic``, so the\n"
        "# manifest file does not exist; without this override, any template\n"
        "# reference to a static asset (e.g. ``images/favicon.svg`` in the auth\n"
        "# login page) raises ``ValueError: Missing staticfiles manifest entry``.\n"
        "# This mirrors the override that ``local.py`` applies for development.\n"
        "STORAGES = {\n"
        '    "default": {\n'
        '        "BACKEND": "django.core.files.storage.FileSystemStorage",\n'
        "    },\n"
        '    "staticfiles": {\n'
        '        "BACKEND": '
        '"django.contrib.staticfiles.storage.StaticFilesStorage",\n'
        "    },\n"
        "}\n"
        "\n"
        "LOGGING = {\n"
        '    "version": 1,\n'
        '    "disable_existing_loggers": False,\n'
        '    "formatters": {\n'
        '        "verbose": {\n'
        '            "format": "{levelname} {asctime} {module} {message}",\n'
        '            "style": "{",\n'
        "        },\n"
        "    },\n"
        '    "handlers": {\n'
        '        "console": {\n'
        '            "class": "logging.StreamHandler",\n'
        '            "formatter": "verbose",\n'
        "        },\n"
        "    },\n"
        '    "root": {\n'
        '        "handlers": ["console"],\n'
        '        "level": "WARNING",\n'
        "    },\n"
        '    "loggers": {\n'
        '        "django": {\n'
        '            "handlers": ["console"],\n'
        '            "level": "WARNING",\n'
        '            "propagate": False,\n'
        "        },\n"
        "    },\n"
        "}\n"
    )
    settings_path = project_path / project_name / "settings" / "test_smoke.py"
    settings_path.write_text(settings_content)


def _create_test_database(postgres_url: str) -> None:
    """Create the test database if it does not exist.

    The database name and connection parameters are extracted from
    *postgres_url* rather than relying on ambient QS_SMOKE_DB_* env vars.
    """
    import psycopg2  # type: ignore[import-untyped]

    from urllib.parse import urlparse

    parsed = urlparse(postgres_url)
    db_name = parsed.path.lstrip("/") if parsed.path else "test_db"
    db_user = parsed.username or "test_user"
    db_password = parsed.password or "test_password"
    db_host = parsed.hostname or "localhost"
    db_port = parsed.port or 5432

    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        dbname="postgres",
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{db_name}"')
    conn.close()


def _postgres_connect_kwargs(
    postgres_service: dict[str, Any],
    *,
    database: str,
    user: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    """Return connection arguments for the pytest-docker PostgreSQL service."""
    return {
        "host": postgres_service["host"],
        "port": postgres_service["port"],
        "dbname": database,
        "user": user if user is not None else postgres_service["user"],
        "password": (
            password if password is not None else postgres_service["password"]
        ),
    }


def _quote_postgres_identifier(value: str) -> str:
    """Quote a generated PostgreSQL identifier without accepting SQL syntax."""
    return '"' + value.replace('"', '""') + '"'


@contextmanager
def _restricted_postgres_database(
    postgres_service: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    """Create and deterministically clean up a restricted, owned database."""
    import psycopg2

    scope = os.environ.get("QS_E2E_CONTAINER_PREFIX", "qs-sa151-180655")
    suffix = secrets.token_hex(8)
    database = f"{scope.replace('-', '_')}_db_{suffix}"
    role = f"{scope.replace('-', '_')}_role_{suffix}"
    password = secrets.token_urlsafe(24)
    admin_connection = None
    restricted_connection = None
    database_created = False
    role_created = False
    cleanup_evidence: dict[str, Any] = {
        "database": database,
        "role": role,
        "database_absent": False,
        "role_absent": False,
    }

    # The finally is deliberately established before either CREATE statement.
    try:
        admin_connection = psycopg2.connect(
            **_postgres_connect_kwargs(postgres_service, database="postgres")
        )
        admin_connection.autocommit = True
        with admin_connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            version_num = int(cursor.fetchone()[0])
            assert version_num // 10000 == 18, (
                f"Expected PostgreSQL 18, got server_version_num={version_num}"
            )
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            assert cursor.fetchone() is None, f"Database already exists: {database}"
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            assert cursor.fetchone() is None, f"Role already exists: {role}"

            cursor.execute(
                f"CREATE ROLE {_quote_postgres_identifier(role)} LOGIN "
                "NOSUPERUSER NOBYPASSRLS NOINHERIT PASSWORD %s",
                (password,),
            )
            role_created = True
            cursor.execute(
                f"CREATE DATABASE {_quote_postgres_identifier(database)} "
                f"OWNER {_quote_postgres_identifier(role)}"
            )
            database_created = True
            cursor.execute(
                "SELECT rolsuper, rolbypassrls, rolinherit, rolcanlogin "
                "FROM pg_roles WHERE rolname = %s",
                (role,),
            )
            role_flags = cursor.fetchone()
            assert role_flags == (False, False, False, True), (
                f"Restricted role flags are incorrect: {role_flags}"
            )

        restricted_connection = psycopg2.connect(
            **_postgres_connect_kwargs(
                postgres_service,
                database=database,
                user=role,
                password=password,
            )
        )
        restricted_connection.autocommit = True
        with restricted_connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_schema, table_name "
                "FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog', 'information_schema')"
            )
            assert cursor.fetchall() == [], "Restricted database is not empty"
            cursor.execute("SELECT to_regclass('public.django_migrations')")
            assert cursor.fetchone()[0] is None, (
                "django_migrations exists before the first generated migration"
            )

        yield {
            "database": database,
            "role": role,
            "password": password,
            "url": (
                f"postgresql://{role}:{password}@{postgres_service['host']}"
                f":{postgres_service['port']}/{database}"
            ),
            "postgres_major": 18,
            "role_flags": role_flags,
            "empty_before_migrate": True,
            "cleanup_evidence": cleanup_evidence,
        }
    finally:
        if restricted_connection is not None:
            restricted_connection.close()
        if admin_connection is not None:
            admin_connection.autocommit = True
            with admin_connection.cursor() as cursor:
                if database_created:
                    cursor.execute(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = %s AND pid <> pg_backend_pid()",
                        (database,),
                    )
                    cursor.execute(
                        f"DROP DATABASE {_quote_postgres_identifier(database)}"
                    )
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
                )
                cleanup_evidence["database_absent"] = cursor.fetchone() is None
                assert cleanup_evidence["database_absent"], (
                    f"Database cleanup failed: {database}"
                )
                if role_created:
                    cursor.execute(f"DROP ROLE {_quote_postgres_identifier(role)}")
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
                cleanup_evidence["role_absent"] = cursor.fetchone() is None
                assert cleanup_evidence["role_absent"], f"Role cleanup failed: {role}"
            admin_connection.close()


def _source_module_inventory(embedded_root: Path) -> dict[str, Any]:
    """Bind embedded manifest defaults, mappings, and source migration shape."""
    from quickscale_core.contracts.module_discovery import (
        authoritative_module_names,
        discover_shipped_module_paths,
    )
    from quickscale_core.manifest.loader import load_manifest_from_path

    names = tuple(authoritative_module_names())
    roots = discover_shipped_module_paths()
    assert set(names) == set(roots), "Authoritative names and roots diverged"
    expected_app_config_identities = {
        name: {
            "name": f"quickscale_modules_{name}",
            "label": f"quickscale_modules_{name}",
        }
        for name in names
    }
    options: dict[str, dict[str, object]] = {}
    option_to_setting: dict[str, dict[str, str]] = {}
    setting_names: dict[str, list[str]] = {}
    expected_settings: dict[str, dict[str, object]] = {}
    manifests: dict[str, Any] = {}
    for name in names:
        manifest_path = embedded_root / name / "module.yml"
        assert manifest_path.exists(), f"Embedded manifest missing for {name}"
        manifest = load_manifest_from_path(manifest_path)
        manifests[name] = manifest
        options[name] = dict(manifest.get_defaults())
        mapping = manifest.get_django_settings_mapping()
        option_to_setting[name] = mapping
        setting_names[name] = list(mapping.values())
        expected_settings[name] = {
            setting_name: manifest.mutable_options[option_name].default
            for option_name, setting_name in mapping.items()
        }
    assert set(options) == set(names), "Module options do not cover authoritative names"
    assert sum(len(settings) for settings in expected_settings.values()) == 68

    model_modules: set[str] = set()
    service_modules: set[str] = set()
    initial_migrations: dict[str, str] = {}
    for name in names:
        root = roots[name]
        models_file = root / "src" / f"quickscale_modules_{name}" / "models.py"
        models_package = (
            root / "src" / f"quickscale_modules_{name}" / "models" / "__init__.py"
        )
        assert not (models_file.exists() and models_package.exists()), (
            f"Ambiguous models representation for {name}"
        )
        if models_file.exists() or models_package.exists():
            model_modules.add(name)
            migration = (
                root
                / "src"
                / f"quickscale_modules_{name}"
                / "migrations"
                / "0001_initial.py"
            )
            assert migration.exists(), f"Missing source 0001_initial for {name}"
            initial_migrations[name] = migration.relative_to(root).as_posix()
        else:
            service_modules.add(name)
            migration_dir = root / "src" / f"quickscale_modules_{name}" / "migrations"
            assert not migration_dir.exists(), f"Service module has migrations: {name}"

    return {
        "names": names,
        "roots": roots,
        "expected_app_config_identities": expected_app_config_identities,
        "manifests": manifests,
        "options": options,
        "option_to_setting": option_to_setting,
        "setting_names": setting_names,
        "expected_settings": expected_settings,
        "model_modules": model_modules,
        "service_modules": service_modules,
        "initial_migrations": initial_migrations,
    }


def _run_generated_json_probe(
    project_path: Path,
    project_name: str,
    environment: dict[str, str],
    setting_names: dict[str, list[str]],
) -> dict[str, Any]:
    """Collect runtime settings, app provenance, migrations, and path provenance."""
    setting_names_json = json.dumps(setting_names, sort_keys=True)
    probe = (
        """
import json
import pathlib
import sys

import django
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

django.setup()
project_root = pathlib.Path.cwd().resolve()
embedded_root = (project_root / "modules").resolve()
manifest_setting_names = json.loads(%r)

def embedded_name(value):
    if not value:
        return None
    path = pathlib.Path(value).resolve()
    try:
        relative = path.relative_to(embedded_root)
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None

app_configs = []
for config in apps.get_app_configs():
    origin = getattr(config.module, "__file__", None)
    module_name = embedded_name(origin)
    if module_name is None:
        continue
    model_origin = getattr(config.models_module, "__file__", None)
    app_configs.append({
        "module": module_name,
        "name": config.name,
        "label": config.label,
        "origin": str(pathlib.Path(origin).resolve()) if origin else None,
        "model_origin": str(pathlib.Path(model_origin).resolve()) if model_origin else None,
    })

loader = MigrationLoader(connection, ignore_no_migrations=False)
recorder = MigrationRecorder(connection)
disk = [
    {"app": app, "name": name}
    for app, name in sorted(loader.disk_migrations)
    if any(item["label"] == app for item in app_configs)
]
applied = [
    {"app": app, "name": name}
    for app, name in sorted(recorder.applied_migrations())
    if any(item["label"] == app for item in app_configs)
]
migration_files = []
for path in sorted(embedded_root.glob("*/**/migrations/0001_initial.py")):
    migration_files.append(str(path.relative_to(project_root)))

manifest_settings = {
    module_name: {
        setting_name: getattr(settings, setting_name)
        for setting_name in module_setting_names
    }
    for module_name, module_setting_names in manifest_setting_names.items()
}

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    )
    public_tables = [row[0] for row in cursor.fetchall()]

print(json.dumps({
    "sys_path": sys.path,
    "app_configs": app_configs,
    "disk_migrations": disk,
    "applied_migrations": applied,
    "migration_files": migration_files,
    "manifest_settings": manifest_settings,
    "public_tables": public_tables,
}, sort_keys=True))
"""
        % setting_names_json
    )
    result = subprocess.run(
        ["poetry", "run", "python", "-c", probe],
        cwd=project_path,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, (
        f"Generated runtime probe failed:\nstdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    return cast(dict[str, Any], json.loads(result.stdout))


def test_install_project_dependencies_strict_network_failure_is_not_skipped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Strict generated-project installation reports network failures."""
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="Connection error: PyPI is unreachable",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AssertionError, match="Poetry lock failed"):
        _install_project_dependencies(tmp_path, strict=True)
    assert calls == [["poetry", "lock"]]


def _run_migrations(
    project_path: Path,
    project_name: str,
    *,
    environment: dict[str, str] | None = None,
    privileged_command: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run database migrations against the PostgreSQL test database.

    The test database must already exist (created by the ``per_test_db``
    fixture or equivalent).
    """
    subprocess_env = (
        dict(environment)
        if environment is not None
        else build_isolated_poetry_env(
            {"DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_smoke"}
        )
    )
    if environment is None:
        subprocess_env["DJANGO_SETTINGS_MODULE"] = f"{project_name}.settings.test_smoke"
    if privileged_command is not None:
        subprocess_env["QUICKSCALE_PRIVILEGED_COMMAND"] = privileged_command

    result = subprocess.run(
        ["poetry", "run", "python", "manage.py", "migrate", "--noinput"],
        cwd=project_path,
        capture_output=True,
        text=True,
        env=subprocess_env,
    )
    assert result.returncode == 0, (
        f"Migrations failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result


def _start_dev_server(
    project_path: Path, project_name: str, port: int
) -> subprocess.Popen[str]:
    """Start Django development server in background with PostgreSQL settings."""
    return subprocess.Popen(
        [
            "poetry",
            "run",
            "python",
            "manage.py",
            "runserver",
            str(port),
            "--noreload",
        ],
        cwd=project_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=build_isolated_poetry_env(
            {"DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_smoke"}
        ),
        text=True,
        bufsize=1,
    )


def _wait_for_server(
    url: str, timeout: int = 30, server_process: subprocess.Popen[str] | None = None
) -> None:
    """Wait for the development server to accept TCP connections.

    This checks TCP connectivity only (not HTTP status), so it succeeds even
    when the root URL returns a non-200 response. The actual route assertion
    is handled separately by ``_assert_url_responds``.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80

    start_time = time.time()

    while time.time() - start_time < timeout:
        if server_process is not None and server_process.poll() is not None:
            output = server_process.stdout.read() if server_process.stdout else ""
            raise RuntimeError(
                f"Server process exited with code {server_process.returncode}.\n"
                f"Output:\n{output}"
            )
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError, ConnectionRefusedError:
            time.sleep(0.5)

    error_msg = f"Server did not start within {timeout} seconds."
    if server_process is not None and server_process.stdout:
        output_lines: list[str] = []
        try:
            for _ in range(20):
                line = server_process.stdout.readline()
                if not line:
                    break
                output_lines.append(line)
            if output_lines:
                error_msg += f"\n\nServer output:\n{''.join(output_lines)}"
        except Exception:
            pass
    raise TimeoutError(error_msg)


def _assert_url_responds(url: str, timeout: int = 15) -> None:
    """Assert that a URL responds with a successful HTTP status (2xx/3xx).

    Requires the embedded module's route to return a successful outcome —
    a 2xx or 3xx response — proving that the URL routing is wired **and**
    the route serves a valid page or redirect.  4xx and 5xx responses are
    treated as failures so that missing routes or server crashes are caught
    rather than silently passing the smoke test.
    """
    start = time.time()
    last_error: Exception | None = None

    while time.time() - start < timeout:
        try:
            response = urllib.request.urlopen(url, timeout=2)
            status = response.getcode()
            if 200 <= status < 400:
                return
            last_error = AssertionError(
                f"URL {url} returned unexpected status {status}"
            )
        except urllib.error.HTTPError as exc:
            # 4xx/5xx means the server is up but the route is broken —
            # do not treat this as success.
            last_error = AssertionError(
                f"URL {url} returned HTTP {exc.code}: {exc.reason}"
            )
            break
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
        time.sleep(0.5)

    raise AssertionError(
        f"URL {url} did not respond successfully within {timeout}s. "
        f"Last error: {last_error}"
    )


def _stop_server(server_process: subprocess.Popen[str]) -> None:
    """Terminate the development server process."""
    try:
        server_process.terminate()
        server_process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        server_process.kill()
        server_process.wait(timeout=2)


class TestGeneratedProjectRuntimeSmoke:
    """Runtime smoke test for generated projects with embedded modules.

    Validates that an embedded-module generated project can:
    1. Generate project scaffold
    2. Embed the auth module
    3. Wire declarative config + managed settings/URLs
    4. Install dependencies via Poetry
    5. Run migrations against PostgreSQL
    6. Boot a development server
    7. Serve an auth-module route (/accounts/profile/) with a successful outcome
       (2xx/3xx) — proving the embedded module's URL routing is wired AND the
       route serves a valid redirect, not just that the server accepts TCP
       connections

    This test IS marked ``@pytest.mark.e2e`` so it is excluded from the
    default CI path (``pytest quickscale_core/tests/ -m "not e2e"``).
    """

    @pytest.mark.e2e
    def test_embedded_auth_module_boots_and_serves_login(
        self, tmp_path: Path, postgres_url: str
    ) -> None:
        """A generated project with embedded auth should boot, migrate, and serve an auth route.

        Requires a successful HTTP outcome (2xx/3xx) for an auth-module route so that
        404 (missing URL wiring) and 5xx (server crash) are caught as failures
        rather than silently passing the smoke test.

        Uses /accounts/profile/ instead of /accounts/login/ because the profile route
        returns 302 (redirect to login) for anonymous users, which is a reliable 3xx
        outcome that proves the auth module's URL routing is wired without requiring
        the allauth login template to render successfully.
        """
        from quickscale_cli.commands.module_config import (
            get_default_auth_config,
            get_default_orgs_config,
        )
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )
        from quickscale_core.generator import ProjectGenerator

        # Phase 1: Generate project scaffold (React theme — with frontend).
        project_name = "runtime_smoke_auth"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)

        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Phase 2: Embed both auth and orgs modules (auth depends on orgs).
        for mod_name in ("auth", "orgs"):
            embedded_path = project_path / "modules" / mod_name
            _copytree_for_generated_project_smoke(
                REPO_ROOT / "quickscale_modules" / mod_name,
                embedded_path,
            )
            assert (embedded_path / "module.yml").exists(), (
                f"{mod_name} module manifest missing after embed"
            )
            assert (embedded_path / "pyproject.toml").exists(), (
                f"{mod_name} module pyproject.toml missing after embed"
            )

        # Phase 3: Write declarative config and sync dependencies.
        auth_options = get_default_auth_config()
        orgs_options = get_default_orgs_config()
        self._write_quickscale_yml_with_modules(
            project_path,
            project_name,
            "showcase_react",
            {"auth": auth_options, "orgs": orgs_options},
        )

        sync_result = sync_project_module_dependencies(
            project_path, {"auth": auth_options, "orgs": orgs_options}
        )
        assert any(
            "quickscale-module-orgs" in dep
            for dep in sync_result.added_path_dependencies
        ), (
            "sync_project_module_dependencies did not register the orgs module "
            f"as a path dependency: {sync_result}"
        )
        assert any(
            "quickscale-module-auth" in dep
            for dep in sync_result.added_path_dependencies
        ), (
            "sync_project_module_dependencies did not register the auth module "
            f"as a path dependency: {sync_result}"
        )

        # Phase 4: Regenerate managed wiring (settings + URLs).
        success, message = regenerate_managed_wiring(project_path)
        assert success, f"regenerate_managed_wiring failed: {message}"

        # Phase 5: Install dependencies.
        _install_project_dependencies(project_path)

        # Phase 6: Write PostgreSQL test settings and run migrations.
        # Set QUICKSCALE_ALLOW_BYPASSRLS so the orgs boot guard passes with
        # a superuser PostgreSQL role (common in dev/test environments).
        # The env var must remain set through Phase 7 (dev server boot)
        # because Django loads AppConfig.ready() at server startup too.
        _write_postgres_test_settings(project_path, project_name, postgres_url)
        _allow_bypass_rls = os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS")
        os.environ["QUICKSCALE_ALLOW_BYPASSRLS"] = "1"
        try:
            _run_migrations(project_path, project_name)

            # Phase 7: Boot development server and assert HTTP route.
            server_port = _find_free_port()
            server_process = _start_dev_server(project_path, project_name, server_port)

            try:
                _wait_for_server(
                    f"http://localhost:{server_port}",
                    timeout=30,
                    server_process=server_process,
                )
                _assert_url_responds(
                    f"http://localhost:{server_port}/accounts/profile/"
                )
            finally:
                _stop_server(server_process)
        finally:
            if _allow_bypass_rls is not None:
                os.environ["QUICKSCALE_ALLOW_BYPASSRLS"] = _allow_bypass_rls
            else:
                os.environ.pop("QUICKSCALE_ALLOW_BYPASSRLS", None)

    @pytest.mark.e2e
    def test_all_module_initial_migrations_apply_from_embedded_sources(
        self,
        tmp_path: Path,
        postgres_service: dict[str, Any],
    ) -> None:
        """Every authoritative embedded module migrates from a clean PG18 DB."""
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )
        from quickscale_core.generator import ProjectGenerator
        from quickscale_core.contracts.module_discovery import (
            authoritative_module_names,
            discover_shipped_module_paths,
        )

        names = tuple(authoritative_module_names())
        roots = discover_shipped_module_paths()

        project_name = "runtime_all_modules"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        for name in names:
            embedded_path = project_path / "modules" / name
            _copytree_for_generated_project_smoke(roots[name], embedded_path)
            assert (embedded_path / "module.yml").exists(), (
                f"{name} module manifest missing after embed"
            )
            assert (embedded_path / "pyproject.toml").exists(), (
                f"{name} module pyproject.toml missing after embed"
            )
        inventory = _source_module_inventory(project_path / "modules")
        assert inventory["names"] == names
        options = inventory["options"]
        expected_settings = inventory["expected_settings"]
        model_modules = inventory["model_modules"]
        service_modules = inventory["service_modules"]
        assert {
            path.name for path in (project_path / "modules").iterdir() if path.is_dir()
        } == set(names)

        self._write_quickscale_yml_with_modules(
            project_path,
            project_name,
            "showcase_react",
            options,
        )
        sync_result = sync_project_module_dependencies(project_path, options)
        path_dependencies = {
            dependency
            for dependency in sync_result.added_path_dependencies
            if "quickscale-module-" in dependency
        }
        assert len(path_dependencies) == len(names), (
            f"Expected one path dependency per authoritative module: {path_dependencies}"
        )
        for name in names:
            assert any(f"quickscale-module-{name}" in dep for dep in path_dependencies)

        success, message = regenerate_managed_wiring(project_path)
        assert success, f"regenerate_managed_wiring failed: {message}"

        _install_project_dependencies(project_path, strict=True)
        assert not any(
            path.name == "wheelhouse" or "wheelhouse" in path.name
            for path in project_path.rglob("*")
        ), "Generated project unexpectedly materialized a local wheelhouse"

        with _restricted_postgres_database(postgres_service) as database:
            _write_postgres_test_settings(
                project_path,
                project_name,
                database["url"],
            )
            migrate_environment = _standalone_generated_env(
                {
                    "DJANGO_SETTINGS_MODULE": (f"{project_name}.settings.test_smoke"),
                    "QUICKSCALE_PRIVILEGED_COMMAND": "migrate",
                    "DATABASE_URL": database["url"],
                    "RUNTIME_DATABASE_URL": database["url"],
                }
            )
            assert "QUICKSCALE_ALLOW_BYPASSRLS" not in migrate_environment
            assert "QUICKSCALE_LOCAL_WHEELHOUSE" not in migrate_environment
            assert str(REPO_ROOT) not in "\n".join(migrate_environment.values())
            migration_result = _run_migrations(
                project_path,
                project_name,
                environment=migrate_environment,
            )
            assert migration_result.returncode == 0
            assert migrate_environment["QUICKSCALE_PRIVILEGED_COMMAND"] == "migrate"

            makemigrations_environment = _standalone_generated_env(
                {
                    "DJANGO_SETTINGS_MODULE": (f"{project_name}.settings.test_smoke"),
                    "DATABASE_URL": database["url"],
                    "RUNTIME_DATABASE_URL": database["url"],
                }
            )
            assert "QUICKSCALE_PRIVILEGED_COMMAND" not in makemigrations_environment
            assert "QUICKSCALE_ALLOW_BYPASSRLS" not in makemigrations_environment
            makemigrations_result = subprocess.run(
                [
                    "poetry",
                    "run",
                    "python",
                    "manage.py",
                    "makemigrations",
                    "--check",
                    "--dry-run",
                ],
                cwd=project_path,
                capture_output=True,
                text=True,
                env=makemigrations_environment,
            )
            assert makemigrations_result.returncode == 0, (
                "makemigrations reported pending changes:\n"
                f"stdout: {makemigrations_result.stdout}\n"
                f"stderr: {makemigrations_result.stderr}"
            )

            runtime = _run_generated_json_probe(
                project_path,
                project_name,
                makemigrations_environment,
                inventory["setting_names"],
            )
            runtime_identities = {
                config["module"]: {
                    "name": config["name"],
                    "label": config["label"],
                }
                for config in runtime["app_configs"]
            }
            assert len(runtime_identities) == len(runtime["app_configs"]), (
                "Runtime app inventory contains duplicate module identities"
            )
            assert runtime_identities == inventory["expected_app_config_identities"], (
                "Runtime AppConfig identities differ from the independent source contract"
            )
            assert len(runtime_identities) == len(names)
            assert all(
                str(REPO_ROOT) not in path
                for path in runtime["sys_path"]
                if isinstance(path, str)
            )
            assert all(
                str(REPO_ROOT) not in origin
                for config in runtime["app_configs"]
                for origin in (config["origin"], config["model_origin"])
                if origin
            )

            runtime_model_modules = {
                config["module"]
                for config in runtime["app_configs"]
                if config["model_origin"] is not None
            }
            assert runtime_model_modules == model_modules
            assert runtime["manifest_settings"] == expected_settings
            assert (
                sum(len(settings) for settings in runtime["manifest_settings"].values())
                == 68
            )
            runtime_settings = [
                value
                for settings in runtime["manifest_settings"].values()
                for value in settings.values()
            ]
            assert any(value is False for value in runtime_settings)
            assert any(value == "" for value in runtime_settings)
            assert any(isinstance(value, list) for value in runtime_settings)
            assert set(runtime["migration_files"]) == {
                f"modules/{name}/{inventory['initial_migrations'][name]}"
                for name in model_modules
            }
            expected_identities = inventory["expected_app_config_identities"]
            model_labels = {
                expected_identities[name]["label"] for name in model_modules
            }
            service_labels = {
                expected_identities[name]["label"] for name in service_modules
            }
            disk_migrations = {
                (migration["app"], migration["name"])
                for migration in runtime["disk_migrations"]
            }
            applied_migrations = {
                (migration["app"], migration["name"])
                for migration in runtime["applied_migrations"]
            }
            expected_migrations = {(label, "0001_initial") for label in model_labels}
            assert disk_migrations == expected_migrations
            assert applied_migrations == expected_migrations
            assert all(
                app not in service_labels for app, _migration_name in disk_migrations
            )
            assert len(runtime["applied_migrations"]) == len(
                set(tuple(item.items()) for item in runtime["applied_migrations"])
            )
            assert "django_migrations" in runtime["public_tables"]

        assert database["cleanup_evidence"] == {
            "database": database["database"],
            "role": database["role"],
            "database_absent": True,
            "role_absent": True,
        }

    @pytest.mark.e2e
    def test_no_redis_createcachetable_succeeds(
        self, tmp_path: Path, postgres_url: str
    ) -> None:
        """A generated project with DatabaseCache must run createcachetable successfully.

        SA63 regression: the createcachetable step must complete without
        triggering the orgs boot guard when QUICKSCALE_ALLOW_BYPASSRLS=1
        is set alongside RUNTIME_DATABASE_URL="".

        This test generates a minimal project, installs its Poetry
        dependencies, writes a test settings module with DatabaseCache,
        and runs ``python manage.py createcachetable`` — proving the
        no-Redis deploy-script path works through a real Django boot.

        The per-test database is created automatically by the
        ``postgres_url`` fixture.
        """
        from quickscale_core.generator import ProjectGenerator

        project_name = "runtime_smoke_cache"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)

        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Install dependencies (no module embedding needed for this test).
        _install_project_dependencies(project_path)

        # Write test settings with DatabaseCache (no-Redis production profile).
        _write_postgres_test_settings(
            project_path, project_name, postgres_url, cache_database=True
        )

        # Run createcachetable with QUICKSCALE_ALLOW_BYPASSRLS set
        # (simulating the start.sh environment).
        # The database already exists (created by the postgres_url fixture).
        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "createcachetable"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env=build_isolated_poetry_env(
                {"DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_smoke"}
            ),
        )
        assert result.returncode == 0, (
            f"createcachetable failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "django_cache_table" in result.stdout or not result.stderr, (
            "createcachetable should report success"
        )

    @pytest.mark.e2e
    def test_production_settings_createcachetable_with_orgs_bypass_hatch(
        self, tmp_path: Path, postgres_url: str
    ) -> None:
        """Generated project with orgs module and production settings must pass
        createcachetable through the env-var bridge (CR-SA63-002).

        This is the genuine production-settings/boot-guard e2e that the prior
        SA63 pass missed: it embeds the orgs module, uses the actual generated
        ``*.settings.production`` module (not ``test_smoke``), sets
        ``RUNTIME_DATABASE_URL=""`` and ``QUICKSCALE_ALLOW_BYPASSRLS=1`` in
        the subprocess environment, and runs ``createcachetable`` — proving
        the complete ``start.sh``-launched path works through Django's real
        production settings and the orgs boot guard.

        The production settings bridge (CR-SA63-001) must select
        ``DATABASE_URL`` because ``RUNTIME_DATABASE_URL`` is explicitly blank
        and the bypass hatch is set.  The orgs boot guard must also pass
        because ``QUICKSCALE_ALLOW_BYPASSRLS=1`` bypasses the RLS role check.
        """
        from quickscale_cli.commands.module_config import (
            get_default_auth_config,
            get_default_orgs_config,
        )
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )
        from quickscale_core.generator import ProjectGenerator

        project_name = "runtime_sa63_prod"
        project_path = tmp_path / project_name

        # Phase 1: Generate project scaffold (React theme — with frontend).
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Phase 2: Embed both auth and orgs modules (orgs depends on auth).
        for mod_name in ("auth", "orgs"):
            embedded_path = project_path / "modules" / mod_name
            _copytree_for_generated_project_smoke(
                REPO_ROOT / "quickscale_modules" / mod_name,
                embedded_path,
            )
            assert (embedded_path / "module.yml").exists(), (
                f"{mod_name} module manifest missing after embed"
            )
            assert (embedded_path / "pyproject.toml").exists(), (
                f"{mod_name} module pyproject.toml missing after embed"
            )

        # Phase 3: Write declarative config and sync dependencies for both modules.
        auth_options = get_default_auth_config()
        orgs_options = get_default_orgs_config()
        self._write_quickscale_yml_with_modules(
            project_path,
            project_name,
            "showcase_react",
            {"auth": auth_options, "orgs": orgs_options},
        )

        sync_result = sync_project_module_dependencies(
            project_path, {"auth": auth_options, "orgs": orgs_options}
        )
        assert any(
            "quickscale-module-orgs" in dep
            for dep in sync_result.added_path_dependencies
        ), (
            "sync_project_module_dependencies did not register the orgs module "
            f"as a path dependency: {sync_result}"
        )
        assert any(
            "quickscale-module-auth" in dep
            for dep in sync_result.added_path_dependencies
        ), (
            "sync_project_module_dependencies did not register the auth module "
            f"as a path dependency: {sync_result}"
        )

        # Phase 4: Regenerate managed wiring (settings + URLs).
        success, message = regenerate_managed_wiring(project_path)
        assert success, f"regenerate_managed_wiring failed: {message}"

        # Phase 5: Install dependencies.
        _install_project_dependencies(project_path)

        # Phase 6: Use the per-test database (already created by the
        # postgres_url fixture).

        # Phase 7: Run createcachetable with production settings and the
        # bridge env pair (simulating the start.sh.j2 createcachetable
        # invocation).
        # Build subprocess env from a copy so we can strip ambient REDIS_URL.
        # The test must prove DatabaseCache/no-Redis path (CR-SA63-002).
        subprocess_env = build_isolated_poetry_env(
            {
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.production",
                "SECRET_KEY": "qs-sa63-test-production-secret-key-not-for-real-use",
                "DATABASE_URL": postgres_url,
                "RUNTIME_DATABASE_URL": "",
                "QUICKSCALE_ALLOW_BYPASSRLS": "1",
                "ALLOWED_HOSTS": "localhost,127.0.0.1",
            }
        )
        subprocess_env.pop("REDIS_URL", None)

        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "createcachetable"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env=subprocess_env,
        )
        assert result.returncode == 0, (
            f"createcachetable under production settings with orgs module "
            f"failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "django_cache_table" in result.stdout or not result.stderr, (
            "createcachetable should report success under production settings"
        )

    @pytest.mark.e2e
    def test_production_settings_createcachetable_with_orgs_privileged_command(
        self, tmp_path: Path, postgres_url: str
    ) -> None:
        """Generated project with orgs module must pass createcachetable via
        the ``QUICKSCALE_PRIVILEGED_COMMAND`` contract (no bypass hatch,
        CR-SA68-001).

        This e2e test follows the actual generated ``start.sh.j2`` no-Redis
        path: it sets ``QUICKSCALE_PRIVILEGED_COMMAND=createcachetable``
        (not the ``QUICKSCALE_ALLOW_BYPASSRLS=1`` escape hatch) alongside
        ``RUNTIME_DATABASE_URL=""``, proving that the orgs boot guard now
        recognises ``createcachetable`` as a sanctioned privileged DB
        command and skips the RLS role check without requiring the escape
        hatch.

        This matches the start.sh.j2 invocation at lines 59-61:
        ``QUICKSCALE_PRIVILEGED_COMMAND=createcachetable RUNTIME_DATABASE_URL=""
        python manage.py createcachetable``
        """
        from quickscale_cli.commands.module_config import (
            get_default_auth_config,
            get_default_orgs_config,
        )
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )
        from quickscale_core.generator import ProjectGenerator

        project_name = "runtime_sa68_privcmd"
        project_path = tmp_path / project_name

        # Phase 1: Generate project scaffold (React theme — with frontend).
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Phase 2: Embed both auth and orgs modules (orgs depends on auth).
        for mod_name in ("auth", "orgs"):
            embedded_path = project_path / "modules" / mod_name
            _copytree_for_generated_project_smoke(
                REPO_ROOT / "quickscale_modules" / mod_name,
                embedded_path,
            )
            assert (embedded_path / "module.yml").exists(), (
                f"{mod_name} module manifest missing after embed"
            )
            assert (embedded_path / "pyproject.toml").exists(), (
                f"{mod_name} module pyproject.toml missing after embed"
            )

        # Phase 3: Write declarative config and sync dependencies for both modules.
        auth_options = get_default_auth_config()
        orgs_options = get_default_orgs_config()
        self._write_quickscale_yml_with_modules(
            project_path,
            project_name,
            "showcase_react",
            {"auth": auth_options, "orgs": orgs_options},
        )

        sync_result = sync_project_module_dependencies(
            project_path, {"auth": auth_options, "orgs": orgs_options}
        )
        assert any(
            "quickscale-module-orgs" in dep
            for dep in sync_result.added_path_dependencies
        ), (
            "sync_project_module_dependencies did not register the orgs module "
            f"as a path dependency: {sync_result}"
        )
        assert any(
            "quickscale-module-auth" in dep
            for dep in sync_result.added_path_dependencies
        ), (
            "sync_project_module_dependencies did not register the auth module "
            f"as a path dependency: {sync_result}"
        )

        # Phase 4: Regenerate managed wiring (settings + URLs).
        success, message = regenerate_managed_wiring(project_path)
        assert success, f"regenerate_managed_wiring failed: {message}"

        # Phase 5: Install dependencies.
        _install_project_dependencies(project_path)

        # Phase 6: Use the per-test database (already created by the
        # postgres_url fixture).

        # Phase 7: Run createcachetable with the actual start.sh.j2
        # privileged-command bridge — no QUICKSCALE_ALLOW_BYPASSRLS.
        # Build subprocess env from a copy so we can strip ambient REDIS_URL.
        # The test must prove DatabaseCache/no-Redis path via privileged
        # command (CR-SA68-001).
        subprocess_env = build_isolated_poetry_env(
            {
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.production",
                "SECRET_KEY": "qs-sa68-test-production-secret-key-not-for-real-use",
                "DATABASE_URL": postgres_url,
                "RUNTIME_DATABASE_URL": "",
                "QUICKSCALE_PRIVILEGED_COMMAND": "createcachetable",
                "ALLOWED_HOSTS": "localhost,127.0.0.1",
            }
        )
        subprocess_env.pop("REDIS_URL", None)
        # No QUICKSCALE_ALLOW_BYPASSRLS — the guard must pass via
        # _is_privileged_command() recognising createcachetable.

        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "createcachetable"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env=subprocess_env,
        )
        assert result.returncode == 0, (
            f"createcachetable under production settings with orgs module "
            f"via privileged command failed:\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "django_cache_table" in result.stdout or not result.stderr, (
            "createcachetable should report success via privileged command"
        )

    @pytest.mark.e2e
    def test_collectstatic_with_production_settings(self, tmp_path: Path) -> None:
        """Generated project must run collectstatic with production settings
        when ``QUICKSCALE_NON_DB_COMMAND=collectstatic`` is set (SA68 Phase 3).

        The non-DB command path must allow collectstatic to run without
        requiring ``RUNTIME_DATABASE_URL`` or a real database connection.
        A dummy ``postgresql://`` URL is used when ``DATABASE_URL`` is also
        unset; Django's ``collectstatic`` does not touch the database, so
        the dummy URL is never actually connected to.

        This mirrors the same command that runs at Docker build time (see
        ``Dockerfile.j2``), proving it works through production settings.
        """
        from quickscale_core.generator import ProjectGenerator

        project_name = "runtime_collectstatic"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)

        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        _install_project_dependencies(project_path)

        # Run collectstatic with production settings and the non-DB command env var.
        # No DATABASE_URL or RUNTIME_DATABASE_URL is needed — the non-DB path
        # provides a dummy URL that Django never actually connects to.
        subprocess_env = build_isolated_poetry_env(
            {
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.production",
                "SECRET_KEY": (
                    "test-secret-key-for-collectstatic-e2e-not-for-real-use"
                ),
                "QUICKSCALE_NON_DB_COMMAND": "collectstatic",
                "ALLOWED_HOSTS": "localhost,127.0.0.1",
            }
        )
        subprocess_env.pop("REDIS_URL", None)

        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "collectstatic", "--noinput"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env=subprocess_env,
        )
        assert result.returncode == 0, (
            f"collectstatic with QUICKSCALE_NON_DB_COMMAND through "
            f"production settings failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "static files" in result.stdout.lower() or not result.stderr, (
            "collectstatic should report static files copied"
        )

    @pytest.mark.e2e
    def test_production_shell_csrf_token_accepts_authenticated_org_mutation(
        self, tmp_path: Path, postgres_url: str
    ) -> None:
        """The generated production UI must pass enforced Django CSRF."""
        from quickscale_cli.commands.module_config import (
            get_default_auth_config,
            get_default_orgs_config,
        )
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )
        from quickscale_core.generator import ProjectGenerator

        project_name = "runtime_sa160_csrf"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)

        for mod_name in ("auth", "orgs"):
            embedded_path = project_path / "modules" / mod_name
            _copytree_for_generated_project_smoke(
                REPO_ROOT / "quickscale_modules" / mod_name,
                embedded_path,
            )

        auth_options = get_default_auth_config()
        orgs_options = get_default_orgs_config()
        orgs_options["mode"] = "saas"
        modules = {"auth": auth_options, "orgs": orgs_options}
        self._write_quickscale_yml_with_modules(
            project_path,
            project_name,
            "showcase_react",
            modules,
        )

        sync_result = sync_project_module_dependencies(project_path, modules)
        assert any(
            "quickscale-module-orgs" in dependency
            for dependency in sync_result.added_path_dependencies
        )
        assert any(
            "quickscale-module-auth" in dependency
            for dependency in sync_result.added_path_dependencies
        )
        success, message = regenerate_managed_wiring(project_path)
        assert success, f"regenerate_managed_wiring failed: {message}"
        _install_project_dependencies(project_path, strict=True)

        production_environment = _standalone_generated_env(
            {
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.production",
                "SECRET_KEY": "qs-sa160-production-csrf-test-secret-not-for-real-use",
                "DATABASE_URL": postgres_url,
                "RUNTIME_DATABASE_URL": "",
                "QUICKSCALE_ALLOW_BYPASSRLS": "1",
                "ALLOWED_HOSTS": "localhost,127.0.0.1",
            }
        )
        production_environment.pop("REDIS_URL", None)
        production_environment.pop("QUICKSCALE_PRIVILEGED_COMMAND", None)
        production_environment.pop("QUICKSCALE_NON_DB_COMMAND", None)

        migration_environment = {
            **production_environment,
            "QUICKSCALE_PRIVILEGED_COMMAND": "migrate",
        }
        migration_environment.pop("QUICKSCALE_ALLOW_BYPASSRLS", None)
        assert migration_environment["RUNTIME_DATABASE_URL"] == ""
        migrate_result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "migrate", "--noinput"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=180,
            env=migration_environment,
        )
        assert migrate_result.returncode == 0, (
            f"production migration failed:\n{migrate_result.stdout}\n"
            f"{migrate_result.stderr}"
        )

        cache_environment = {
            **production_environment,
            "QUICKSCALE_PRIVILEGED_COMMAND": "createcachetable",
        }
        cache_environment.pop("QUICKSCALE_ALLOW_BYPASSRLS", None)
        assert cache_environment["RUNTIME_DATABASE_URL"] == ""
        cache_result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "createcachetable"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=180,
            env=cache_environment,
        )
        assert cache_result.returncode == 0, (
            f"production createcachetable failed:\n{cache_result.stdout}\n"
            f"{cache_result.stderr}"
        )

        frontend_path = project_path / "frontend"
        assert shutil.which("pnpm") is not None, "pnpm is required for production E2E"
        frontend_install_result = subprocess.run(
            ["pnpm", "install"],
            cwd=frontend_path,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert frontend_install_result.returncode == 0, (
            f"generated frontend install failed:\n{frontend_install_result.stdout}\n"
            f"{frontend_install_result.stderr}"
        )
        frontend_typecheck_result = subprocess.run(
            ["pnpm", "run", "type-check"],
            cwd=frontend_path,
            capture_output=True,
            text=True,
            timeout=240,
        )
        assert frontend_typecheck_result.returncode == 0, (
            f"generated frontend type-check failed:\n"
            f"{frontend_typecheck_result.stdout}\n{frontend_typecheck_result.stderr}"
        )
        frontend_build_result = subprocess.run(
            ["pnpm", "run", "build"],
            cwd=frontend_path,
            capture_output=True,
            text=True,
            timeout=240,
        )
        assert frontend_build_result.returncode == 0, (
            f"generated frontend build failed:\n{frontend_build_result.stdout}\n"
            f"{frontend_build_result.stderr}"
        )

        collectstatic_environment = {
            **production_environment,
            "QUICKSCALE_NON_DB_COMMAND": "collectstatic",
        }
        assert "QUICKSCALE_PRIVILEGED_COMMAND" not in collectstatic_environment
        collectstatic_result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "collectstatic", "--noinput"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=180,
            env=collectstatic_environment,
        )
        assert collectstatic_result.returncode == 0, (
            f"production collectstatic failed:\n{collectstatic_result.stdout}\n"
            f"{collectstatic_result.stderr}"
        )

        credential_probe = textwrap.dedent(
            """
            import django

            django.setup()
            from django.contrib.auth import get_user_model

            get_user_model().objects.create_user(
                username="sa160_browser_user",
                email="sa160_browser_user@example.test",
                password="sa160-browser-password",
            )
            """
        )
        credential_result = subprocess.run(
            ["poetry", "run", "python", "-c", credential_probe],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,
            env=production_environment,
        )
        assert credential_result.returncode == 0, (
            f"generated credential creation failed:\n{credential_result.stdout}\n"
            f"{credential_result.stderr}"
        )

        server_port = _find_free_port()
        assert "QUICKSCALE_PRIVILEGED_COMMAND" not in production_environment
        assert "QUICKSCALE_NON_DB_COMMAND" not in production_environment
        server_process = subprocess.Popen(
            [
                "poetry",
                "run",
                "python",
                "manage.py",
                "runserver",
                str(server_port),
                "--noreload",
            ],
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=production_environment,
        )

        proxy_stack: ExitStack | None = None
        session_fingerprint: str | None = None
        try:
            django_base_url = f"http://localhost:{server_port}"
            _wait_for_server(
                django_base_url,
                timeout=30,
                server_process=server_process,
            )

            from playwright.sync_api import sync_playwright

            observed_proxy_requests: list[dict[str, Any]] = []
            proxy_diagnostics: dict[str, Any] = {}
            proxy_stack = ExitStack()
            base_url = proxy_stack.enter_context(
                _https_reverse_proxy(
                    tmp_path,
                    f"http://127.0.0.1:{server_port}",
                    observed_proxy_requests,
                    proxy_diagnostics,
                )
            )
            session_fingerprint = proxy_diagnostics["certificate_fingerprint_sha256"]
            assert proxy_diagnostics["certificate_generation_count"] == 1
            assert len(session_fingerprint) == 64
            api_url = f"{base_url}/api/orgs/"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox"],
                )
                try:
                    browser_version = browser.version
                    control_context = browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        ignore_https_errors=True,
                    )
                    positive_context = browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        ignore_https_errors=True,
                    )
                    try:
                        control_response = control_context.request.get(
                            f"{django_base_url}/orgs/",
                            max_redirects=0,
                        )
                        assert control_response.status in {301, 302, 307, 308}, (
                            "Unproxied production control must redirect to HTTPS: "
                            f"status={control_response.status}"
                        )
                        redirect_location = control_response.headers.get("location")
                        assert (
                            redirect_location
                            == f"https://localhost:{server_port}/orgs/"
                        ), (
                            "Unproxied production redirect Location was not bound: "
                            f"{redirect_location!r}"
                        )

                        positive_page = positive_context.new_page()
                        login_response = positive_page.goto(
                            f"{base_url}/accounts/login/"
                        )
                        assert login_response is not None
                        assert login_response.status == 200, (
                            "Proxy-marked login navigation failed: "
                            f"status={login_response.status}"
                        )
                        login_input = positive_page.locator('input[name="login"]')
                        if login_input.count() == 0:
                            login_input = positive_page.locator(
                                'input[name="username"]'
                            )
                        assert login_input.count() == 1, (
                            "Authenticated calibration login field was not rendered"
                        )
                        login_input.fill("sa160_browser_user@example.test")
                        positive_page.locator('input[name="password"]').fill(
                            "sa160-browser-password"
                        )
                        with positive_page.expect_response(
                            lambda response: (
                                response.url == f"{base_url}/accounts/login/"
                                and response.request.method == "POST"
                            ),
                            timeout=30_000,
                        ) as login_post_info:
                            positive_page.get_by_role(
                                "button", name="Sign In", exact=True
                            ).click()
                        login_post_response = login_post_info.value

                        login_state = positive_page.locator("body").inner_text()
                        cookies = {
                            cookie["name"]: cookie
                            for cookie in positive_context.cookies()
                        }
                        assert cookies.get("sessionid", {}).get("secure") is True, (
                            "Chromium calibration did not retain a Secure sessionid: "
                            f"browser={browser_version}, login_status={login_post_response.status}, "
                            f"url={positive_page.url!r}, "
                            f"body={login_state!r}, cookies={cookies!r}"
                        )
                        assert cookies.get("sessionid", {}).get("httpOnly") is True, (
                            "Chromium calibration did not retain an HttpOnly sessionid: "
                            f"browser={browser_version}, cookies={cookies!r}"
                        )
                        assert cookies.get("csrftoken", {}).get("secure") is True, (
                            "Chromium calibration did not retain a Secure csrftoken: "
                            f"browser={browser_version}, cookies={cookies!r}"
                        )
                        assert cookies.get("csrftoken", {}).get("httpOnly") is True, (
                            "Chromium calibration did not retain an HttpOnly csrftoken: "
                            f"browser={browser_version}, cookies={cookies!r}"
                        )

                        try:
                            shell_response = positive_page.goto(
                                f"{base_url}/orgs/new/",
                                wait_until="domcontentloaded",
                            )
                        except Exception as exc:
                            observed_targets = [
                                (request["method"], request["target"])
                                for request in observed_proxy_requests
                            ]
                            response_summary = [
                                (
                                    response["target"],
                                    response["status"],
                                    response["body_length"],
                                    "content-encoding" in response["header_names"],
                                )
                                for response in proxy_diagnostics["responses"]
                            ]
                            raise AssertionError(
                                "Authenticated shell navigation failed with proxy "
                                f"diagnostics: error={exc!r}, targets={observed_targets!r}, "
                                f"responses={response_summary!r}, "
                                f"upstream_errors={proxy_diagnostics['upstream_errors']!r}, "
                                f"unexpected={proxy_diagnostics['unexpected_handler_errors']!r}, "
                                f"timeouts={proxy_diagnostics['handler_timeouts']}"
                            ) from exc
                        assert shell_response is not None
                        assert shell_response.status == 200, (
                            "Authenticated proxy-marked shell navigation failed: "
                            f"status={shell_response.status}, url={positive_page.url}"
                        )
                        document_cookie = positive_page.evaluate("document.cookie")
                        assert not any(
                            entry.strip().startswith("csrftoken=")
                            for entry in document_cookie.split(";")
                        ), (
                            "HttpOnly csrftoken leaked into document.cookie: "
                            f"browser={browser_version}, document.cookie={document_cookie!r}"
                        )
                        csrf_token = positive_page.locator(
                            'meta[name="csrf-token"]'
                        ).get_attribute("content")
                        assert csrf_token, (
                            "Authenticated shell did not render a non-empty CSRF meta token: "
                            f"browser={browser_version}"
                        )

                        omitted_header_name = "SA160 omitted-header control"
                        omitted_header_result = positive_page.evaluate(
                            """
                            async (name) => {
                              const response = await fetch('/api/orgs/', {
                                method: 'POST',
                                credentials: 'same-origin',
                                headers: {
                                  Accept: 'application/json',
                                  'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({name}),
                              })
                              return {status: response.status, body: await response.text()}
                            }
                            """,
                            omitted_header_name,
                        )
                        assert omitted_header_result["status"] == 403, (
                            "Same-origin omitted-header control must be rejected: "
                            f"{omitted_header_result!r}"
                        )

                        positive_page.get_by_role(
                            "heading", name="Create organization", exact=True
                        ).wait_for(state="visible")
                        organization_name = "SA160 browser-created organization"
                        with positive_page.expect_request(
                            lambda request: (
                                request.url == api_url and request.method == "POST"
                            ),
                            timeout=30_000,
                        ) as request_info:
                            with positive_page.expect_response(
                                lambda response: (
                                    response.url == api_url
                                    and response.request.method == "POST"
                                ),
                                timeout=30_000,
                            ) as response_info:
                                positive_page.get_by_label(
                                    "Organization name", exact=True
                                ).fill(organization_name)
                                positive_page.get_by_role(
                                    "button",
                                    name="Create organization",
                                    exact=True,
                                ).click()

                        create_request = request_info.value
                        create_response = response_info.value
                        assert create_request.url == api_url
                        observed_csrf_header = next(
                            (
                                value
                                for name, value in create_request.headers.items()
                                if name.lower() == "x-csrftoken"
                            ),
                            None,
                        )
                        assert observed_csrf_header == csrf_token, (
                            "Generated apiRequest did not send the rendered CSRF token: "
                            f"observed={observed_csrf_header!r}, rendered={csrf_token!r}"
                        )
                        assert create_response.status == 201, (
                            "Generated apiRequest organization mutation did not return 201: "
                            f"status={create_response.status}, body={create_response.text()!r}"
                        )
                        create_payload = create_response.json()
                        assert (
                            create_payload["organization"]["name"] == organization_name
                        )
                        next_url = create_payload["next_url"]
                        assert isinstance(next_url, str) and next_url.startswith("/")
                        expected_redirect_url = urljoin(base_url, next_url)
                        positive_page.wait_for_url(
                            expected_redirect_url,
                            wait_until="domcontentloaded",
                            timeout=30_000,
                        )
                        assert positive_page.url == expected_redirect_url, (
                            "OrgCreatePage did not perform the returned full-document redirect: "
                            f"expected={expected_redirect_url!r}, actual={positive_page.url!r}"
                        )

                        persisted_result = positive_page.evaluate(
                            """
                            async () => {
                              const response = await fetch('/api/orgs/', {
                                credentials: 'same-origin',
                                headers: {Accept: 'application/json'},
                              })
                              return {status: response.status, payload: await response.json()}
                            }
                            """
                        )
                        assert persisted_result["status"] == 200
                        persisted_names = [
                            organization["name"]
                            for organization in persisted_result["payload"][
                                "organizations"
                            ]
                        ]
                        assert persisted_names.count(organization_name) == 1, (
                            "Positive organization was not persisted in the authenticated API list: "
                            f"{persisted_names!r}"
                        )
                        assert omitted_header_name not in persisted_names, (
                            "Omitted-header control created an organization: "
                            f"{persisted_names!r}"
                        )

                        login_requests = [
                            request
                            for request in observed_proxy_requests
                            if request["method"] == "POST"
                            and request["target"] == "/accounts/login/"
                        ]
                        assert len(login_requests) == 1, (
                            "Expected exactly one proxied browser login POST: "
                            f"{login_requests!r}"
                        )
                        create_requests = [
                            request
                            for request in observed_proxy_requests
                            if request["method"] == "POST"
                            and request["target"] == "/api/orgs/"
                            and organization_name.encode() in request["body"]
                        ]
                        assert len(create_requests) == 1, (
                            "Expected exactly one proxied organization create POST: "
                            f"{create_requests!r}"
                        )
                        for browser_request in (*login_requests, *create_requests):
                            assert (
                                browser_request["headers"].get("origin") == base_url
                            ), (
                                "Browser-generated Origin did not use the frozen HTTPS "
                                f"proxy origin: {browser_request!r}"
                            )
                            assert (
                                "x-forwarded-proto" not in browser_request["headers"]
                            ), (
                                "Browser request unexpectedly supplied proxy forwarding "
                                f"state: {browser_request!r}"
                            )
                    finally:
                        positive_context.close()
                        control_context.close()
                finally:
                    browser.close()
        finally:
            if proxy_stack is not None:
                proxy_stack.close()
                if session_fingerprint is not None:
                    assert (
                        proxy_diagnostics["certificate_fingerprint_sha256"]
                        == session_fingerprint
                    )
                    assert proxy_diagnostics["unexpected_handler_errors"] == []
                    assert not proxy_diagnostics["server_thread"].is_alive()
            _stop_server(server_process)
            assert not (tmp_path / "localhost.key").exists()
            assert not (tmp_path / "localhost.crt").exists()

    @staticmethod
    def _write_quickscale_yml_with_auth(
        project_path: Path,
        project_name: str,
        theme: str,
        auth_options: dict[str, object],
    ) -> None:
        """Write a minimal quickscale.yml that declares the auth module."""
        import yaml

        config_payload = {
            "version": "1",
            "project": {
                "slug": project_name,
                "package": project_name,
                "theme": theme,
            },
            "docker": {"start": False},
            "modules": {"auth": dict(auth_options)},
        }
        rendered = yaml.safe_dump(
            config_payload,
            sort_keys=False,
            default_flow_style=False,
        )
        (project_path / "quickscale.yml").write_text(rendered)

    @staticmethod
    def _write_quickscale_yml_with_orgs(
        project_path: Path,
        project_name: str,
        theme: str,
        orgs_options: dict[str, object],
    ) -> None:
        """Write a minimal quickscale.yml that declares the orgs module."""
        import yaml

        config_payload = {
            "version": "1",
            "project": {
                "slug": project_name,
                "package": project_name,
                "theme": theme,
            },
            "docker": {"start": False},
            "modules": {"orgs": dict(orgs_options)},
        }
        rendered = yaml.safe_dump(
            config_payload,
            sort_keys=False,
            default_flow_style=False,
        )
        (project_path / "quickscale.yml").write_text(rendered)

    @staticmethod
    def _write_quickscale_yml_with_modules(
        project_path: Path,
        project_name: str,
        theme: str,
        modules_config: dict[str, dict[str, object]],
    ) -> None:
        """Write a minimal quickscale.yml that declares multiple modules."""
        import yaml

        config_payload = {
            "version": "1",
            "project": {
                "slug": project_name,
                "package": project_name,
                "theme": theme,
            },
            "docker": {"start": False},
            "modules": {
                mod_name: dict(mod_options)
                for mod_name, mod_options in modules_config.items()
            },
        }
        rendered = yaml.safe_dump(
            config_payload,
            sort_keys=False,
            default_flow_style=False,
        )
        (project_path / "quickscale.yml").write_text(rendered)
