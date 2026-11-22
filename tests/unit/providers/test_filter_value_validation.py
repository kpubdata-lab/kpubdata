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


def _query(name: str, value: object, dataset: DatasetRef) -> Query:
    # Required filters are supplied, so a refusal is the value check's, never the
    # missing-filter check's (kipris needs applicationNumber, for example).
    query = Query(filters={**_required_filters(dataset), "zzfilter": value})
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
        _ = adapter.query_records(dataset, _query(name, value, dataset))

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
    query = _query(name, None, dataset)

    with pytest.raises(_Stop):
        _ = adapter.query_records(dataset, query)

    _method, url, params = transport.calls[0]
    assert "zzfilter" not in url
    assert params is None or "zzfilter" not in cast(dict[str, object], params)


def _required_filters(dataset: DatasetRef) -> dict[str, object]:
    raw = dataset.raw_metadata.get("required_query_filters", [])
    return {str(name): "1" for name in cast(list[object], raw)}


def test_kipris_refuses_a_non_scalar_application_number_before_http() -> None:
    """kipris sends only applicationNumber, so that is the filter the value rule must reach."""
    transport = RecordingTransport()
    adapter = cast(_Adapter, _build("kipris", transport))
    dataset = adapter.list_datasets()[0]

    with pytest.raises(InvalidRequestError, match="'applicationNumber'"):
        _ = adapter.query_records(dataset, Query(filters={"applicationNumber": [1, 2]}))

    assert transport.calls == []


def test_kipris_treats_a_none_application_number_as_missing() -> None:
    transport = RecordingTransport()
    adapter = cast(_Adapter, _build("kipris", transport))
    dataset = adapter.list_datasets()[0]

    with pytest.raises(InvalidRequestError, match="require filter"):
        _ = adapter.query_records(dataset, Query(filters={"applicationNumber": None}))

    assert transport.calls == []


def test_kipris_sends_a_numeric_application_number_as_text() -> None:
    transport = RecordingTransport()
    adapter = cast(_Adapter, _build("kipris", transport))
    dataset = adapter.list_datasets()[0]

    with pytest.raises(_Stop):
        _ = adapter.query_records(dataset, Query(filters={"applicationNumber": 1020200012345}))

    _method, url, _params = transport.calls[0]
    assert "applicationNumber=1020200012345" in url


# --- SDK-set parameter names passed as filters ---------------------------------
#
# The same rule as spec datasets: a filter named like the credential parameter is
# dropped (the configured key is sent, the filter's value never), and one named like
# a paging or response-format parameter the adapter sets is refused before HTTP.
# Names match case-insensitively.

_CREDENTIAL = {
    "kipris": "serviceKey",
    "korean": "key",
    "kosis": "apiKey",
    "law": "OC",
    "lofin": "Key",
    "neis": "KEY",
    "sgis": "accessToken",
}
_CONFIGURED = {name: "k" for name in _CREDENTIAL} | {"sgis": "token"}
_PAGING = [
    ("kipris", "pageNo"),
    ("kipris", "numOfRows"),
    ("korean", "start"),
    ("korean", "num"),
    ("law", "page"),
    ("law", "display"),
    ("lofin", "pIndex"),
    ("lofin", "pSize"),
    ("neis", "pIndex"),
    ("neis", "PSIZE"),
]
_FORMAT = [
    ("kipris", "_type"),
    ("korean", "req_type"),
    ("kosis", "format"),
    ("kosis", "jsonVD"),
    ("law", "type"),
    ("lofin", "Type"),
    ("neis", "type"),
]


def _sdk_name_query(name: str, dataset: DatasetRef, filter_name: str) -> Query:
    query = Query(filters={**_required_filters(dataset), filter_name: "attacker-999"})
    if name == "kosis":
        query.start_date = "2024"
        query.end_date = "2024"
    return query


def _refuses(name: str, filter_name: str, hint: str) -> None:
    transport = RecordingTransport()
    adapter = cast(_Adapter, _build(name, transport))
    dataset = adapter.list_datasets()[0]

    with pytest.raises(InvalidRequestError, match=hint) as excinfo:
        _ = adapter.query_records(dataset, _sdk_name_query(name, dataset, filter_name))

    assert repr(filter_name) in str(excinfo.value)
    assert "attacker-999" not in str(excinfo.value)
    assert transport.calls == []


@pytest.mark.parametrize(("name", "filter_name"), _PAGING)
def test_list_refuses_a_paging_named_filter_before_http(name: str, filter_name: str) -> None:
    _refuses(name, filter_name, "page_size")


@pytest.mark.parametrize(("name", "filter_name"), _FORMAT)
def test_list_refuses_a_format_named_filter_before_http(name: str, filter_name: str) -> None:
    _refuses(name, filter_name, "format is fixed")


@pytest.mark.parametrize("upper", [False, True], ids=["as-named", "upper-case"])
@pytest.mark.parametrize("name", sorted(_CREDENTIAL))
def test_list_drops_a_credential_named_filter_and_sends_the_configured_key(
    name: str, upper: bool
) -> None:
    credential = _CREDENTIAL[name]
    filter_name = credential.upper() if upper else credential
    transport = RecordingTransport()
    adapter = cast(_Adapter, _build(name, transport))
    dataset = adapter.list_datasets()[0]

    with pytest.raises(_Stop):
        _ = adapter.query_records(dataset, _sdk_name_query(name, dataset, filter_name))

    assert len(transport.calls) == 1
    _method, url, params = transport.calls[0]
    sent = dict(cast(dict[str, str], params)) if params is not None else {}
    assert "attacker-999" not in url
    assert "attacker-999" not in sent.values()
    if params is not None:
        assert sent[credential] == _CONFIGURED[name]
    else:
        assert f"{credential}={_CONFIGURED[name]}" in url


class _RawAdapter:
    def list_datasets(self) -> list[DatasetRef]:
        raise NotImplementedError

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        raise NotImplementedError


@pytest.mark.parametrize("upper", [False, True], ids=["as-named", "upper-case"])
@pytest.mark.parametrize("name", ["kipris", "korean", "lofin", "neis"])
def test_call_raw_never_lets_a_credential_named_param_replace_the_configured_key(
    name: str, upper: bool
) -> None:
    """call_raw merged caller params over the key, so ``KEY=attacker`` replaced it."""
    credential = _CREDENTIAL[name]
    transport = RecordingTransport()
    adapter = cast(_RawAdapter, _build(name, transport))
    dataset = adapter.list_datasets()[0]
    param_name = credential.upper() if upper else credential

    with pytest.raises(_Stop):
        _ = adapter.call_raw(dataset, "op", {param_name: "attacker-999"})

    _method, url, _params = transport.calls[0]
    assert "attacker-999" not in url
    assert f"{credential}=k" in url
