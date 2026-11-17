"""Contain plaintext credential transport without forging HTTPS recording evidence (#893)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.executor import SpecDatasetAdapter, SpecExecutor
from kpubdata.core.models import Query
from kpubdata.core.spec import SpecDefinition, discover_specs
from kpubdata.exceptions import TransportError
from kpubdata.transport.cache import ResponseCache
from kpubdata.transport.http import HttpTransport, TransportConfig, TransportRequirements
from tests.unit.core.test_executor import _golden_spec, _ref

_CANARY = "canary-plaintext-transport-value"
_URL = "http://apis.data.go.kr/example"
_SEND = "kpubdata.transport.http.httpx.Client.send"


@pytest.mark.parametrize("location", ["params", "url", "header", "path", "config", "requirements"])
def test_plaintext_credentials_fail_before_cache_client_or_send(
    location: str,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    cache = ResponseCache(base_dir=tmp_path)
    config = TransportConfig(cache=cache, max_retries=3)
    requirements = None
    url = _URL
    params = None
    headers = None
    secret_values: tuple[str, ...] = ()
    if location == "params":
        params = {"sErViCeKeY": _CANARY}
    elif location == "url":
        url += f"?serviceKey={_CANARY}"
    elif location == "header":
        headers = {"Authorization": f"Bearer {_CANARY}"}
    elif location == "path":
        url += f"/{_CANARY}"
        secret_values = (_CANARY,)
    elif location == "config":
        config.headers = {"Authorization": f"Bearer {_CANARY}"}
    else:
        requirements = TransportRequirements(headers={"Authorization": f"Bearer {_CANARY}"})
    transport = HttpTransport(config, requirements=requirements)
    with (
        patch.object(
            cache, "get_entry", side_effect=AssertionError("cache must not be read")
        ) as read_cache,
        patch.object(
            transport, "_build_client", side_effect=AssertionError("client must not initialize")
        ) as build_client,
        patch(_SEND, side_effect=AssertionError("network send must not occur")) as send,
        caplog.at_level(logging.DEBUG),
        pytest.raises(TransportError, match="require HTTPS") as error,
    ):
        transport.request("GET", url, params=params, headers=headers, secret_values=secret_values)
    read_cache.assert_not_called()
    build_client.assert_not_called()
    send.assert_not_called()
    assert _CANARY not in str(error.value.to_dict())
    assert _CANARY not in caplog.text
    assert error.value.__context__ is None


@pytest.mark.parametrize(
    "url,params",
    [(_URL, {"page": "1"}), (_URL.replace("http:", "https:"), {"serviceKey": _CANARY})],
)
def test_unauthenticated_http_and_authenticated_https_remain_usable(
    url: str,
    params: dict[str, str],
) -> None:
    response = httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", url))
    with HttpTransport() as transport, patch(_SEND, return_value=response) as send:
        assert transport.request("GET", url, params=params).status_code == 200
    send.assert_called_once()


@pytest.mark.parametrize(
    "spec",
    [item for item in discover_specs() if item.endpoint.base_url.startswith("http://")],
    ids=lambda item: item.id,
)
def test_bundled_spec_cannot_send_its_configured_key_over_http(spec: SpecDefinition) -> None:
    assert spec.auth.type != "none"
    with HttpTransport() as transport:
        adapter = SpecDatasetAdapter(
            spec.provider,
            [spec],
            SpecExecutor(
                transport,
                KPubDataConfig(
                    provider_keys={"datago": _CANARY, spec.provider: _CANARY}, env_fallback=False
                ),
            ),
        )
        with (
            patch(_SEND, side_effect=AssertionError("network send must not occur")) as send,
            pytest.raises(TransportError, match="require HTTPS"),
        ):
            adapter.query_records(_ref(spec), Query(filters=dict(spec.examples[0].params)))
    send.assert_not_called()


def test_exact_historical_http_replay_remains_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _golden_spec("apt_trade")
    monkeypatch.setenv("KPUBDATA_MODE", "replay")
    with HttpTransport() as transport:
        adapter = SpecDatasetAdapter(
            "datago",
            [spec],
            SpecExecutor(
                transport, KPubDataConfig(provider_keys={"datago": _CANARY}, env_fallback=False)
            ),
        )
        with patch(_SEND, side_effect=AssertionError("network send must not occur")) as send:
            batch = adapter.query_records(
                _ref(spec), Query(filters={"LAWD_CD": "11110", "DEAL_YMD": "202401"})
            )
    assert batch.items
    send.assert_not_called()


def test_replay_miss_never_falls_back_to_plaintext_live(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("KPUBDATA_MODE", "replay")
    monkeypatch.setenv("KPUBDATA_REPLAY_DIR", str(tmp_path))
    with (
        HttpTransport() as transport,
        patch(_SEND, side_effect=AssertionError("network send must not occur")) as send,
        pytest.raises(TransportError, match="require HTTPS"),
    ):
        transport.request(
            "GET", _URL, params={"serviceKey": _CANARY}, dataset_id="datago.apt_trade"
        )
    send.assert_not_called()


@pytest.mark.parametrize("channel", ["headers", "params", "auth", "userinfo", "cookie"])
def test_prepared_client_credentials_cannot_reach_plaintext(channel: str) -> None:
    sent: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={})

    transport = HttpTransport()
    client = httpx.Client(transport=httpx.MockTransport(handle))
    transport._client = client
    # Normal client preparation/auth/hooks run, with no socket transport.
    url = _URL
    if channel == "headers":
        client.headers["Authorization"] = f"Bearer {_CANARY}"
    elif channel == "params":
        client.params = {"serviceKey": _CANARY}
    elif channel == "auth":
        client.auth = ("canary-user", _CANARY)
    elif channel == "userinfo":
        url = f"http://canary-user:{_CANARY}@apis.data.go.kr/example"
    else:
        client.cookies.set("session", _CANARY, domain="apis.data.go.kr", path="/")
    try:
        with pytest.raises(TransportError, match="require HTTPS") as error:
            transport.request("GET", url)
        assert sent == []
        assert _CANARY not in str(error.value.to_dict())
        assert error.value.__context__ is None
        transport.request("GET", url.replace("http:", "https:"))
        assert len(sent) == 1
        assert sent[0].url.scheme == "https"
    finally:
        transport.close()


def test_https_response_cookie_is_not_sent_on_subsequent_http() -> None:
    sent: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, headers={"Set-Cookie": f"session={_CANARY}; Path=/"})

    with HttpTransport() as transport:
        transport.client.close()
        transport._client = httpx.Client(transport=httpx.MockTransport(handle))
        transport.request("GET", _URL.replace("http:", "https:"))
        with pytest.raises(TransportError, match="require HTTPS"):
            transport.request("GET", _URL)
    assert len(sent) == 1
    assert sent[0].url.scheme == "https"


def test_opted_in_credentialed_redirect_cannot_downgrade_to_http() -> None:
    from kpubdata.transport.http import _in_flight_secrets

    sent: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(302, headers={"Location": _URL})

    with HttpTransport(TransportConfig(follow_credentialed_redirects=True)) as transport:
        transport.client.close()
        transport._client = httpx.Client(transport=httpx.MockTransport(handle))
        with pytest.raises(TransportError, match="require HTTPS"):
            transport.request("GET", _URL.replace("http:", "https:"), secret_values=(_CANARY,))
        assert _in_flight_secrets.get() == ()
    assert len(sent) == 1
    assert sent[0].url.scheme == "https"


def test_reused_client_keeps_one_guard_after_user_hooks() -> None:
    from kpubdata.transport.http import _require_https_credentials

    sent: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200)

    def add_cookie(request: httpx.Request) -> None:
        request.headers["Cookie"] = f"session={_CANARY}"

    with HttpTransport() as transport:
        transport.client.close()
        transport._client = httpx.Client(transport=httpx.MockTransport(handle))
        transport.request("GET", _URL)
        transport.request("GET", _URL)
        assert transport.client.event_hooks["request"].count(_require_https_credentials) == 1
        transport.client.event_hooks["request"].append(add_cookie)
        with pytest.raises(TransportError, match="require HTTPS"):
            transport.request("GET", _URL)
        assert transport.client.event_hooks["request"][-1] is _require_https_credentials
        assert transport.client.event_hooks["request"].count(_require_https_credentials) == 1
    assert len(sent) == 2


def test_declared_secrets_are_scoped_to_one_send_and_absent_from_extensions() -> None:
    from kpubdata.transport.http import _in_flight_secrets

    sent: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        assert _CANARY not in repr(request.extensions)
        return httpx.Response(200)

    with HttpTransport() as transport:
        transport.client.close()
        transport._client = httpx.Client(transport=httpx.MockTransport(handle))
        transport.request("GET", _URL.replace("http:", "https:"), secret_values=(_CANARY,))
        assert _in_flight_secrets.get() == ()
        transport.request("GET", _URL)
    assert len(sent) == 2
