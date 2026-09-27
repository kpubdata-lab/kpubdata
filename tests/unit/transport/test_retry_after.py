"""Test module.

This file ``tests/unit/transport/test_retry_after.py`` defines test scenarios and helper objects.
For regression prevention and public contract validation verify core flows, exceptions, and edge conditions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch

import httpx
import pytest

from kpubdata.exceptions import RateLimitError, TransportError
from kpubdata.transport.http import HttpTransport, TransportConfig


def _response(status_code: int, *, retry_after: str | None = None) -> httpx.Response:
    """
    As internal helper for handles response processing.

    Args:
        status_code (int): input value provided by caller.
        retry_after (str | None): input value provided by caller.

    Returns:
        httpx.Response: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.
    """
    request = httpx.Request("GET", "https://example.test/resource")
    headers = {"Retry-After": retry_after} if retry_after is not None else None
    return httpx.Response(status_code=status_code, headers=headers, request=request)


# test 429 with retry after seconds uses header delay Explains scenario validated by test.
def test_429_with_retry_after_seconds_uses_header_delay() -> None:
    """
    test 429 with retry after seconds uses header delay Verify scenario.

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
        request_mock.side_effect = [_response(429, retry_after="2"), _response(200)]

        response = transport.request("GET", "https://example.test/resource")

    assert response.status_code == 200
    assert request_mock.call_count == 2
    sleep_mock.assert_called_once_with(2.0)


# test 429 with retry after http date uses computed delay Explains scenario validated by test.
def test_429_with_retry_after_http_date_uses_computed_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    test 429 with retry after http date uses computed delay Verify scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    import kpubdata.transport.http as http_module

    fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    retry_at = fixed_now + timedelta(seconds=4)
    retry_after_header = format_datetime(retry_at, usegmt=True)

    class _FixedDatetime:
        """
        Class encapsulating _FixedDatetime role.

        This class ``tests/unit/transport/test_retry_after.py`` within module _FixedDatetimemanages its state and behavior together.
        Key methods: now.

        Property description:
            Properties defined in constructor and class body are reused by sub-methods in shared context.
        """

        @staticmethod
        def now(_tz: timezone) -> datetime:
            """
            now performs operation.

            Args:
                _tz (timezone): input value provided by caller.

            Returns:
                datetime: returns computation result or value from sub-call.

            Raises:
                can propagate exceptions from sub-dependencies as-is.
            """
            return fixed_now

    monkeypatch.setattr(http_module, "datetime", _FixedDatetime)

    transport = HttpTransport(TransportConfig(max_retries=1, retry_backoff_factor=0.5))

    with (
        patch("kpubdata.transport.http.httpx.Client.send") as request_mock,
        patch("kpubdata.transport.http.time.sleep") as sleep_mock,
    ):
        request_mock.side_effect = [_response(429, retry_after=retry_after_header), _response(200)]

        response = transport.request("GET", "https://example.test/resource")

    assert response.status_code == 200
    assert request_mock.call_count == 2
    sleep_mock.assert_called_once_with(4.0)


# test 429 with invalid retry after falls back to exponential backoff Explains scenario validated by test.
def test_429_with_invalid_retry_after_falls_back_to_exponential_backoff() -> None:
    """
    test 429 with invalid retry after falls back to exponential backoff Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=1, retry_backoff_factor=0.75))

    with (
        patch("kpubdata.transport.http.httpx.Client.send") as request_mock,
        patch("kpubdata.transport.http.time.sleep") as sleep_mock,
    ):
        request_mock.side_effect = [_response(429, retry_after="abc"), _response(200)]

        response = transport.request("GET", "https://example.test/resource")

    assert response.status_code == 200
    sleep_mock.assert_called_once_with(0.75)


# test 429 without retry after uses exponential backoff Explains scenario validated by test.
def test_429_without_retry_after_uses_exponential_backoff() -> None:
    """
    test 429 without retry after uses exponential backoff Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=1, retry_backoff_factor=0.25))

    with (
        patch("kpubdata.transport.http.httpx.Client.send") as request_mock,
        patch("kpubdata.transport.http.time.sleep") as sleep_mock,
    ):
        request_mock.side_effect = [_response(429), _response(200)]

        response = transport.request("GET", "https://example.test/resource")

    assert response.status_code == 200
    sleep_mock.assert_called_once_with(0.25)


# test 503 with retry after respects header delay Explains scenario validated by test.
def test_503_with_retry_after_respects_header_delay() -> None:
    """
    test 503 with retry after respects header delay Verify scenario.

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
        request_mock.side_effect = [_response(503, retry_after="3"), _response(200)]

        response = transport.request("GET", "https://example.test/resource")

    assert response.status_code == 200
    sleep_mock.assert_called_once_with(3.0)


# test non retryable status does not retry even with retry after Explains scenario validated by test.
def test_non_retryable_status_does_not_retry_even_with_retry_after() -> None:
    """
    test non retryable status does not retry even with retry after Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=3, retry_backoff_factor=0.5))

    with (
        patch(
            "kpubdata.transport.http.httpx.Client.send",
            return_value=_response(400, retry_after="9"),
        ) as request_mock,
        patch("kpubdata.transport.http.time.sleep") as sleep_mock,
        pytest.raises(TransportError, match="HTTP status error 400"),
    ):
        _ = transport.request("GET", "https://example.test/resource")

    assert request_mock.call_count == 1
    sleep_mock.assert_not_called()


def test_retry_after_beyond_the_cap_raises_instead_of_sleeping() -> None:
    """exceeding limit ``Retry-After``means immediate return not wait.

    when there was no limit server ``Retry-After: 3600`` gives library
    caller's thread hour holds slept. that retry not stop —
    "now cannot use"is signal not "here sleep"is instruction not.
    """
    transport = HttpTransport(TransportConfig(max_retries=1, max_retry_delay=60.0))

    with (
        patch("kpubdata.transport.http.httpx.Client.send") as request_mock,
        patch("kpubdata.transport.http.time.sleep") as sleep_mock,
    ):
        request_mock.side_effect = [_response(429, retry_after="3600"), _response(200)]

        with pytest.raises(RateLimitError) as exc:
            transport.request("GET", "https://example.test/resource")

    sleep_mock.assert_not_called()
    assert request_mock.call_count == 1
    assert exc.value.retryable is True
    assert exc.value.detail == {"retry_after": 3600.0, "max_retry_delay": 60.0}


def test_retry_after_within_the_cap_still_sleeps() -> None:
    transport = HttpTransport(TransportConfig(max_retries=1, max_retry_delay=60.0))

    with (
        patch("kpubdata.transport.http.httpx.Client.send") as request_mock,
        patch("kpubdata.transport.http.time.sleep") as sleep_mock,
    ):
        request_mock.side_effect = [_response(429, retry_after="30"), _response(200)]

        response = transport.request("GET", "https://example.test/resource")

    assert response.status_code == 200
    sleep_mock.assert_called_once_with(30.0)


def test_the_cap_does_not_touch_exponential_backoff() -> None:
    # limit applies only to server hint — no hint = existing backoff unchanged.
    transport = HttpTransport(
        TransportConfig(max_retries=1, retry_backoff_factor=0.5, max_retry_delay=0.1)
    )

    with (
        patch("kpubdata.transport.http.httpx.Client.send") as request_mock,
        patch("kpubdata.transport.http.time.sleep") as sleep_mock,
    ):
        request_mock.side_effect = [_response(503), _response(200)]

        response = transport.request("GET", "https://example.test/resource")

    assert response.status_code == 200
    sleep_mock.assert_called_once_with(0.5)


def test_the_cap_is_configurable() -> None:
    transport = HttpTransport(TransportConfig(max_retries=1, max_retry_delay=7200.0))

    with (
        patch("kpubdata.transport.http.httpx.Client.send") as request_mock,
        patch("kpubdata.transport.http.time.sleep") as sleep_mock,
    ):
        request_mock.side_effect = [_response(429, retry_after="3600"), _response(200)]

        assert transport.request("GET", "https://example.test/resource").status_code == 200

    sleep_mock.assert_called_once_with(3600.0)


def test_a_terminal_status_error_carries_its_status_code() -> None:
    """Masking breaks Raises chain, original response disappears too.

    status_code not carried then caller 401 and 503 way to distinguish message
    string only nothing.
    """
    transport = HttpTransport(TransportConfig(max_retries=1))

    with patch("kpubdata.transport.http.httpx.Client.send") as request_mock:
        request_mock.side_effect = [_response(401)]

        with pytest.raises(TransportError) as exc:
            transport.request("GET", "https://example.test/resource")

    assert exc.value.status_code == 401


def test_an_exhausted_429_is_a_rate_limit_error() -> None:
    # If 429 raised as generic TransportError caller cannot distinguish Limit exceeded from other transport failureand
    # cannot distinguish.
    from kpubdata.exceptions import RateLimitError

    transport = HttpTransport(TransportConfig(max_retries=1))

    with (
        patch("kpubdata.transport.http.httpx.Client.send") as request_mock,
        patch("kpubdata.transport.http.time.sleep"),
    ):
        request_mock.side_effect = [_response(429), _response(429)]

        with pytest.raises(RateLimitError) as exc:
            transport.request("GET", "https://example.test/resource")

    assert exc.value.status_code == 429
