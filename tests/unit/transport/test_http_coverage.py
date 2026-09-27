"""Test module.

This file ``tests/unit/transport/test_http_coverage.py`` defines test scenarios and helper objects.
For regression prevention and public contract validation verify core flows, exceptions, and edge conditions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from kpubdata.exceptions import TransportError
from kpubdata.transport.http import HttpTransport, TransportConfig


def _response(status_code: int) -> httpx.Response:
    """
    As internal helper for handles response processing.

    Args:
        status_code (int): input value provided by caller.

    Returns:
        httpx.Response: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.
    """
    request = httpx.Request("GET", "https://example.test/resource")
    return httpx.Response(status_code=status_code, request=request)


def _request_error() -> httpx.RequestError:
    """
    As internal helper for request error processing.

    Returns:
        httpx.RequestError: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.
    """
    request = httpx.Request("GET", "https://example.test/resource")
    return httpx.RequestError("boom", request=request)


# test repr reports configuration and client state Explains scenario validated by test.
def test_repr_reports_configuration_and_client_state() -> None:
    """
    test repr reports configuration and client state Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(timeout=2.5, max_retries=4, retry_backoff_factor=0.2))

    assert "client_initialized=False" in repr(transport)

    transport._client = MagicMock(spec=httpx.Client)
    assert "client_initialized=True" in repr(transport)


# test client property initializes client lazily Explains scenario validated by test.
def test_client_property_initializes_client_lazily() -> None:
    """
    test client property initializes client lazily Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport()
    fake_client = MagicMock(spec=httpx.Client)

    with patch.object(transport, "_build_client", return_value=fake_client) as build_client:
        client = transport.client

    assert client is fake_client
    build_client.assert_called_once_with()


# test request rejects negative max retries Explains scenario validated by test.
def test_request_rejects_negative_max_retries() -> None:
    """
    test request rejects negative max retries Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=-1))

    with pytest.raises(ValueError, match="max_retries"):
        _ = transport.request("GET", "https://example.test")


# test request rejects negative retry backoff factor Explains scenario validated by test.
def test_request_rejects_negative_retry_backoff_factor() -> None:
    """
    test request rejects negative retry backoff factor Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=0, retry_backoff_factor=-0.1))

    with pytest.raises(ValueError, match="retry_backoff_factor"):
        _ = transport.request("GET", "https://example.test")


# test request retries on request error then succeeds Explains scenario validated by test.
def test_request_retries_on_request_error_then_succeeds() -> None:
    """
    test request retries on request error then succeeds Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=1, retry_backoff_factor=0.5))

    with (
        patch("kpubdata.transport.http.httpx.Client.send") as request_mock,
        patch("kpubdata.transport.http.time.sleep") as sleep_mock,
    ):
        request_mock.side_effect = [_request_error(), _response(200)]

        response = transport.request("GET", "https://example.test")

    assert response.status_code == 200
    assert request_mock.call_count == 2
    sleep_mock.assert_called_once_with(0.5)


# test request error exhaustion raises transport error Explains scenario validated by test.
def test_request_error_exhaustion_raises_transport_error() -> None:
    """
    test request error exhaustion raises transport error Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=2, retry_backoff_factor=0.25))

    with (
        patch("kpubdata.transport.http.httpx.Client.send", side_effect=_request_error()),
        patch("kpubdata.transport.http.time.sleep") as sleep_mock,
        pytest.raises(TransportError, match="Request failed after 3 attempts"),
    ):
        transport.request("GET", "https://example.test")

    assert sleep_mock.call_count == 2


# test request unreachable state raises runtime error Explains scenario validated by test.
def test_request_unreachable_state_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """retry loop refactor(#414) contract after: identity retry does not consume attempt count.

    max_retries=0(1 total attempt)also in decode failure on identity retry via must recover.
    loop tail RuntimeErroris defensive code remains(unreachable — pragma no cover).
    """
    from tests.unit.transport.test_identity_retry import FakeGzipBrokenClient

    client = FakeGzipBrokenClient()
    transport = HttpTransport(TransportConfig(max_retries=0, cache=None))
    object.__setattr__(transport, "_client", client)

    response = transport.request("GET", "https://example.test/api")

    assert response.content == b'{"ok": true}'
    # 1st attempt(default headers) failure → identity retry happens within 1 attempt.
    assert client.sent_accept_encodings == [None, "identity"]
