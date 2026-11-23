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

from kpubdata.transport import http as http_module
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


# A key long enough that a partial leak is unmistakable, with ``+``, ``/`` and ``=``.
_LONG_KEY = "ABCDEFGHIJ" * 4 + "+/=x5"


def _preview_of(body: str, *secrets: str) -> str:
    response = httpx.Response(200, headers={"content-type": "text/plain"}, content=body.encode())
    return http_module._response_preview(response, secret_values=secrets)


def _leaks_part_of(key: str, preview: str, *, min_len: int = 8) -> bool:
    return any(key[start : start + min_len] in preview for start in range(len(key) - min_len + 1))


def test_second_occurrence_past_the_cut_is_not_partly_logged() -> None:
    # Replacing the first occurrence shortens the text, which used to pull 25
    # characters of the second, unmatched occurrence in under the cut.
    body = _LONG_KEY + "a" * 465 + _LONG_KEY

    preview = _preview_of(body, _LONG_KEY)

    assert preview == "[REDACTED]" + "a" * 465 + "[REDACTED]"[:25]
    assert not _leaks_part_of(_LONG_KEY, preview)


@pytest.mark.parametrize("gap", range(440, 520, 3))
def test_no_part_of_a_key_reaches_the_preview_at_any_offset(gap: int) -> None:
    for lead in ("", _LONG_KEY, _LONG_KEY + "b" + _LONG_KEY):
        body = lead + "a" * gap + _LONG_KEY + "a" * 10 + _LONG_KEY

        preview = _preview_of(body, _LONG_KEY)

        assert len(preview) <= 500
        assert not _leaks_part_of(_LONG_KEY, preview), (lead, gap, preview)


@pytest.mark.parametrize(
    "echoed",
    [
        "fake+key\\/0002==",  # JSON-escaped slash
        "fake%2bkey%2f0002%3d%3d",  # quote, lowercase hex
    ],
)
def test_json_escaped_and_lowercase_hex_forms_are_redacted_in_preview(echoed: str) -> None:
    preview = _preview_of(f'{{"msg": "bad key {echoed}"}}', _KEY)

    assert preview == '{"msg": "bad key [REDACTED]"}'


def test_quote_plus_lowercase_hex_form_is_redacted_in_preview() -> None:
    key = "fake key+/="
    echoed = "fake+key%2b%2f%3d"  # quote_plus, lowercase hex

    assert _preview_of(f"bad key {echoed}", key) == "bad key [REDACTED]"


def test_lowercase_hex_form_is_masked_in_url_path() -> None:
    url = "https://api.example.test/svc/fake%2bkey%2f0002%3d%3d/json"

    masked = http_module._mask_url(url, secret_values=(_KEY,))

    assert masked == "https://api.example.test/svc/[REDACTED]/json"
