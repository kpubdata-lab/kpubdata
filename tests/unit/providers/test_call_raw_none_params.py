"""``call_raw`` leaves out a parameter whose value is ``None`` instead of sending "None".

``str(None)`` is the non-empty text ``"None"``, so an optional parameter the caller left
unset reached the provider as a filter value. The transport is a recording stand-in, so
the request each adapter builds is the one inspected.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import suppress
from typing import cast
from urllib.parse import parse_qsl, urlparse

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.exceptions import PublicDataError
from kpubdata.providers.fds.adapter import FdsAdapter
from kpubdata.providers.kipris.adapter import KiprisAdapter
from kpubdata.providers.korean.adapter import KoreanAdapter
from kpubdata.providers.kosis.adapter import KosisAdapter
from kpubdata.providers.lofin.adapter import LofinAdapter
from kpubdata.providers.neis.adapter import NeisAdapter
from kpubdata.providers.sgis.adapter import SgisAdapter
from kpubdata.transport.http import HttpTransport


class _Response:
    content = b"{}"
    status_code = 200
    headers: Mapping[str, str] = {}
    text = "{}"
    encoding = "utf-8"


class _Transport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def request(self, method: str, url: str, **kwargs: object) -> _Response:
        self.calls.append((url, kwargs))
        return _Response()


class _Auth:
    def get_access_token(self) -> str:
        return "token"


Builder = Callable[[_Transport], ProviderAdapter]


def _sgis(transport: _Transport) -> ProviderAdapter:
    return SgisAdapter(
        config=KPubDataConfig(provider_keys={"sgis": "id:secret"}),
        transport=cast(HttpTransport, cast(object, transport)),
        auth_client=_Auth(),
    )


def _plain(cls: Callable[..., ProviderAdapter], provider: str) -> Builder:
    def build(transport: _Transport) -> ProviderAdapter:
        return cls(
            config=KPubDataConfig(provider_keys={provider: "K"}),
            transport=cast(HttpTransport, cast(object, transport)),
        )

    return build


_CASES: list[tuple[str, Builder, str, str]] = [
    ("kipris", _plain(KiprisAdapter, "kipris"), "patent_family", ""),
    ("korean", _plain(KoreanAdapter, "korean"), "dict_search", ""),
    ("neis", _plain(NeisAdapter, "neis"), "school_info", "schoolInfo"),
    ("fds", _plain(FdsAdapter, "fds"), "traceability_item", "I1200"),
    ("lofin", _plain(LofinAdapter, "lofin"), "expenditure_budget", ""),
    ("kosis", _plain(KosisAdapter, "kosis"), "population_migration", ""),
    ("sgis", _sgis, "boundary.sido", "list"),
]


@pytest.mark.parametrize(("provider", "build", "dataset_key", "operation"), _CASES)
def test_call_raw_omits_a_none_parameter(
    provider: str, build: Builder, dataset_key: str, operation: str
) -> None:
    transport = _Transport()
    adapter = build(transport)
    dataset = adapter.get_dataset(dataset_key)

    with suppress(PublicDataError):  # the empty answer is not a valid payload
        adapter.call_raw(dataset, operation, {"q": "x", "optional_filter": None})

    assert transport.calls, provider
    url, kwargs = transport.calls[0]
    pairs = parse_qsl(urlparse(url).query, keep_blank_values=True)
    sent = kwargs.get("params")
    if isinstance(sent, Mapping):
        pairs.extend((str(k), str(v)) for k, v in sent.items())
    assert ("q", "x") in pairs, provider
    assert "optional_filter" not in dict(pairs), provider
    assert "None" not in [value for _, value in pairs], provider
