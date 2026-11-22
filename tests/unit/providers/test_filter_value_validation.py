"""Custom adapters refuse unsupported filter values before any HTTP request.

API_SPEC promises that every ``list()`` omits a ``None`` filter, accepts booleans
only for spec parameters declared boolean, and raises ``InvalidRequestError`` for
lists, mappings, dates and non-finite numbers before transport. These adapters used
to send ``str(value)``, so a list went out as ``[1, 2]`` and ``None`` as ``None``.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from decimal import Decimal
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.exceptions import InvalidRequestError
from kpubdata.providers.fds.adapter import FdsAdapter
from kpubdata.providers.kipris.adapter import KiprisAdapter
from kpubdata.providers.korean.adapter import KoreanAdapter
from kpubdata.providers.kosis.adapter import KosisAdapter
from kpubdata.providers.law.adapter import LawAdapter
from kpubdata.providers.lofin.adapter import LofinAdapter
from kpubdata.providers.neis.adapter import NeisAdapter
from kpubdata.providers.sgis.adapter import SgisAdapter
from kpubdata.transport.http import HttpTransport


class _Stop(Exception):
    """Raised by the transport so a test can inspect the first request."""


class RecordingTransport:
    """Records each request and stops it; the refusal tests expect none."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> object:
        self.calls.append((method, url, kwargs.get("params")))
        raise _Stop


class FakeAuth:
    """SGIS token source that never touches the network."""

    def __init__(self) -> None:
        self.token_requests = 0

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        _ = force_refresh
        self.token_requests += 1
        return "token"

    def invalidate(self) -> None:
        return None


class _Adapter:
    """The two adapter methods these tests use."""

    def list_datasets(self) -> list[DatasetRef]:
        raise NotImplementedError

    def query_records(self, dataset: DatasetRef, query: Query) -> object:
        raise NotImplementedError


_KEYS = {
    "fds": "k",
    "kipris": "k",
    "korean": "k",
    "kosis": "k",
    "law": "k",
    "lofin": "k",
    "neis": "k",
    "sgis_consumer_key": "k",
    "sgis_consumer_secret": "k",
}


def _build(name: str, transport: RecordingTransport) -> object:
    config = KPubDataConfig(provider_keys=_KEYS)
    http = cast(HttpTransport, cast(object, transport))
    factories: dict[str, Callable[[], object]] = {
        "fds": lambda: FdsAdapter(config=config, transport=http),
        "kipris": lambda: KiprisAdapter(config=config, transport=http),
        "korean": lambda: KoreanAdapter(config=config, transport=http),
        "kosis": lambda: KosisAdapter(config=config, transport=http),
        "law": lambda: LawAdapter(config=config, transport=http),
        "lofin": lambda: LofinAdapter(config=config, transport=http),
        "neis": lambda: NeisAdapter(config=config, transport=http),
        "sgis": lambda: SgisAdapter(config=config, transport=http, auth_client=FakeAuth()),
    }
    return factories[name]()


ADAPTERS = ["fds", "kipris", "korean", "kosis", "law", "lofin", "neis", "sgis"]

BAD_VALUES = [
    pytest.param([1, 2], id="list"),
    pytest.param({"a": 1}, id="dict"),
    pytest.param(datetime.date(2024, 1, 1), id="date"),
    pytest.param(True, id="bool"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(Decimal("Infinity"), id="decimal-inf"),
]


def _query(name: str, value: object) -> Query:
    query = Query(filters={"zzfilter": value})
    if name == "kosis":
        query.start_date = "2024"
        query.end_date = "2024"
    return query


@pytest.mark.parametrize("value", BAD_VALUES)
@pytest.mark.parametrize("name", ADAPTERS)
def test_list_refuses_non_scalar_filter_before_http(name: str, value: object) -> None:
    transport = RecordingTransport()
    adapter = cast(_Adapter, _build(name, transport))
    dataset = adapter.list_datasets()[0]

    with pytest.raises(InvalidRequestError, match="'zzfilter'"):
        _ = adapter.query_records(dataset, _query(name, value))

    assert transport.calls == []


def test_sgis_refuses_before_requesting_a_token() -> None:
    transport = RecordingTransport()
    auth = FakeAuth()
    config = KPubDataConfig(provider_keys=_KEYS)
    adapter = SgisAdapter(
        config=config, transport=cast(HttpTransport, cast(object, transport)), auth_client=auth
    )

    with pytest.raises(InvalidRequestError):
        _ = adapter.query_records(adapter.list_datasets()[0], Query(filters={"zzfilter": [1]}))

    assert auth.token_requests == 0
    assert transport.calls == []


@pytest.mark.parametrize("name", ADAPTERS)
def test_list_omits_none_filter(name: str) -> None:
    transport = RecordingTransport()
    adapter = cast(_Adapter, _build(name, transport))
    dataset = adapter.list_datasets()[0]
    query = _query(name, None)
    if name in {"kipris", "korean", "neis"}:
        query.filters.update(_required_filters(dataset))

    with pytest.raises(_Stop):
        _ = adapter.query_records(dataset, query)

    _method, url, params = transport.calls[0]
    assert "zzfilter" not in url
    assert params is None or "zzfilter" not in cast(dict[str, object], params)


def _required_filters(dataset: DatasetRef) -> dict[str, object]:
    raw = dataset.raw_metadata.get("required_query_filters", [])
    return {str(name): "1" for name in cast(list[object], raw)}
