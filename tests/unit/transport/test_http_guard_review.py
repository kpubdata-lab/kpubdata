"""Exercise concurrent guard repair and anonymous cookie handling with real HTTPX."""

from __future__ import annotations

import threading
from collections.abc import Callable

import httpx
import pytest

from kpubdata.exceptions import TransportError
from kpubdata.transport.http import HttpTransport, _require_https_credentials

_URL = "http://example.test/data"
_CANARY = "synthetic-review-credential"


def test_guard_repair_never_leaves_a_concurrent_request_unprotected() -> None:
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    delivered: list[httpx.Request] = []
    errors: list[Exception] = []

    def pause_reader(request: httpx.Request) -> None:
        if threading.current_thread().name == "guard-reader":
            entered.set()
            assert release.wait(5)
            request.headers["Authorization"] = f"Bearer {_CANARY}"

    def no_op(_request: httpx.Request) -> None:
        pass

    class ScheduledHooks(list[Callable[..., object]]):
        def __setitem__(self, index, value) -> None:
            super().__setitem__(index, value)
            # Resume an already-running HTTPX iterator at the exact replacement
            # boundary, while the SDK writer still holds its private lock.
            release.set()
            assert finished.wait(5)

    def handle(request: httpx.Request) -> httpx.Response:
        delivered.append(request)
        return httpx.Response(200, json={})

    with HttpTransport() as transport:
        transport._client = httpx.Client(transport=httpx.MockTransport(handle))
        client = transport.client
        client.event_hooks["request"] = ScheduledHooks([pause_reader, _require_https_credentials])

        def reader() -> None:
            try:
                transport.request("GET", _URL)
            except Exception as exc:
                errors.append(exc)
            finally:
                finished.set()

        thread = threading.Thread(target=reader, name="guard-reader")
        thread.start()
        try:
            assert entered.wait(5)
            client.event_hooks["request"].append(no_op)
            assert transport.request("GET", _URL).status_code == 200
        finally:
            release.set()
            thread.join(5)
        assert not thread.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], TransportError)
        assert len(delivered) == 1
        assert "authorization" not in delivered[0].headers


def test_one_client_is_used_for_preparation_guard_and_send() -> None:
    delivered: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        delivered.append(request)
        return httpx.Response(200)

    clients = [
        httpx.Client(transport=httpx.MockTransport(handle), auth=("review", _CANARY))
        for _ in range(3)
    ]

    class SwitchingTransport(HttpTransport):
        reads = 0

        @property
        def client(self) -> httpx.Client:
            result = clients[min(self.reads, len(clients) - 1)]
            self.reads += 1
            return result

    transport = SwitchingTransport()
    try:
        with pytest.raises(TransportError, match="require HTTPS"):
            transport.request("GET", _URL)
        assert transport.reads == 1
        assert delivered == []
    finally:
        for client in clients:
            client.close()


@pytest.mark.parametrize("redirect", [False, True])
def test_anonymous_http_cookies_do_not_disable_subsequent_anonymous_requests(
    redirect: bool,
) -> None:
    delivered: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        delivered.append(request)
        headers = {"Set-Cookie": "WMONID=synthetic-routing-cookie; Path=/"}
        if redirect and len(delivered) == 1:
            return httpx.Response(302, headers={**headers, "Location": "/next"})
        return httpx.Response(200, headers=headers, json={})

    with HttpTransport() as transport:
        transport._client = httpx.Client(transport=httpx.MockTransport(handle))
        first = transport.request("GET", _URL)
        assert first.status_code == 200
        assert first.cookies["WMONID"] == "synthetic-routing-cookie"
        assert not transport.client.cookies
        assert transport.request("GET", _URL).status_code == 200
    assert len(delivered) == (3 if redirect else 2)
    assert all("cookie" not in request.headers for request in delivered)


def test_late_credential_error_retains_only_safe_request_context() -> None:
    from kpubdata.transport.http import _in_flight_context

    def never_send(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("credentialed HTTP request must not reach the network")

    with HttpTransport() as transport:
        transport._client = httpx.Client(
            transport=httpx.MockTransport(never_send), auth=("review", _CANARY)
        )
        with pytest.raises(TransportError) as failure:
            transport.request("GET", _URL, provider="datago", dataset_id="datago.review")
    assert failure.value.provider == "datago"
    assert failure.value.dataset_id == "datago.review"
    assert _CANARY not in repr(failure.value.to_dict())
    assert failure.value.__context__ is None
    assert _in_flight_context.get() == (None, None)


def test_managed_client_never_accepts_http_cookies_even_before_response_hooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.Client

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Set-Cookie": "WMONID=synthetic-routing; Path=/"})

    def factory(**kwargs) -> httpx.Client:
        client = real_client(**kwargs, transport=httpx.MockTransport(handle))

        def observe(response: httpx.Response) -> None:
            # An in-flight anonymous call must not contaminate another request's
            # jar even during the interval before SDK response cleanup runs.
            assert not client.cookies
            assert response.cookies["WMONID"] == "synthetic-routing"

        client.event_hooks["response"].append(observe)
        return client

    monkeypatch.setattr("kpubdata.transport.http.httpx.Client", factory)
    with HttpTransport() as transport:
        assert transport.request("GET", _URL).status_code == 200


def test_digest_auth_challenge_cannot_send_its_credentialed_http_retry() -> None:
    delivered: list[dict[str, str]] = []

    def challenge(request: httpx.Request) -> httpx.Response:
        delivered.append(dict(request.headers))
        return httpx.Response(
            401,
            headers={"WWW-Authenticate": 'Digest realm="review", nonce="synthetic", qop="auth"'},
        )

    with HttpTransport() as transport:
        transport._client = httpx.Client(
            transport=httpx.MockTransport(challenge), auth=httpx.DigestAuth("review", _CANARY)
        )
        with pytest.raises(TransportError, match="require HTTPS"):
            transport.request("GET", _URL)
    assert len(delivered) == 1
    assert "authorization" not in delivered[0]


def test_explicit_proxy_authorization_header_is_still_refused() -> None:
    transport = HttpTransport()
    try:
        with pytest.raises(TransportError, match="require HTTPS"):
            transport.request("GET", _URL, headers={"Proxy-Authorization": f"Basic {_CANARY}"})
        assert transport._client is None
    finally:
        transport.close()


def test_plaintext_response_cannot_delete_a_managed_secure_https_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.Client
    sent: list[dict[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(dict(request.headers))
        cookie = (
            "session=synthetic-secure-session; Secure; Path=/"
            if request.url.scheme == "https"
            else "session=synthetic-routing-cookie; Path=/"
        )
        return httpx.Response(200, headers={"Set-Cookie": cookie})

    def factory(**kwargs) -> httpx.Client:
        return real_client(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr("kpubdata.transport.http.httpx.Client", factory)
    with HttpTransport() as transport:
        transport.request("GET", _URL.replace("http:", "https:"))
        assert transport.client.cookies["session"] == "synthetic-secure-session"
        response = transport.request("GET", _URL)
        assert response.cookies["session"] == "synthetic-routing-cookie"
        assert transport.client.cookies["session"] == "synthetic-secure-session"
        transport.request("GET", _URL.replace("http:", "https:"))
    assert "cookie" not in sent[0] and "cookie" not in sent[1]
    assert sent[2]["cookie"] == "session=synthetic-secure-session"
