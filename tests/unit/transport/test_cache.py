"""Test module.

This file ``tests/unit/transport/test_cache.py`` defines test scenarios and helper objects.
For regression prevention and public contract validation verify core flows, exceptions, and edge conditions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast
from unittest.mock import patch

import httpx
import pytest

from kpubdata.client import Client
from kpubdata.exceptions import ConfigError, TransportError
from kpubdata.transport.cache import ResponseCache, make_cache_key
from kpubdata.transport.http import HttpTransport, TransportConfig


def _response(
    status_code: int = 200,
    *,
    method: str = "GET",
    url: str = "https://example.test/resource",
    content: bytes = b'{"ok": true}',
) -> httpx.Response:
    """
    As internal helper for handles response processing.

    Args:
        status_code (int): input value provided by caller.
        method (str): input value provided by caller.
        url (str): input value provided by caller.
        content (bytes): input value provided by caller.

    Returns:
        httpx.Response: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.
    """
    request = httpx.Request(method, url)
    return httpx.Response(status_code=status_code, content=content, request=request)


# test response cache roundtrip Explains scenario validated by test.
def test_response_cache_roundtrip(tmp_path: Path) -> None:
    """
    test response cache roundtrip Verify scenario.

    Args:
        tmp_path (Path): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    cache = ResponseCache(base_dir=tmp_path)

    cache.set("abc", b"payload", ttl_seconds=60)

    assert cache.get("abc") == (b"payload", "")


# test response cache expiry Explains scenario validated by test.
def test_response_cache_expiry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    test response cache expiry Verify scenario.

    Args:
        tmp_path (Path): input value provided by caller.
        monkeypatch (pytest.MonkeyPatch): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    cache = ResponseCache(base_dir=tmp_path)
    now = 1_700_000_000.0

    monkeypatch.setattr("kpubdata.transport.cache.time.time", lambda: now)
    cache.set("abc", b"payload", ttl_seconds=10)

    monkeypatch.setattr("kpubdata.transport.cache.time.time", lambda: now + 11)
    assert cache.get("abc") is None
    assert not (tmp_path / "abc.json").exists()


# test response cache missing key returns none Explains scenario validated by test.
def test_response_cache_missing_key_returns_none(tmp_path: Path) -> None:
    """
    test response cache missing key returns none Verify scenario.

    Args:
        tmp_path (Path): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    cache = ResponseCache(base_dir=tmp_path)

    assert cache.get("missing") is None


# test make cache key redacts secret values Explains scenario validated by test.
def test_make_cache_key_isolates_credentials() -> None:
    """
    test make cache key redacts secret values Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    key_one = make_cache_key(
        "GET",
        "https://example.test/resource",
        {"serviceKey": "secret-a", "query": "stations"},
        {"Authorization": "Bearer aaa", "Accept": "application/json"},
    )
    key_two = make_cache_key(
        "GET",
        "https://example.test/resource",
        {"query": "stations", "serviceKey": "secret-b"},
        {"Accept": "application/json", "Authorization": "Bearer bbb"},
    )
    key_three = make_cache_key(
        "GET",
        "https://example.test/resource",
        {"query": "other", "serviceKey": "secret-b"},
        {"Accept": "application/json", "Authorization": "Bearer bbb"},
    )

    # #263: Different credentials = different cache key even for same endpoint.
    assert key_one != key_two
    assert key_one != key_three
    assert key_two != key_three


# test response cache filesystem errors are swallowed Explains scenario validated by test.
def test_response_cache_filesystem_errors_are_swallowed(tmp_path: Path) -> None:
    """
    test response cache filesystem errors are swallowed Verify scenario.

    Args:
        tmp_path (Path): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    blocked_path = tmp_path / "blocked"
    _ = blocked_path.write_text("not-a-directory", encoding="utf-8")
    cache = ResponseCache(base_dir=blocked_path)

    cache.set("abc", b"payload", ttl_seconds=60)
    assert cache.get("abc") is None
    cache.clear()
    cache.clear_expired()


# test http transport get cache hit logs and skips network Explains scenario validated by test.
def test_http_transport_get_cache_hit_logs_and_skips_network(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    test http transport get cache hit logs and skips network Verify scenario.

    Args:
        tmp_path (Path): input value provided by caller.
        caplog (pytest.LogCaptureFixture): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    cache = ResponseCache(base_dir=tmp_path)
    transport = HttpTransport(TransportConfig(max_retries=0), cache=cache, cache_ttl_seconds=60)
    response = _response(content=b'{"cached": false}')
    caplog.set_level(logging.DEBUG, logger="kpubdata.transport")

    with patch("kpubdata.transport.http.httpx.Client.send", return_value=response) as request_mock:
        first = transport.request(
            "GET",
            "https://example.test/resource",
            params={"serviceKey": "secret", "page": "1"},
            dataset_id="datago.tour_kor_area",
            provider="datago",
        )
        second = transport.request(
            "GET",
            "https://example.test/resource",
            params={"page": "1", "serviceKey": "rotated-secret"},
            dataset_id="datago.tour_kor_area",
            provider="datago",
        )
        third = transport.request(
            "GET",
            "https://example.test/resource",
            params={"serviceKey": "secret", "page": "1"},
            dataset_id="datago.tour_kor_area",
            provider="datago",
        )

    # #263: Changing credentials = no reuse of previous response even for same endpoint
    # (2 network calls), Returning to original credential hits own cache.
    assert first.content == second.content == third.content == b'{"cached": false}'
    assert request_mock.call_count == 2

    miss_records = [
        record for record in caplog.records if record.getMessage() == "transport cache miss; stored"
    ]
    hit_records = [
        record for record in caplog.records if record.getMessage() == "transport cache hit"
    ]
    assert len(miss_records) == 2
    assert len(hit_records) == 1
    assert hit_records[0].__dict__["provider"] == "datago"
    # two misses are different cache keys(credential isolation), hit is first request(secret) key identical.
    first_key = miss_records[0].__dict__["cache_key"]
    second_key = miss_records[1].__dict__["cache_key"]
    assert first_key != second_key
    assert hit_records[0].__dict__["cache_key"] == first_key


# test http transport post is never cached Explains scenario validated by test.
def test_http_transport_post_is_never_cached(tmp_path: Path) -> None:
    """
    test http transport post is never cached Verify scenario.

    Args:
        tmp_path (Path): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    cache = ResponseCache(base_dir=tmp_path)
    transport = HttpTransport(TransportConfig(max_retries=0), cache=cache, cache_ttl_seconds=60)
    response = _response(method="POST", content=b'{"created": true}')

    with patch("kpubdata.transport.http.httpx.Client.send", return_value=response) as request_mock:
        _ = transport.request("POST", "https://example.test/resource", content=b"{}")
        _ = transport.request("POST", "https://example.test/resource", content=b"{}")

    assert request_mock.call_count == 2
    assert list(tmp_path.glob("*.json")) == []


# test http transport non 2xx is never cached Explains scenario validated by test.
def test_http_transport_non_2xx_is_never_cached(tmp_path: Path) -> None:
    """
    test http transport non 2xx is never cached Verify scenario.

    Args:
        tmp_path (Path): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    cache = ResponseCache(base_dir=tmp_path)
    transport = HttpTransport(TransportConfig(max_retries=0), cache=cache, cache_ttl_seconds=60)
    response = _response(status_code=404)

    with (
        patch("kpubdata.transport.http.httpx.Client.send", return_value=response),
        pytest.raises(TransportError),
    ):
        _ = transport.request("GET", "https://example.test/resource")

    assert list(tmp_path.glob("*.json")) == []


# test client from env enables cache and honors overrides Explains scenario validated by test.
def test_client_from_env_enables_cache_and_honors_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    test client from env enables cache and honors overrides Verify scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): input value provided by caller.
        tmp_path (Path): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    monkeypatch.setenv("KPUBDATA_CACHE", "1")
    monkeypatch.setenv("KPUBDATA_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("KPUBDATA_CACHE_TTL", "12")

    client = Client.from_env()
    transport_config = cast(TransportConfig, client.__dict__["_transport_config"])

    assert transport_config.cache_ttl_seconds == 12
    assert isinstance(transport_config.cache, ResponseCache)
    assert transport_config.cache is not None
    assert transport_config.cache.base_dir == tmp_path


# test client from env explicit cache false disables env cache Explains scenario validated by test.
def test_client_from_env_explicit_cache_false_disables_env_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    test client from env explicit cache false disables env cache Verify scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): input value provided by caller.
        tmp_path (Path): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    monkeypatch.setenv("KPUBDATA_CACHE", "1")
    monkeypatch.setenv("KPUBDATA_CACHE_DIR", str(tmp_path))

    client = Client.from_env(cache=False)
    transport_config = cast(TransportConfig, client.__dict__["_transport_config"])

    assert transport_config.cache is None


# test client from env invalid cache ttl raises config error Explains scenario validated by test.
def test_client_from_env_invalid_cache_ttl_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    test client from env invalid cache ttl raises config error Verify scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        invalid KPUBDATA_CACHE_TTL value reports as ConfigError.
    """
    monkeypatch.setenv("KPUBDATA_CACHE_TTL", "abc")

    with pytest.raises(ConfigError) as exc_info:
        Client.from_env()

    error = exc_info.value
    assert "KPUBDATA_CACHE_TTL" in str(error)
    assert "integer" in str(error)
    assert "'abc'" in str(error)
    assert isinstance(error.__cause__, ValueError)


# test client from env invalid cache ttl explicit override takes priority Explains scenario validated by test.
def test_client_from_env_invalid_cache_ttl_explicit_override_takes_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    test client from env invalid cache ttl explicit override takes priority Verify scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        explicit override takes priority over env var.
    """
    monkeypatch.setenv("KPUBDATA_CACHE_TTL", "abc")

    client = Client.from_env(cache_ttl_seconds=30)
    transport_config = cast(TransportConfig, client.__dict__["_transport_config"])

    assert transport_config.cache_ttl_seconds == 30


# test client from env missing cache ttl uses default Explains scenario validated by test.
def test_client_from_env_missing_cache_ttl_uses_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    test client from env missing cache ttl uses default Verify scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        default 86400 used when env var missing.
    """
    monkeypatch.delenv("KPUBDATA_CACHE_TTL", raising=False)

    client = Client.from_env()
    transport_config = cast(TransportConfig, client.__dict__["_transport_config"])

    assert transport_config.cache_ttl_seconds == 86400


# test client from env empty cache ttl uses default Explains scenario validated by test.
def test_client_from_env_empty_cache_ttl_uses_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    test client from env empty cache ttl uses default Verify scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        default 86400 used when env var empty.
    """
    monkeypatch.setenv("KPUBDATA_CACHE_TTL", "")

    client = Client.from_env()
    transport_config = cast(TransportConfig, client.__dict__["_transport_config"])

    assert transport_config.cache_ttl_seconds == 86400
