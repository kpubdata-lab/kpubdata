"""Threads that share a client build its HTTP client and its SGIS token once (#823).

Three places checked and then assigned with no lock. Each test makes the slow step slow
enough that, unlocked, every thread reaches it before any has finished.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import cast

import httpx
import pytest

from kpubdata import Client
from kpubdata.config import KPubDataConfig
from kpubdata.providers.sgis import auth as sgis_auth
from kpubdata.providers.sgis.auth import SgisAuthClient
from kpubdata.transport.http import HttpTransport, TransportConfig

_THREADS = 8


def _together(work: Callable[[], object]) -> list[object]:
    """Run ``work`` on every thread at once and return what each got."""
    start = threading.Barrier(_THREADS)
    results: list[object] = []
    failures: list[BaseException] = []

    def run() -> None:
        try:
            start.wait(timeout=10)
            results.append(work())
        except BaseException as error:  # noqa: BLE001 - reported below
            failures.append(error)

    threads = [threading.Thread(target=run) for _ in range(_THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert failures == []
    assert len(results) == _THREADS
    return results


def test_the_http_client_is_built_once(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[httpx.Client] = []
    real = HttpTransport._build_client

    def slow(self: HttpTransport, *args: object, **kwargs: object) -> httpx.Client:
        time.sleep(0.05)
        client = real(self)
        built.append(client)
        return client

    monkeypatch.setattr(HttpTransport, "_build_client", slow)
    transport = HttpTransport(TransportConfig())
    try:
        clients = _together(lambda: transport.client)

        assert len(built) == 1
        assert all(client is built[0] for client in clients)
    finally:
        transport.close()
    # Nothing was left open: the one client built is the one closed.
    assert built[0].is_closed


def test_close_and_reopen_still_build_one_at_a_time(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = HttpTransport(TransportConfig())
    first = transport.client
    transport.close()

    second = transport.client

    assert first.is_closed and not second.is_closed and second is not first
    transport.close()
    transport.close()  # closing twice is harmless


def _token_client() -> SgisAuthClient:
    config = KPubDataConfig(provider_keys={"sgis": "consumer-key:consumer-secret"})
    return SgisAuthClient(config=config, transport=cast(HttpTransport, object()))


def _slow_tokens(monkeypatch: pytest.MonkeyPatch, requested: list[str]) -> None:
    def request(self: SgisAuthClient) -> sgis_auth._TokenState:
        time.sleep(0.05)
        requested.append(f"token-{len(requested) + 1}")
        return sgis_auth._TokenState(
            value=requested[-1], expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

    monkeypatch.setattr(SgisAuthClient, "_request_access_token", request)


def test_the_sgis_token_is_requested_once(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[str] = []
    _slow_tokens(monkeypatch, requested)
    client = _token_client()

    tokens = _together(client.get_access_token)

    assert requested == ["token-1"]
    assert set(tokens) == {"token-1"}


def test_a_refresh_asked_by_many_at_once_is_one_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every thread saw ``token-1`` rejected and asks for a refresh; one request serves all."""
    requested: list[str] = []
    _slow_tokens(monkeypatch, requested)
    client = _token_client()
    assert client.get_access_token() == "token-1"

    tokens = _together(lambda: client.get_access_token(force_refresh=True))

    assert requested == ["token-1", "token-2"]
    assert set(tokens) == {"token-2"}


def test_a_refresh_asked_alone_always_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative: the lock does not turn a refresh into a cache hit."""
    requested: list[str] = []
    _slow_tokens(monkeypatch, requested)
    client = _token_client()

    assert client.get_access_token() == "token-1"
    assert client.get_access_token() == "token-1"
    assert client.get_access_token(force_refresh=True) == "token-2"
    client.invalidate()
    assert client.get_access_token() == "token-3"
    assert requested == ["token-1", "token-2", "token-3"]


def test_the_search_index_always_belongs_to_the_provider_asked_for() -> None:
    """Key and index were assigned separately; a reader in between got one provider's
    index under another's key."""
    client = Client(env_keys=False)
    try:
        catalog = client.datasets
        providers = ["datago", "seoul", "bok", "localdata"]
        stop = threading.Event()
        wrong: list[str] = []

        def search(provider: str) -> None:
            while not stop.is_set():
                for found in catalog.search("", provider=provider) or catalog.list(
                    provider=provider
                ):
                    if not found.id.startswith(f"{provider}."):
                        wrong.append(f"{provider}: {found.id}")
                        stop.set()

        threads = [threading.Thread(target=search, args=(name,)) for name in providers * 2]
        for thread in threads:
            thread.start()
        time.sleep(1.0)
        stop.set()
        for thread in threads:
            thread.join(timeout=30)
    finally:
        client.close()

    assert wrong == []
    cached = catalog._index_cache
    assert cached is not None
    key, index = cached
    assert tuple(item.dataset.id for item in index) == key[1]
