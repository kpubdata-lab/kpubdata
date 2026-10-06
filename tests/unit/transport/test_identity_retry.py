"""Unit tests for transport layer identity retry — KorService2-like decoding fault handling(#414).

If httpx.DecodingError occurs due to Content-Encoding mismatch, retry with Accept-Encoding: identity
retry once with identity encoding to recover response. goes through actual HttpTransport.request path.
"""

from __future__ import annotations

import httpx
import pytest

from kpubdata.exceptions import TransportError
from kpubdata.transport.http import HttpTransport, TransportConfig


class FakeGzipBrokenClient:
    """Default header request declares gzip + raw body to trigger DecodingError, and, identity request gets normal response."""

    def __init__(self, *, always_broken: bool = False) -> None:
        self.sent_accept_encodings: list[str | None] = []
        self.always_broken = always_broken

    def build_request(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        json: object = None,
    ) -> httpx.Request:
        accept = (headers or {}).get("Accept-Encoding")
        self.sent_accept_encodings.append(accept)
        return httpx.Request(method, url, params=params, headers=headers)

    def send(
        self, request: httpx.Request, stream: bool = True, follow_redirects: bool = True
    ) -> httpx.Response:
        accept = request.headers.get("accept-encoding")
        if accept == "identity" and not self.always_broken:
            return httpx.Response(200, content=b'{"ok": true}', request=request)
        # gzip declared + non-gzip body → httpx raises DecodingError on read.
        return httpx.Response(
            200,
            headers={"Content-Encoding": "gzip"},
            content=b"plain-not-gzip-body",
            request=request,
        )


def _transport_with(client: FakeGzipBrokenClient) -> HttpTransport:
    transport = HttpTransport(config=TransportConfig(timeout=5, max_retries=0, cache=None))
    sentinel = object()
    object.__setattr__(transport, "_client", None)
    transport.__dict__["_client"] = sentinel
    # client property returns _client so real client substitution
    transport.__dict__["_client"] = client  # type: ignore[assignment]
    return transport


def test_decoding_error_retries_with_identity() -> None:
    """On DecodingError, recover response via identity header retry."""
    client = FakeGzipBrokenClient()
    transport = _transport_with(client)

    response = transport.request("GET", "https://example.test/api", params={"a": "1"})

    assert response.status_code == 200
    assert response.content == b'{"ok": true}'
    assert client.sent_accept_encodings[0] is None
    assert client.sent_accept_encodings[1] == "identity"


def test_identity_failure_raises_transport_error() -> None:
    """If identity retry also fails, conclude with TransportError."""
    client = FakeGzipBrokenClient(always_broken=True)
    transport = _transport_with(client)

    with pytest.raises(TransportError):
        transport.request("GET", "https://example.test/api")
