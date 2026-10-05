"""A request that carries a credential is not redirected (#812).

The client used to follow every redirect. With the key in the query string, following
one re-sends the key to wherever the answer points — and over ``http://`` anyone on the
path can write that answer. A request without a credential is redirected as before.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from kpubdata.exceptions import TransportError
from kpubdata.transport.http import HttpTransport, TransportConfig

_URL = "http://apis.data.go.kr/service/rest/data"
_CANARY = "canary-value-for-redirect-test"
_SEND = "kpubdata.transport.http.httpx.Client.send"


def _redirect(location: str, status: int = 302) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers={"location": location},
        request=httpx.Request("GET", _URL),
    )


def _ok() -> httpx.Response:
    return httpx.Response(200, text='{"ok": true}', request=httpx.Request("GET", _URL))


def _followed(send: MagicMock) -> bool:
    return bool(send.call_args.kwargs["follow_redirects"])


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_a_redirect_of_a_request_with_a_key_is_refused(status: int) -> None:
    transport = HttpTransport(TransportConfig(max_retries=0))
    answer = _redirect("https://elsewhere.example/collect", status)

    with patch(_SEND, return_value=answer) as send, pytest.raises(TransportError) as excinfo:
        transport.request("GET", _URL, params={"serviceKey": _CANARY, "pageNo": "1"})

    assert _followed(send) is False
    assert send.call_count == 1
    assert excinfo.value.status_code == status
    message = str(excinfo.value)
    assert "elsewhere.example" in message
    assert "is not redirected" in message
    assert _CANARY not in message


def test_the_error_names_the_host_only_never_the_location() -> None:
    """The location can carry the key back; only where it points is said."""
    transport = HttpTransport(TransportConfig(max_retries=0))
    answer = _redirect(f"https://elsewhere.example/collect?serviceKey={_CANARY}&next=/private")

    with patch(_SEND, return_value=answer), pytest.raises(TransportError) as excinfo:
        transport.request("GET", _URL, params={"serviceKey": _CANARY})

    assert _CANARY not in str(excinfo.value)
    assert "/private" not in str(excinfo.value)
    assert excinfo.value.__cause__ is None


def test_a_key_passed_by_value_counts_as_a_credential() -> None:
    transport = HttpTransport(TransportConfig(max_retries=0))

    with (
        patch(_SEND, return_value=_redirect("https://elsewhere.example/")) as send,
        pytest.raises(TransportError),
    ):
        transport.request(
            "GET", f"http://openapi.seoul.go.kr:8088/{_CANARY}/json/x/1/5", secret_values=(_CANARY,)
        )

    assert _followed(send) is False


def test_a_request_without_a_credential_is_redirected_as_before() -> None:
    transport = HttpTransport(TransportConfig(max_retries=0))

    with patch(_SEND, return_value=_ok()) as send:
        transport.request("GET", _URL, params={"pageNo": "1"})

    assert _followed(send) is True


def test_a_request_with_a_key_that_is_not_redirected_goes_through() -> None:
    transport = HttpTransport(TransportConfig(max_retries=0))

    with patch(_SEND, return_value=_ok()) as send:
        response = transport.request("GET", _URL, params={"serviceKey": _CANARY})

    assert response.status_code == 200
    assert _followed(send) is False


def test_following_is_an_explicit_setting() -> None:
    assert TransportConfig().follow_credentialed_redirects is False
    transport = HttpTransport(TransportConfig(max_retries=0, follow_credentialed_redirects=True))

    with patch(_SEND, return_value=_ok()) as send:
        transport.request("GET", _URL, params={"serviceKey": _CANARY})

    assert _followed(send) is True
