"""Client.close() keeps closing dedicated provider transports after reuse (#973).

A client that is closed and then used again rebuilds its HTTP clients lazily.
close() used to forget the dedicated provider transports it owned, so the
second close() left the rebuilt connection pool open.
"""

from __future__ import annotations

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
