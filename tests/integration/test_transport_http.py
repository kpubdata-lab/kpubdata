"""Test module.
transport http tests."""

from __future__ import annotations

# pyright: reportImplicitOverride=false, reportPrivateUsage=false
import http.server
import json
import threading
import time
from collections.abc import Generator
from dataclasses import dataclass
from typing import cast

import pytest
from typing_extensions import TypedDict

from kpubdata.exceptions import TransportError, TransportTimeoutError
from kpubdata.transport.decode import decode_json, detect_content_type
from kpubdata.transport.http import HttpTransport, TransportConfig


class Scenario(TypedDict, total=False):
    """Scenario encapsulates scenario."""

    status: int
    body: str | bytes
    content_type: str
    delay: float
    omit_content_length: bool


class MockThreadingHTTPServer(http.server.ThreadingHTTPServer):
    """MockThreadingHTTPServer encapsulates HTTP server."""

    hit_count: int
    hit_lock: threading.Lock
    last_body: bytes
    last_headers: dict[str, str]

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler: type[http.server.BaseHTTPRequestHandler],
    ) -> None:
        """Initialize instance state."""
        super().__init__(server_address, request_handler)
        self.scenarios: list[Scenario] = []
        self.hit_count = 0
        self.hit_lock = threading.Lock()
        self.last_body = b""
        self.last_headers = {}


class MockHandler(http.server.BaseHTTPRequestHandler):
    """MockHandler encapsulates HTTP handler."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002, ARG002
        """Suppress HTTP server logging."""
        return

    def do_GET(self) -> None:  # noqa: N802
        """Delegate GET to common handler."""
        self._handle_request()

    def do_POST(self) -> None:  # noqa: N802
        """Delegate POST to common handler."""
        self._handle_request()

    def _handle_request(self) -> None:
        """Helper for handling requests."""
        # Get response for current request, update observable server state
        server = cast(MockThreadingHTTPServer, self.server)
        length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(length) if length else b""

        with server.hit_lock:
            server.hit_count += 1
            server.last_body = request_body
            server.last_headers = {k.lower(): v for k, v in self.headers.items()}
            scenario: Scenario = server.scenarios.pop(0) if server.scenarios else {}

        # Simulate timeout and retry via delayed responses
        delay = scenario.get("delay", 0.0)
        if delay > 0:
            time.sleep(delay)

        # Construct response body and headers, return as in-process server
        status = scenario.get("status", 200)
        body = scenario.get("body", "")
        payload = body if isinstance(body, bytes) else body.encode("utf-8")
        content_type = scenario.get("content_type", "text/plain; charset=utf-8")

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if not scenario.get("omit_content_length", False):
            self.send_header("Content-Length", str(len(payload)))
        self.end_headers()

        try:
            _ = self.wfile.write(payload)
        except BrokenPipeError:
            return


@dataclass
class MockServer:
    """MockServer encapsulates server control."""

    base_url: str
    scenarios: list[Scenario]
    server: MockThreadingHTTPServer

    @property
    def hit_count(self) -> int:
        """Get hit count."""
        return self.server.hit_count

    @property
    def last_body(self) -> bytes:
        """Get last request body."""
        return self.server.last_body

    @property
    def last_headers(self) -> dict[str, str]:
        """Get last request headers."""
        return self.server.last_headers


@pytest.fixture
def mock_server() -> Generator[MockServer, None, None]:
    """Setup mock server."""
    server = MockThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield MockServer(
            base_url=f"http://127.0.0.1:{server.server_port}",
            scenarios=server.scenarios,
            server=server,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


@pytest.fixture
def transport_config() -> TransportConfig:
    """Setup transport config."""
    return TransportConfig(timeout=2.0, max_retries=2, retry_backoff_factor=0)


# test get success scenario
def test_get_success(mock_server: MockServer, transport_config: TransportConfig) -> None:
    """Verify test get success scenario."""
    mock_server.scenarios.append(
        {
            "status": 200,
            "body": '{"ok": true}',
            "content_type": "application/json",
        }
    )

    with HttpTransport(transport_config) as transport:
        response = transport.request("GET", f"{mock_server.base_url}/ok")

    assert response.status_code == 200
    assert response.text == '{"ok": true}'
    assert detect_content_type(response) == "json"
    assert decode_json(response.text) == {"ok": True}


# test post with json body scenario
def test_post_with_json_body(mock_server: MockServer, transport_config: TransportConfig) -> None:
    """Verify test post with json body scenario."""
    mock_server.scenarios.append({"status": 200, "body": "ok"})

    with HttpTransport(transport_config) as transport:
        response = transport.request(
            "POST",
            f"{mock_server.base_url}/submit",
            json_body={"key": "value"},
        )

    assert response.status_code == 200
    assert json.loads(mock_server.last_body.decode("utf-8")) == {"key": "value"}
    assert mock_server.last_headers["content-type"].startswith("application/json")


# test retry on 500 then success scenario
def test_retry_on_500_then_success(
    mock_server: MockServer, transport_config: TransportConfig
) -> None:
    """Verify test retry on 500 then success scenario."""
    mock_server.scenarios.extend(
        [
            {"status": 500, "body": "server error"},
            {"status": 200, "body": "ok"},
        ]
    )

    with HttpTransport(transport_config) as transport:
        response = transport.request("GET", f"{mock_server.base_url}/retry-500")

    assert response.status_code == 200
    assert mock_server.hit_count == 2


# test retry on 429 then success scenario
def test_retry_on_429_then_success(
    mock_server: MockServer, transport_config: TransportConfig
) -> None:
    """Verify test retry on 429 then success scenario."""
    mock_server.scenarios.extend(
        [
            {"status": 429, "body": "rate limited"},
            {"status": 200, "body": "ok"},
        ]
    )

    with HttpTransport(transport_config) as transport:
        response = transport.request("GET", f"{mock_server.base_url}/retry-429")

    assert response.status_code == 200
    assert mock_server.hit_count == 2


# test no retry on 404 scenario
def test_no_retry_on_404(mock_server: MockServer, transport_config: TransportConfig) -> None:
    """Verify test no retry on 404 scenario."""
    mock_server.scenarios.append({"status": 404, "body": "not found"})

    with HttpTransport(transport_config) as transport, pytest.raises(TransportError):
        _ = transport.request("GET", f"{mock_server.base_url}/not-found")

    assert mock_server.hit_count == 1


def test_content_length_over_limit_raises_transport_error(mock_server: MockServer) -> None:
    mock_server.scenarios.append({"status": 200, "body": "0123456789"})
    config = TransportConfig(max_retries=0, max_response_bytes=5)

    with (
        HttpTransport(config) as transport,
        pytest.raises(TransportError, match="max_response_bytes"),
    ):
        _ = transport.request("GET", f"{mock_server.base_url}/too-large")

    assert mock_server.hit_count == 1


def test_streamed_body_over_limit_raises_transport_error(mock_server: MockServer) -> None:
    mock_server.scenarios.append({"status": 200, "body": "0123456789", "omit_content_length": True})
    config = TransportConfig(max_retries=0, max_response_bytes=5)

    with (
        HttpTransport(config) as transport,
        pytest.raises(TransportError, match="max_response_bytes"),
    ):
        _ = transport.request("GET", f"{mock_server.base_url}/stream-too-large")

    assert mock_server.hit_count == 1


# test timeout then success scenario
def test_timeout_then_success(mock_server: MockServer) -> None:
    """Verify test timeout then success scenario."""
    mock_server.scenarios.extend(
        [
            {"status": 200, "body": "slow", "delay": 5.0},
            {"status": 200, "body": "ok"},
        ]
    )
    config = TransportConfig(timeout=0.3, max_retries=2, retry_backoff_factor=0)

    with HttpTransport(config) as transport:
        response = transport.request("GET", f"{mock_server.base_url}/timeout-then-success")

    assert response.status_code == 200
    assert response.text == "ok"
    assert mock_server.hit_count == 2


# test timeout exhausted scenario
def test_timeout_exhausted(mock_server: MockServer) -> None:
    """Verify test timeout exhausted scenario."""
    mock_server.scenarios.extend(
        [
            {"status": 200, "body": "slow-1", "delay": 5.0},
            {"status": 200, "body": "slow-2", "delay": 5.0},
            {"status": 200, "body": "slow-3", "delay": 5.0},
        ]
    )
    config = TransportConfig(timeout=0.3, max_retries=2, retry_backoff_factor=0)

    with HttpTransport(config) as transport, pytest.raises(TransportTimeoutError):
        _ = transport.request("GET", f"{mock_server.base_url}/timeout-exhausted")

    assert mock_server.hit_count == 3


# test retryable status exhausted scenario
def test_retryable_status_exhausted(
    mock_server: MockServer, transport_config: TransportConfig
) -> None:
    """Verify test retryable status exhausted scenario."""
    mock_server.scenarios.extend(
        [
            {"status": 500, "body": "boom-1"},
            {"status": 500, "body": "boom-2"},
            {"status": 500, "body": "boom-3"},
        ]
    )

    with HttpTransport(transport_config) as transport, pytest.raises(TransportError):
        _ = transport.request("GET", f"{mock_server.base_url}/retryable-exhausted")

    assert mock_server.hit_count == 3


# test context manager lifecycle scenario
def test_context_manager_lifecycle(
    mock_server: MockServer, transport_config: TransportConfig
) -> None:
    """Verify test context manager lifecycle scenario."""
    mock_server.scenarios.append({"status": 200, "body": "ok"})

    transport = HttpTransport(transport_config)
    with transport as t:
        response = t.request("GET", f"{mock_server.base_url}/context")
        assert response.status_code == 200

    assert transport._client is None
