"""Credentials stay out of the DEBUG response preview and the transport config reprs.

The preview logged the first 500 characters of every body unmasked: the sgis
token request (``no_store``) put the access token in the log, and a key a
provider echoed back in an error body leaked as well. ``TransportConfig`` and
``TransportRequirements`` used the default dataclass ``repr``, which printed
``Authorization`` header values verbatim.
"""

from __future__ import annotations

import logging

import httpx
import pytest

from kpubdata.transport.http import HttpTransport, TransportConfig, TransportRequirements

_TOKEN = "FAKE-TOKEN-0001"
_KEY = "fake+key/0002=="


def _transport_returning(body: bytes, content_type: str) -> HttpTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": content_type}, content=body)

    transport = HttpTransport(TransportConfig(max_retries=0))
    transport._client = httpx.Client(transport=httpx.MockTransport(handler))
    return transport


def _previews(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        str(record.__dict__["preview"])
        for record in caplog.records
        if record.message == "HTTP response preview"
    ]


def test_no_store_response_body_is_withheld_from_preview(
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = b'{"errCd": 0, "result": {"accessToken": "' + _TOKEN.encode() + b'"}}'
    transport = _transport_returning(body, "application/json")

    with caplog.at_level(logging.DEBUG, logger="kpubdata.transport"):
        transport.request(
            "GET",
            "https://sgis.example.test/auth/authentication.json",
            params={"consumer_key": "ck", "consumer_secret": "cs"},
            no_store=True,
            secret_values=("ck", "cs"),
        )

    previews = _previews(caplog)
    assert previews == [f"[withheld, {len(body)} bytes]"]
    assert all(_TOKEN not in record.getMessage() for record in caplog.records)
    assert all(_TOKEN not in str(record.__dict__) for record in caplog.records)


@pytest.mark.parametrize("echoed", [_KEY, "fake%2Bkey%2F0002%3D%3D"])
def test_secret_echoed_in_body_is_redacted_from_preview(
    caplog: pytest.LogCaptureFixture, echoed: str
) -> None:
    body = f"<error><msg>invalid serviceKey {echoed}</msg></error>".encode()
    transport = _transport_returning(body, "application/xml")

    with caplog.at_level(logging.DEBUG, logger="kpubdata.transport"):
        transport.request(
            "GET",
            "https://api.example.test/resource",
            params={"serviceKey": _KEY},
            secret_values=(_KEY,),
        )

    previews = _previews(caplog)
    assert previews == ["<error><msg>invalid serviceKey [REDACTED]</msg></error>"]
    assert all(echoed not in str(record.__dict__) for record in caplog.records)


def test_secret_straddling_preview_cut_is_not_partly_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = ("a" * 495 + _KEY).encode()
    transport = _transport_returning(body, "text/plain")

    with caplog.at_level(logging.DEBUG, logger="kpubdata.transport"):
        transport.request("GET", "https://api.example.test/resource", secret_values=(_KEY,))

    assert _previews(caplog) == ["a" * 495 + "[REDA"]


def test_transport_config_repr_masks_credential_headers() -> None:
    config = TransportConfig(
        headers={
            "Authorization": "Bearer FAKE-SECRET-TOK",
            "Cookie": "session=FAKE-COOKIE",
            "Accept": "application/json",
        }
    )

    text = repr(config)

    assert "FAKE-SECRET-TOK" not in text
    assert "FAKE-COOKIE" not in text
    assert "'Authorization': '[REDACTED]'" in text
    assert "'Accept': 'application/json'" in text
    assert text.startswith("TransportConfig(timeout=30.0, max_retries=3,")
    # Equality and the stored headers are untouched.
    assert config == TransportConfig(headers=dict(config.headers or {}))
    assert config.headers is not None
    assert config.headers["Authorization"] == "Bearer FAKE-SECRET-TOK"


def test_transport_requirements_repr_masks_credential_headers() -> None:
    requirements = TransportRequirements(
        headers={"Proxy-Authorization": "Basic FAKE-PROXY", "User-Agent": "kpubdata"}
    )

    text = repr(requirements)

    assert "FAKE-PROXY" not in text
    assert "'Proxy-Authorization': '[REDACTED]'" in text
    assert "'User-Agent': 'kpubdata'" in text
    assert text.startswith("TransportRequirements(verify_ssl=None, headers=")
    assert requirements == TransportRequirements(
        headers={"Proxy-Authorization": "Basic FAKE-PROXY", "User-Agent": "kpubdata"}
    )
