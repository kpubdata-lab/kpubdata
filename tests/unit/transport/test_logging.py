"""Test module.

This file ``tests/unit/transport/test_logging.py`` defines test scenarios and helper objects.
For regression prevention and public contract validation verify core flows, exceptions, and edge conditions.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast
from unittest.mock import patch

import httpx
import pytest

import kpubdata.transport.http as http_module
from kpubdata.core.models import Query
from kpubdata.exceptions import TransportError, TransportTimeoutError
from kpubdata.transport.http import HttpTransport, TransportConfig


def _response_with_content(content: bytes, content_type: str) -> httpx.Response:
    """
    As internal helper for handles response with content processing.

    Args:
        content (bytes): input value provided by caller.
        content_type (str): input value provided by caller.

    Returns:
        httpx.Response: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.
    """
    request = httpx.Request("GET", "https://example.test/resource")
    return httpx.Response(
        status_code=200,
        headers={"content-type": content_type},
        content=content,
        request=request,
    )


# test request params log redacts service key Explains scenario validated by test.
def test_request_params_log_redacts_service_key(caplog: pytest.LogCaptureFixture) -> None:
    """
    test request params log redacts service key Verify scenario.

    Args:
        caplog (pytest.LogCaptureFixture): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=0))
    response = _response_with_content(b'{"ok": true}', "application/json")
    caplog.set_level(logging.DEBUG, logger="kpubdata.transport")

    with patch("kpubdata.transport.http.httpx.Client.send", return_value=response):
        _ = transport.request(
            "GET",
            "https://example.test/resource",
            params={"serviceKey": "super-secret", "query": "station"},
        )

    param_records = [record for record in caplog.records if record.message == "HTTP request params"]
    assert len(param_records) == 1
    params = cast(dict[str, str], cast(Any, param_records[0]).params)
    assert params == {"serviceKey": "[REDACTED]", "query": "station"}


# test response preview logged and truncated Explains scenario validated by test.
def test_response_preview_logged_and_truncated(caplog: pytest.LogCaptureFixture) -> None:
    """
    test response preview logged and truncated Verify scenario.

    Args:
        caplog (pytest.LogCaptureFixture): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=0))
    long_text = "a" * 900
    response = _response_with_content(long_text.encode("utf-8"), "text/plain; charset=utf-8")
    caplog.set_level(logging.DEBUG, logger="kpubdata.transport")

    with patch("kpubdata.transport.http.httpx.Client.send", return_value=response):
        _ = transport.request("GET", "https://example.test/resource")

    preview_records = [
        record for record in caplog.records if record.message == "HTTP response preview"
    ]
    assert len(preview_records) == 1
    content_length = cast(int, cast(Any, preview_records[0]).content_length)
    preview = cast(str, cast(Any, preview_records[0]).preview)
    assert content_length == 900
    assert preview == long_text[:500]
    assert len(preview) == 500


# test sanitize params redacts sensitive keys Explains scenario validated by test.
def test_sanitize_params_redacts_sensitive_keys() -> None:
    """
    test sanitize params redacts sensitive keys Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    sanitize_params = cast(
        Callable[[dict[str, object] | None], dict[str, str]],
        http_module._sanitize_params,
    )
    sanitized = sanitize_params(
        {
            "serviceKey": "a",
            "SERVICE_KEY": "b",
            "api_key": "c",
            "apikey": "d",
            "token": "e",
            "Authorization": "f",
            "secret": "g",
            "password": "h",
            "KEY": "i",
            "query": "station",
        }
    )

    assert sanitized == {
        "serviceKey": "[REDACTED]",
        "SERVICE_KEY": "[REDACTED]",
        "api_key": "[REDACTED]",
        "apikey": "[REDACTED]",
        "token": "[REDACTED]",
        "Authorization": "[REDACTED]",
        "secret": "[REDACTED]",
        "password": "[REDACTED]",
        "KEY": "[REDACTED]",
        "query": "station",
    }


# test response preview handles text and binary content Explains scenario validated by test.
def test_response_preview_handles_text_and_binary_content() -> None:
    """
    test response preview handles text and binary content Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    response_preview = cast(Callable[[httpx.Response], str], http_module._response_preview)
    text_response = _response_with_content(b'{"count": 1}', "application/json")
    binary_response = _response_with_content(b"\x00\x01\x02\x03", "application/octet-stream")

    assert response_preview(text_response) == '{"count": 1}'
    assert response_preview(binary_response) == "[binary content, 4 bytes]"


# test debug gating skips sanitization and preview helpers Explains scenario validated by test.
def test_debug_gating_skips_sanitization_and_preview_helpers() -> None:
    """
    test debug gating skips sanitization and preview helpers Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=0))
    response = _response_with_content(b"ok", "text/plain")

    with (
        patch("kpubdata.transport.http.logger.isEnabledFor", return_value=False),
        patch(
            "kpubdata.transport.http._sanitize_params",
            side_effect=AssertionError("_sanitize_params should not be called"),
        ),
        patch(
            "kpubdata.transport.http._response_preview",
            side_effect=AssertionError("_response_preview should not be called"),
        ),
        patch("kpubdata.transport.http.httpx.Client.send", return_value=response),
    ):
        _ = transport.request("GET", "https://example.test/resource", params={"serviceKey": "x"})


# test request logs include dataset context Explains scenario validated by test.
def test_request_logs_include_dataset_context(caplog: pytest.LogCaptureFixture) -> None:
    """
    test request logs include dataset context Verify scenario.

    Args:
        caplog (pytest.LogCaptureFixture): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=0))
    response = _response_with_content(b'{"ok": true}', "application/json")
    caplog.set_level(logging.DEBUG, logger="kpubdata.transport")

    with patch("kpubdata.transport.http.httpx.Client.send", return_value=response):
        _ = transport.request(
            "GET",
            "https://example.test/resource",
            dataset_id="datago.village_fcst",
            provider="datago",
        )

    for message in {
        "HTTP request start",
        "HTTP request success",
        "HTTP response preview",
    }:
        record = next(record for record in caplog.records if record.getMessage() == message)
        assert record.__dict__["dataset_id"] == "datago.village_fcst"
        assert record.__dict__["provider"] == "datago"


# test mask url redacts sensitive query params Explains scenario validated by test.
def test_mask_url_redacts_sensitive_query_params() -> None:
    """
    test mask url redacts sensitive query params Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    mask_url = cast(Callable[[str], str], http_module._mask_url)

    masked = mask_url(
        "https://api.example.test/data?serviceKey=secret&SERVICE_KEY=other&query=station"
    )
    assert masked == (
        "https://api.example.test/data?serviceKey=[REDACTED]&SERVICE_KEY=[REDACTED]&query=station"
    )
    assert mask_url("https://api.example.test/data?query=station") == (
        "https://api.example.test/data?query=station"
    )
    assert mask_url("https://api.example.test/data") == "https://api.example.test/data"
    assert mask_url("https://[invalid") == "[invalid url]"


# test exception message masks sensitive query params Explains scenario validated by test.
def test_exception_message_masks_sensitive_query_params() -> None:
    """
    test exception message masks sensitive query params Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=0))
    secret_url = "https://api.example.test/data?serviceKey=super-secret&query=station"
    response = httpx.Response(status_code=403, request=httpx.Request("GET", secret_url))

    with (
        patch("kpubdata.transport.http.httpx.Client.send", return_value=response),
        pytest.raises(TransportError) as excinfo,
    ):
        _ = transport.request("GET", secret_url)

    message = str(excinfo.value)
    assert "super-secret" not in message
    assert "serviceKey=[REDACTED]" in message
    assert "query=station" in message


# test request logs mask sensitive url Explains scenario validated by test.
def test_request_logs_mask_sensitive_url(caplog: pytest.LogCaptureFixture) -> None:
    """
    test request logs mask sensitive url Verify scenario.

    Args:
        caplog (pytest.LogCaptureFixture): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    transport = HttpTransport(TransportConfig(max_retries=0))
    secret_url = "https://api.example.test/data?serviceKey=super-secret&query=station"
    response = _response_with_content(b'{"ok": true}', "application/json")
    caplog.set_level(logging.DEBUG, logger="kpubdata.transport")

    with patch("kpubdata.transport.http.httpx.Client.send", return_value=response):
        _ = transport.request("GET", secret_url)

    start_records = [
        record for record in caplog.records if record.getMessage() == "HTTP request start"
    ]
    assert len(start_records) == 1
    logged_url = cast(str, cast(Any, start_records[0]).url)
    assert "super-secret" not in logged_url
    assert logged_url == "https://api.example.test/data?serviceKey=[REDACTED]&query=station"


# test status error chain suppressed when url masked Explains scenario validated by test.
def test_status_error_chain_suppressed_when_url_masked() -> None:
    """
    test status error chain suppressed when url masked Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        masked URL with HTTPStatusErrorwhen raised __cause__/__context__
        not kept original httpx Raisesin sensitive URLin tracebackin not exposed.
    """
    transport = HttpTransport(TransportConfig(max_retries=0))
    secret_url = "https://api.example.test/data?serviceKey=super-secret&query=station"
    response = httpx.Response(status_code=403, request=httpx.Request("GET", secret_url))

    with (
        patch("kpubdata.transport.http.httpx.Client.send", return_value=response),
        pytest.raises(TransportError) as excinfo,
    ):
        _ = transport.request("GET", secret_url)

    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


# test timeout chain suppressed when url masked Explains scenario validated by test.
def test_timeout_chain_suppressed_when_url_masked() -> None:
    """
    test timeout chain suppressed when url masked Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        masked URL with TimeoutExceptionwhen raised TransportTimeoutErroris
        original Raises __cause__in not kept.
    """
    transport = HttpTransport(TransportConfig(max_retries=0))
    secret_url = "https://api.example.test/data?serviceKey=super-secret&query=station"
    timeout_exc = httpx.TimeoutException("timed out", request=httpx.Request("GET", secret_url))

    with (
        patch("kpubdata.transport.http.httpx.Client.send", side_effect=timeout_exc),
        pytest.raises(TransportTimeoutError) as excinfo,
    ):
        _ = transport.request("GET", secret_url)

    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


# test request error chain suppressed when url masked Explains scenario validated by test.
def test_request_error_chain_suppressed_when_url_masked() -> None:
    """
    test request error chain suppressed when url masked Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        masked URL with RequestErrorwhen raised TransportErroris
        original Raises __cause__in not kept.
    """
    transport = HttpTransport(TransportConfig(max_retries=0))
    secret_url = "https://api.example.test/data?serviceKey=super-secret&query=station"
    request_exc = httpx.ConnectError("connect failed", request=httpx.Request("GET", secret_url))

    with (
        patch("kpubdata.transport.http.httpx.Client.send", side_effect=request_exc),
        pytest.raises(TransportError) as excinfo,
    ):
        _ = transport.request("GET", secret_url)

    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


# test exception chain preserved when url not masked Explains scenario validated by test.
def test_exception_chain_preserved_when_url_not_masked() -> None:
    """
    test exception chain preserved when url not masked Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        unmask URL: for debugging convenience original httpx Raises
        kept as-is in __cause__.
    """
    transport = HttpTransport(TransportConfig(max_retries=0))
    plain_url = "https://api.example.test/data?query=station"
    response = httpx.Response(status_code=403, request=httpx.Request("GET", plain_url))

    with (
        patch("kpubdata.transport.http.httpx.Client.send", return_value=response),
        pytest.raises(TransportError) as excinfo,
    ):
        _ = transport.request("GET", plain_url)

    assert isinstance(excinfo.value.__cause__, httpx.HTTPStatusError)


class TestPathSegmentSecretMasking:
    """Masking of keys carried as real values in URL path (#354)."""

    def test_path_segment_matching_secret_is_redacted(self) -> None:
        """seoul-shaped URL path key segments are substituted as [REDACTED]."""
        from kpubdata.transport.http import _mask_url

        url = "http://openapi.seoul.go.kr:8088/SECRET-KEY-123/json/SearchParkInfoService/1/10"
        masked = _mask_url(url, secret_values=("SECRET-KEY-123",))

        assert "SECRET-KEY-123" not in masked
        assert "[REDACTED]" in masked
        # service name, index have different values so not mistakenly substituted.
        assert "SearchParkInfoService" in masked
        assert masked.endswith("/1/10")

    def test_transport_logs_never_contain_path_key(self, caplog) -> None:
        """transport log(success/debug)raw path key does not remain."""
        transport = HttpTransport(TransportConfig(max_retries=0))
        response = httpx.Response(
            200,
            text='{"ok": true}',
            request=httpx.Request("GET", "http://openapi.seoul.go.kr:8088/REAL-KEY-9/json/x/1/5"),
        )
        with (
            patch("kpubdata.transport.http.httpx.Client.send", return_value=response),
            caplog.at_level(logging.DEBUG, logger="kpubdata.transport"),
        ):
            transport.request(
                "GET",
                "http://openapi.seoul.go.kr:8088/REAL-KEY-9/json/x/1/5",
                secret_values=("REAL-KEY-9",),
            )

        for record in caplog.records:
            assert "REAL-KEY-9" not in record.getMessage()

    def test_seoul_adapter_passes_its_key_as_secret_value(self, monkeypatch) -> None:
        """seoul adapter passes real keys as secret_values to transport call."""
        import json as json_module

        from kpubdata.config import KPubDataConfig
        from kpubdata.providers.seoul.adapter import SeoulAdapter

        captured: dict[str, object] = {}

        def fake_request(method, url, **kwargs):
            captured.update(kwargs)
            return httpx.Response(
                200,
                text=json_module.dumps(
                    {
                        "SearchParkInfoService": {
                            "list_total_count": 1,
                            "RESULT": {"CODE": "INFO-000"},
                            "row": [{}],
                        }
                    }
                ),
                request=httpx.Request("GET", url),
            )

        adapter = SeoulAdapter(config=KPubDataConfig(provider_keys={"seoul": "SEOUL-SECRET-42"}))
        monkeypatch.setattr(adapter._transport, "request", fake_request)

        dataset = adapter.get_dataset("park_usage")
        _ = adapter.query_records(dataset, Query(page_size=5))

        assert captured.get("secret_values") == ("SEOUL-SECRET-42",)


def test_mask_url_redacts_the_law_oc_key_parameter() -> None:
    """law(national law information)uses API key as ``OC`` parameter.

    by name alone does not look like credential missing from masking list and, Raises
    message URL has key left in plaintext.
    """
    mask_url = cast(Callable[[str], str], http_module._mask_url)

    masked = mask_url("https://www.law.go.kr/DRF/lawSearch.do?OC=real-law-key&target=law")

    assert "real-law-key" not in masked
    assert "OC=[REDACTED]" in masked
    assert "target=law" in masked


def test_mask_url_redacts_the_oc_parameter_case_insensitively() -> None:
    mask_url = cast(Callable[[str], str], http_module._mask_url)

    assert "real-law-key" not in mask_url("https://law.test/x?oc=real-law-key")


def test_mask_url_redacts_the_sgis_oauth_parameters() -> None:
    """sgis(statistical geographic information)uses OAuth-style names.

    list is not substring match but exact name so must list separately —
    ``consumer_key`` is ``key`` contains but not caught.
    """
    mask_url = cast(Callable[[str], str], http_module._mask_url)

    masked = mask_url(
        "https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json"
        "?consumer_key=real-key&consumer_secret=real-secret&accessToken=real-token"
    )

    for secret in ("real-key", "real-secret", "real-token"):
        assert secret not in masked
    assert masked.count("[REDACTED]") == 3


class TestKeysPassedAsParamsAreAlsoMasked:
    """passing key via ``params=`` path's Raises chain.

    whether to break chain ``_mask_url(url) != url`` judged by single. So key
    only when embedded in URL string broke and, ``params=`` when passed via URL stays as-is
    chain maintained — httpx is in Raises message params combines **final** URL puts
    so, that message ``__cause__`` goes through traceback remains as-is in.

    but key params sending via params actually is majority — datago, localdata, semas,
    sgis and spec executor all do this. existing tests all only URL string side
    checked not revealed.
    """

    _SECRET = "SUPERSECRETKEY"
    _URL = "https://apis.data.go.kr/service/rest/data"

    def _forbidden(self) -> httpx.Response:
        request = httpx.Request("GET", self._URL, params={"serviceKey": self._SECRET, "page": "1"})
        return httpx.Response(status_code=403, request=request)

    def test_the_chain_is_broken_when_the_key_travels_in_params(self) -> None:
        transport = HttpTransport(TransportConfig(max_retries=0))

        with (
            patch("kpubdata.transport.http.httpx.Client.send", return_value=self._forbidden()),
            pytest.raises(TransportError) as excinfo,
        ):
            _ = transport.request(
                "GET", self._URL, params={"serviceKey": self._SECRET, "page": "1"}
            )

        assert excinfo.value.__cause__ is None
        assert excinfo.value.__suppress_context__ is True

    def test_the_key_appears_nowhere_in_the_rendered_traceback(self) -> None:
        """``__cause__`` being None is not enough — must not appear in actual output."""
        import traceback

        transport = HttpTransport(TransportConfig(max_retries=0))

        with (
            patch("kpubdata.transport.http.httpx.Client.send", return_value=self._forbidden()),
            pytest.raises(TransportError) as excinfo,
        ):
            _ = transport.request(
                "GET", self._URL, params={"serviceKey": self._SECRET, "page": "1"}
            )

        rendered = "".join(
            traceback.format_exception(
                type(excinfo.value), excinfo.value, excinfo.value.__traceback__
            )
        )
        assert self._SECRET not in rendered

    def test_the_status_code_survives_the_broken_chain(self) -> None:
        """breaking chain makes original response disappear too — status code must go directly into Raises.

        datago of 403 guidanceand spec executor of AuthError sees this value.
        """
        transport = HttpTransport(TransportConfig(max_retries=0))

        with (
            patch("kpubdata.transport.http.httpx.Client.send", return_value=self._forbidden()),
            pytest.raises(TransportError) as excinfo,
        ):
            _ = transport.request(
                "GET", self._URL, params={"serviceKey": self._SECRET, "page": "1"}
            )

        assert excinfo.value.status_code == 403

    def test_a_request_without_any_credential_keeps_its_chain(self) -> None:
        """breaking chain for unauthenticated requests only harms debugging."""
        transport = HttpTransport(TransportConfig(max_retries=0))
        request = httpx.Request("GET", self._URL, params={"page": "1"})
        response = httpx.Response(status_code=403, request=request)

        with (
            patch("kpubdata.transport.http.httpx.Client.send", return_value=response),
            pytest.raises(TransportError) as excinfo,
        ):
            _ = transport.request("GET", self._URL, params={"page": "1"})

        assert isinstance(excinfo.value.__cause__, httpx.HTTPStatusError)

    def test_a_credential_header_also_breaks_the_chain(self) -> None:
        """providers using Authorization header also deserve same protection."""
        transport = HttpTransport(TransportConfig(max_retries=0))
        request = httpx.Request("GET", self._URL)
        response = httpx.Response(status_code=403, request=request)

        with (
            patch("kpubdata.transport.http.httpx.Client.send", return_value=response),
            pytest.raises(TransportError) as excinfo,
        ):
            _ = transport.request(
                "GET", self._URL, headers={"Authorization": f"Bearer {self._SECRET}"}
            )

        assert excinfo.value.__cause__ is None


class TestForbiddenDetectionDoesNotDependOnTheChain:
    """403 judgment dependent on ``__cause__`` makes masking and each invalidate other.

    datago is key params sends via params so, moment chain breaks ``__cause__`` based
    judgment finds nothing — user sees key registration guidance instead of generic error sees.
    """

    def test_datago_reads_the_status_code(self) -> None:
        from kpubdata.providers.datago.adapter import DataGoAdapter

        chained = TransportError("forbidden", provider="datago", status_code=403)

        assert DataGoAdapter._is_http_403(chained) is True
        assert DataGoAdapter._is_http_403(TransportError("boom", status_code=503)) is False
        assert DataGoAdapter._is_http_403(TransportError("boom")) is False


class TestTheExceptionChainIsFullyDetached:
    """``from None`` is ``__suppress_context__`` only sets.

    ``__context__`` has original httpx Raisesremains as-is and, its message has params omitted
    combines final URL — i.e. key — is in. standard traceback output and Sentry is that
    flag but, ``exc.__context__.request.url`` omitted directly read logger has
    visible.
    """

    _SECRET = "SUPERSECRETKEY"
    _URL = "https://apis.data.go.kr/service/rest/data"

    def _forbidden(self) -> httpx.Response:
        request = httpx.Request("GET", self._URL, params={"serviceKey": self._SECRET, "page": "1"})
        return httpx.Response(status_code=403, request=request)

    def test_context_is_cleared_not_just_suppressed(self) -> None:
        transport = HttpTransport(TransportConfig(max_retries=0))

        with (
            patch("kpubdata.transport.http.httpx.Client.send", return_value=self._forbidden()),
            pytest.raises(TransportError) as excinfo,
        ):
            _ = transport.request(
                "GET", self._URL, params={"serviceKey": self._SECRET, "page": "1"}
            )

        assert excinfo.value.__cause__ is None
        assert excinfo.value.__context__ is None, (
            "__suppress_context__ 만으로는 부족하다 — 체인을 직접 읽는 쪽에 키가 보인다"
        )

    def test_the_key_is_unreachable_through_the_whole_chain(self) -> None:
        """no key reachable from Raises anywhere."""
        transport = HttpTransport(TransportConfig(max_retries=0))

        with (
            patch("kpubdata.transport.http.httpx.Client.send", return_value=self._forbidden()),
            pytest.raises(TransportError) as excinfo,
        ):
            _ = transport.request(
                "GET", self._URL, params={"serviceKey": self._SECRET, "page": "1"}
            )

        reachable: list[str] = []
        node: BaseException | None = excinfo.value
        seen: set[int] = set()
        while node is not None and id(node) not in seen:
            seen.add(id(node))
            reachable.append(str(node))
            request = getattr(node, "request", None)
            if request is not None:
                reachable.append(str(request.url))
            node = node.__cause__ or node.__context__

        assert self._SECRET not in "".join(reachable)

    def test_a_request_without_a_credential_keeps_its_context(self) -> None:
        """breaking chain for unauthenticated requests only harms debugging."""
        transport = HttpTransport(TransportConfig(max_retries=0))
        response = httpx.Response(
            status_code=403, request=httpx.Request("GET", self._URL, params={"page": "1"})
        )

        with (
            patch("kpubdata.transport.http.httpx.Client.send", return_value=response),
            pytest.raises(TransportError) as excinfo,
        ):
            _ = transport.request("GET", self._URL, params={"page": "1"})

        assert isinstance(excinfo.value.__cause__, httpx.HTTPStatusError)


class TestOneSensitiveNameList:
    """three lists must diverge — actually diverges.

    ``cache.py`` in sgis of ``consumer_secret`` was missing and, in list not
    name fingerprint not as-is raw Cache key material becomes.
    """

    def test_every_module_reads_the_same_object(self) -> None:
        from kpubdata.transport import cache as cache_module
        from kpubdata.transport import replay as replay_module
        from kpubdata.transport._sensitive import SENSITIVE_PARAM_KEYS

        assert http_module.SENSITIVE_PARAM_KEYS is SENSITIVE_PARAM_KEYS
        assert cache_module.SENSITIVE_PARAM_KEYS is SENSITIVE_PARAM_KEYS
        assert replay_module.SENSITIVE_PARAM_KEYS is SENSITIVE_PARAM_KEYS

    def test_the_sgis_secret_is_fingerprinted_in_cache_keys(self) -> None:
        from kpubdata.transport.cache import make_cache_key

        mine = make_cache_key("GET", "https://x/y", {"consumer_secret": "MINE", "q": "1"}, {})
        yours = make_cache_key("GET", "https://x/y", {"consumer_secret": "YOURS", "q": "1"}, {})

        assert "MINE" not in mine, "원문이 캐시 키 재료로 들어가면 안 된다"
        assert mine != yours, "자격이 다르면 캐시 엔트리도 달라야 한다"
