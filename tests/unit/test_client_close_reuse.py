"""Client.close() keeps closing dedicated provider transports after reuse (#973).

A client that is closed and then used again rebuilds its HTTP clients lazily.
close() used to forget the dedicated provider transports it owned, so the
second close() left the rebuilt connection pool open.

The other tests pin the rest of the lifecycle: no built-in adapter builds a
transport close() cannot reach, the context manager closes every pool on exit
(also when the body raises) and can be entered again, and the shared transport
follows the same rebuild-then-close rule.
"""

from __future__ import annotations

import pytest

from kpubdata.client import Client
from kpubdata.transport.http import HttpTransport


def _dedicated_transports(client: Client) -> list[HttpTransport]:
    client._registry.get("lofin")  # lofin declares its own transport requirements
    return list(client._provider_transports)


def test_close_after_reuse_closes_dedicated_provider_transports() -> None:
    client = Client(provider_keys={}, env_keys=False)
    transports = _dedicated_transports(client)
    assert transports, "lofin is expected to own a dedicated transport"

    client.close()
    for transport in transports:
        assert transport._client is None
        _ = transport.client  # reuse after close rebuilds the pool lazily

    client.close()

    assert all(transport._client is None for transport in transports)


def test_close_is_idempotent() -> None:
    client = Client(provider_keys={}, env_keys=False)
    transports = _dedicated_transports(client)

    client.close()
    client.close()

    assert all(transport._client is None for transport in transports)


def test_building_every_builtin_provider_creates_no_untracked_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[HttpTransport] = []
    original_init = HttpTransport.__init__

    def _recording_init(self: HttpTransport, *args: object, **kwargs: object) -> None:
        created.append(self)
        original_init(self, *args, **kwargs)

    client = Client(provider_keys={}, env_keys=False)
    monkeypatch.setattr(HttpTransport, "__init__", _recording_init)
    for provider_name in list(client._registry):
        client._registry.get(provider_name)

    tracked = {id(client._transport), *(id(t) for t in client._provider_transports)}
    untracked = [transport for transport in created if id(transport) not in tracked]
    assert untracked == [], "an adapter built its own transport that close() never reaches"


def test_context_manager_exit_closes_shared_and_dedicated_pools() -> None:
    client = Client(provider_keys={}, env_keys=False)
    transports = _dedicated_transports(client)

    with client as entered:
        assert entered is client
        shared_pool = client._transport._client
        assert shared_pool is not None  # __enter__ builds the shared pool eagerly
        dedicated_pools = [transport.client for transport in transports]

    assert client._transport._client is None
    assert shared_pool.is_closed
    assert all(transport._client is None for transport in transports)
    assert all(pool.is_closed for pool in dedicated_pools)


def test_shared_transport_rebuilds_after_close_and_closes_again() -> None:
    client = Client(provider_keys={}, env_keys=False)
    first_pool = client._transport.client

    client.close()
    second_pool = client._transport.client  # reuse after close builds a fresh pool

    assert first_pool.is_closed
    assert second_pool is not first_pool
    assert not second_pool.is_closed

    client.close()

    assert second_pool.is_closed


def test_context_manager_can_be_reentered_after_exit() -> None:
    client = Client(provider_keys={}, env_keys=False)

    with client:
        first_pool = client._transport.client
    with client:
        second_pool = client._transport.client
        assert not second_pool.is_closed

    assert first_pool.is_closed
    assert second_pool.is_closed


def test_context_manager_propagates_exceptions_and_still_closes() -> None:
    client = Client(provider_keys={}, env_keys=False)

    with pytest.raises(ValueError, match="boom"), client:
        pool = client._transport.client
        raise ValueError("boom")

    assert pool.is_closed
