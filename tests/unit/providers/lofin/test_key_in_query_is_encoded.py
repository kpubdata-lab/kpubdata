"""LOFIN puts its key into the query through an encoder, like every other value (#840).

The URL was built as ``?Key={api_key}&...`` with the key as it is. A key holding ``&``
or ``#`` cut the query short or began a new parameter, ``+`` reached the provider as a
space, and ``%`` followed by two hex digits as another character.

These go through the real ``HttpTransport`` and a real ``httpx.Client``; only the network
is replaced, so the query is the one the provider would be sent.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any
from urllib.parse import parse_qs, parse_qsl

import httpx
import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import Query
from kpubdata.exceptions import PublicDataError
from kpubdata.providers.lofin.adapter import LofinAdapter
from kpubdata.transport._sensitive import _secret_forms
from kpubdata.transport.http import HttpTransport, TransportConfig

#: Stand-in values with every character that means something in a query string.
_KEYS = [
    "plain-key-value",
    "with+plus/slash=equals",
    "with&ampersand#hash",
    "with%percent%2Fliteral",
    "with space?question",
]


class _Network:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            # An upstream that echoes the request it was sent, key included.
            return httpx.Response(self.status, text=f"rejected: {request.url}")
        return httpx.Response(200, json={})


@pytest.fixture()
def network(monkeypatch: pytest.MonkeyPatch) -> _Network:
    monkeypatch.delenv("KPUBDATA_MODE", raising=False)
    seen = _Network()
    real_client = httpx.Client

    def mocked_client(**kwargs: Any) -> httpx.Client:
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(seen.handle), **kwargs)

    monkeypatch.setattr(httpx, "Client", mocked_client)
    return seen


def _call(key: str, filters: dict[str, str] | None = None) -> None:
    transport = HttpTransport(TransportConfig(max_retries=0))
    adapter = LofinAdapter(
        config=KPubDataConfig(provider_keys={"datago": key}), transport=transport
    )
    try:
        adapter.query_records(
            adapter.get_dataset("expenditure_budget"), Query(filters=dict(filters or {}))
        )
    finally:
        transport.close()


@pytest.mark.parametrize("key", _KEYS)
def test_the_key_reaches_the_provider_as_it_was_configured(network: _Network, key: str) -> None:
    with pytest.raises(PublicDataError):
        _call(key)  # the empty answer is not a valid payload; the request was sent

    (request,) = network.requests
    query = parse_qs(request.url.query.decode("ascii"), keep_blank_values=True)
    # One ``Key``, holding exactly the configured value — nothing split off it.
    assert query["Key"] == [key]
    assert set(query) == {"Key", "Type", "pIndex", "pSize"}
    assert (query["Type"], query["pIndex"], query["pSize"]) == (["json"], ["1"], ["100"])


def test_filter_names_and_values_are_encoded_once(network: _Network) -> None:
    filters = {"accnut_year": "2024", "wdr_sfrnd_code_nm": "서울 & 경기", "note": "50%2Foff"}

    with pytest.raises(PublicDataError):
        _call("with&ampersand#hash", filters)

    (request,) = network.requests
    pairs = dict(parse_qsl(request.url.query.decode("ascii"), keep_blank_values=True))
    for name, value in filters.items():
        assert pairs[name] == value
    assert pairs["Key"] == "with&ampersand#hash"
    # Encoded once: a literal ``%2F`` in a value is sent as ``%252F``, not as ``/``.
    assert b"50%252Foff" in request.url.query


@pytest.mark.parametrize("key", _KEYS)
def test_no_form_of_the_key_is_in_the_error_or_the_log(
    network: _Network, caplog: pytest.LogCaptureFixture, key: str
) -> None:
    network.status = 500

    with caplog.at_level(logging.DEBUG), pytest.raises(PublicDataError) as failure:
        _call(key)

    rendered = "".join(
        traceback.format_exception(type(failure.value), failure.value, failure.value.__traceback__)
    )
    logged = caplog.text + "".join(str(record.__dict__) for record in caplog.records)
    # The key did travel — otherwise the check below shows nothing.
    assert (
        network.requests and key in parse_qs(network.requests[0].url.query.decode("ascii"))["Key"]
    )
    for form in _secret_forms((key,)):
        assert form not in str(failure.value)
        assert form not in rendered
        assert form not in logged
