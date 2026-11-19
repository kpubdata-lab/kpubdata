"""Regression tests for the transport review findings (cache, close race, error context)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from kpubdata.exceptions import RateLimitError, ServiceUnavailableError, TransportError
from kpubdata.transport import http as http_module
from kpubdata.transport._envelope import is_upstream_error_envelope
from kpubdata.transport.cache import ResponseCache
from kpubdata.transport.http import HttpTransport, TransportConfig, TransportRequirements

_URL = "https://example.test/resource"


def _install(transport: HttpTransport, handler: httpx.MockTransport) -> None:
    transport._client = httpx.Client(
        transport=handler, event_hooks={"request": [http_module._require_https_credentials]}
    )


def _patch_builder(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    def build(
        self: HttpTransport, requirements: TransportRequirements | None = None
    ) -> httpx.Client:
        return httpx.Client(
            transport=handler, event_hooks={"request": [http_module._require_https_credentials]}
        )

    monkeypatch.setattr(HttpTransport, "_build_client", build)


class TestEnvelopeWithMislabelledContentType:
    @pytest.mark.parametrize("content_type", ["text/plain", "text/html", ""])
    def test_xml_error_envelope_is_recognised(self, content_type: str) -> None:
        body = b"<response><header><resultCode>22</resultCode></header></response>"
        assert is_upstream_error_envelope(body, content_type) is True

    @pytest.mark.parametrize("content_type", ["text/plain", "text/html"])
    def test_json_error_envelope_is_recognised(self, content_type: str) -> None:
        body = b'{"response":{"header":{"resultCode":"22"}}}'
        assert is_upstream_error_envelope(body, content_type) is True

    def test_html_page_is_not_an_envelope(self) -> None:
        assert is_upstream_error_envelope(b"<html><body>22</body></html>", "text/html") is False

    def test_mislabelled_error_is_not_cached(self, tmp_path: Path) -> None:
        body = b"<response><header><resultCode>22</resultCode></header></response>"
        cache = ResponseCache(str(tmp_path))
        transport = HttpTransport(TransportConfig(cache=cache, max_retries=0), cache=cache)
        _install(
            transport,
            httpx.MockTransport(
                lambda r: httpx.Response(200, content=body, headers={"content-type": "text/plain"})
            ),
        )
        transport.request("GET", _URL)
        key = transport._make_cache_key(method="GET", url=_URL, params=None, headers=None)
        assert key is not None
        assert cache.get_entry(key) is None


class TestCacheKeyCoversConfiguredCredentials:
    def test_config_authorization_isolates_shared_cache(self, tmp_path: Path) -> None:
        def make(token: str) -> HttpTransport:
            cache = ResponseCache(str(tmp_path))
            transport = HttpTransport(
                TransportConfig(cache=cache, headers={"Authorization": token}), cache=cache
            )
            transport._client = httpx.Client(
                headers={"Authorization": token},
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(200, json={"who": r.headers["authorization"]})
                ),
                event_hooks={"request": [http_module._require_https_credentials]},
            )
            return transport

        make("Bearer A").request("GET", _URL)
        assert make("Bearer B").request("GET", _URL).json() == {"who": "Bearer B"}

    def test_requirements_authorization_changes_key(self, tmp_path: Path) -> None:
        cache = ResponseCache(str(tmp_path))
        keys = set()
        for token in ("Bearer A", "Bearer B"):
            transport = HttpTransport(
                TransportConfig(cache=cache),
                requirements=TransportRequirements(headers={"Authorization": token}),
                cache=cache,
            )
            keys.add(transport._make_cache_key(method="GET", url=_URL, params=None, headers=None))
        assert len(keys) == 2


class TestCloseRace:
    def test_send_on_a_closed_client_is_a_transport_error(self) -> None:
        transport = HttpTransport(TransportConfig(max_retries=0))
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
        client.event_hooks["request"] = [http_module._require_https_credentials]
        client.close()
        transport._client = client
        with pytest.raises(TransportError) as exc:
            transport.request("GET", _URL, provider="p", dataset_id="d")
        assert type(exc.value) is TransportError
        assert exc.value.provider == "p"

    def test_retry_in_flight_does_not_reopen_the_pool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503)

        _patch_builder(monkeypatch, httpx.MockTransport(handler))
        transport = HttpTransport(TransportConfig(max_retries=2), sleep=lambda s: transport.close())
        with pytest.raises(TransportError):
            transport.request("GET", _URL)
        assert calls["n"] == 1
        assert transport._client is None

    def test_client_reused_after_close_still_rebuilds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_builder(monkeypatch, httpx.MockTransport(lambda r: httpx.Response(200, json={})))
        transport = HttpTransport(TransportConfig(max_retries=0))
        transport.request("GET", _URL)
        transport.close()
        assert transport.request("GET", _URL).status_code == 200


class TestErrorContext:
    def test_timeout_carries_context(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("t", request=request)

        transport = HttpTransport(TransportConfig(max_retries=0))
        _install(transport, httpx.MockTransport(handler))
        with pytest.raises(TransportError) as exc:
            transport.request("GET", _URL, provider="p", dataset_id="d")
        assert (exc.value.provider, exc.value.dataset_id) == ("p", "d")

    def test_request_error_carries_context(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("c", request=request)

        transport = HttpTransport(TransportConfig(max_retries=0))
        _install(transport, httpx.MockTransport(handler))
        with pytest.raises(TransportError) as exc:
            transport.request("GET", _URL, provider="p", dataset_id="d")
        assert (exc.value.provider, exc.value.dataset_id) == ("p", "d")

    def test_decoding_error_carries_context(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.DecodingError("d", request=request)

        transport = HttpTransport(TransportConfig(max_retries=0))
        _install(transport, httpx.MockTransport(handler))
        with pytest.raises(TransportError) as exc:
            transport.request("GET", _URL, provider="p", dataset_id="d")
        assert (exc.value.provider, exc.value.dataset_id) == ("p", "d")

    def test_oversized_response_is_final_and_has_context(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"x" * 100)

        transport = HttpTransport(TransportConfig(max_retries=0, max_response_bytes=10))
        _install(transport, httpx.MockTransport(handler))
        with pytest.raises(TransportError) as exc:
            transport.request("GET", _URL, provider="p", dataset_id="d")
        assert exc.value.retryable is False
        assert exc.value.status_code == 200
        assert (exc.value.provider, exc.value.dataset_id) == ("p", "d")

    def test_503_beyond_the_retry_after_cap_is_service_unavailable(self) -> None:
        handler = httpx.MockTransport(
            lambda r: httpx.Response(503, headers={"Retry-After": "3600"})
        )
        transport = HttpTransport(TransportConfig(max_retries=1, max_retry_delay=60.0))
        _install(transport, handler)
        with pytest.raises(ServiceUnavailableError) as exc:
            transport.request("GET", _URL)
        assert exc.value.status_code == 503
        assert exc.value.retryable is True

    def test_429_beyond_the_retry_after_cap_stays_rate_limit(self) -> None:
        handler = httpx.MockTransport(
            lambda r: httpx.Response(429, headers={"Retry-After": "3600"})
        )
        transport = HttpTransport(TransportConfig(max_retries=1, max_retry_delay=60.0))
        _install(transport, handler)
        with pytest.raises(RateLimitError):
            transport.request("GET", _URL)


class TestCacheTtlSentinel:
    def test_explicit_default_value_wins_over_config(self) -> None:
        transport = HttpTransport(TransportConfig(cache_ttl_seconds=60), cache_ttl_seconds=86400)
        assert transport.cache_ttl_seconds == 86400

    def test_unset_falls_back_to_config(self) -> None:
        assert HttpTransport(TransportConfig(cache_ttl_seconds=60)).cache_ttl_seconds == 60
