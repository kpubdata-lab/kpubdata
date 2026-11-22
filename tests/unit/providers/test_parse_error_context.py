"""Parse and envelope errors name the provider and the dataset on every path.

#1085 made SGIS attach ``provider`` and ``dataset_id`` to its parse errors. The
other adapters, the data.go.kr envelope mappers and the spec executor left one or
both of them ``None``, so a caller could not tell which dataset a gateway HTML page
or an envelope refusal came from.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.executor import SpecExecutor, build_spec_dataset_ref
from kpubdata.core.models import Query
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.core.spec import load_spec_file
from kpubdata.exceptions import (
    AuthError,
    InvalidRequestError,
    ParseError,
    ProviderResponseError,
    PublicDataError,
    RateLimitError,
    ServiceUnavailableError,
)
from kpubdata.providers.bok.adapter import BokAdapter
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.providers.fds.adapter import FdsAdapter
from kpubdata.providers.kipris.adapter import KiprisAdapter
from kpubdata.providers.korean.adapter import KoreanAdapter
from kpubdata.providers.kosis.adapter import KosisAdapter
from kpubdata.providers.law.adapter import LawAdapter
from kpubdata.providers.localdata.adapter import LocaldataAdapter
from kpubdata.providers.lofin.adapter import LofinAdapter
from kpubdata.providers.neis.adapter import NeisAdapter
from kpubdata.providers.semas.adapter import SemasAdapter
from kpubdata.providers.seoul.adapter import SeoulAdapter
from kpubdata.transport.http import HttpTransport
from tests.unit.core.test_executor import SPECS_DIR, FakeResponse, FakeTransport, _make_executor

#: What a gateway in front of the API returns when it fails: an HTML page that
#: still claims to be JSON.
_HTML = b"<html><body><h1>502 Bad Gateway</h1></body></html>"


class _Resp:
    def __init__(self, body: bytes, content_type: str) -> None:
        self.content = body
        self.status_code = 200
        self.headers = {"content-type": content_type}
        self.text = body.decode("utf-8", "replace")


class _Transport:
    def __init__(self, body: bytes, content_type: str = "application/json") -> None:
        self._body = body
        self._content_type = content_type

    def request(self, method: str, url: str, **kwargs: object) -> _Resp:
        return _Resp(self._body, self._content_type)


_AdapterFactory = Callable[..., ProviderAdapter]

_CASES: list[tuple[str, _AdapterFactory, str, str, dict[str, object]]] = [
    ("fds", FdsAdapter, "fds.traceability_item", "", {}),
    ("kipris", KiprisAdapter, "kipris.patent_family", "", {"applicationNumber": "1"}),
    ("korean", KoreanAdapter, "korean.dict_search", "", {"q": "a"}),
    ("neis", NeisAdapter, "neis.school_info", "schoolInfo", {}),
    ("lofin", LofinAdapter, "lofin.expenditure_budget", "", {}),
    ("bok", BokAdapter, "bok.base_rate", "", {"start_date": "202401", "end_date": "202402"}),
    ("kosis", KosisAdapter, "kosis.industrial_production", "", {}),
    ("law", LawAdapter, "law.law_search", "", {}),
    ("seoul", SeoulAdapter, "seoul.bike_realtime", "", {}),
    ("semas", SemasAdapter, "semas.zone_one", "", {}),
    ("localdata", LocaldataAdapter, "localdata.hospital", "", {}),
]


def _adapter(provider: str, factory: _AdapterFactory, body: bytes, ctype: str) -> ProviderAdapter:
    transport = cast(HttpTransport, _Transport(body, ctype))
    return factory(config=KPubDataConfig(provider_keys={provider: "K"}), transport=transport)


@pytest.mark.parametrize(("provider", "factory", "dataset_id", "operation", "params"), _CASES)
def test_a_non_json_body_names_provider_and_dataset(
    provider: str,
    factory: _AdapterFactory,
    dataset_id: str,
    operation: str,
    params: dict[str, object],
) -> None:
    adapter = _adapter(provider, factory, _HTML, "application/json")
    dataset = adapter.get_dataset(dataset_id.split(".", 1)[1])

    with pytest.raises(ParseError) as excinfo:
        adapter.call_raw(dataset, operation, dict(params))

    assert excinfo.value.provider == provider
    assert excinfo.value.dataset_id == dataset.id


@pytest.mark.parametrize(("provider", "factory", "dataset_id", "operation", "params"), _CASES)
def test_a_non_object_body_names_provider_and_dataset(
    provider: str,
    factory: _AdapterFactory,
    dataset_id: str,
    operation: str,
    params: dict[str, object],
) -> None:
    if provider == "kosis":
        pytest.skip("KOSIS answers with a top-level array, so an array is not an error")
    adapter = _adapter(provider, factory, b'"just a string"', "application/json")
    dataset = adapter.get_dataset(dataset_id.split(".", 1)[1])

    with pytest.raises((ParseError, ProviderResponseError)) as excinfo:
        adapter.call_raw(dataset, operation, dict(params))

    assert excinfo.value.provider == provider
    assert excinfo.value.dataset_id == dataset.id


def test_datago_non_json_body_names_provider_and_dataset() -> None:
    adapter = _adapter("datago", DataGoAdapter, _HTML, "application/json")
    dataset = adapter.get_dataset("generic")

    with pytest.raises(ParseError) as excinfo:
        adapter.call_raw(dataset, "x", {"_base_url": "https://apis.data.go.kr/1/svc"})

    assert excinfo.value.provider == "datago"
    assert excinfo.value.dataset_id == dataset.id


def _gateway(code: str) -> bytes:
    return (
        "<OpenAPI_ServiceResponse><cmmMsgHeader>"
        f"<errMsg>ERR</errMsg><returnReasonCode>{code}</returnReasonCode>"
        "</cmmMsgHeader></OpenAPI_ServiceResponse>"
    ).encode()


_RESULT_CODES: list[tuple[str, type[PublicDataError]]] = [
    ("30", AuthError),
    ("22", RateLimitError),
    ("10", InvalidRequestError),
    ("01", ServiceUnavailableError),
    ("99", ProviderResponseError),
]


@pytest.mark.parametrize(("code", "error"), _RESULT_CODES)
def test_datago_result_code_error_names_the_dataset(
    code: str, error: type[PublicDataError]
) -> None:
    adapter = _adapter("datago", DataGoAdapter, _gateway(code), "text/xml")
    dataset = adapter.get_dataset("generic")

    with pytest.raises(error) as excinfo:
        adapter.call_raw(dataset, "x", {"_base_url": "https://apis.data.go.kr/1/svc"})

    assert excinfo.value.provider_code == code
    assert excinfo.value.provider == "datago"
    assert excinfo.value.dataset_id == dataset.id


@pytest.mark.parametrize(("code", "error"), _RESULT_CODES)
@pytest.mark.parametrize("factory", [SemasAdapter, LocaldataAdapter])
def test_family_result_code_error_names_the_dataset(
    factory: _AdapterFactory, code: str, error: type[PublicDataError]
) -> None:
    provider = "semas" if factory is SemasAdapter else "localdata"
    adapter = _adapter(provider, factory, _gateway(code), "text/xml")
    dataset = adapter.list_datasets()[0]

    with pytest.raises(error) as excinfo:
        adapter.query_records(dataset, Query())

    assert excinfo.value.provider_code == code
    assert excinfo.value.provider == provider
    assert excinfo.value.dataset_id == dataset.id


def test_spec_executor_non_json_body_names_provider_and_dataset() -> None:
    spec = load_spec_file(SPECS_DIR / "datago" / "apt_trade.yaml")
    transport = FakeTransport([FakeResponse(_HTML)])
    executor: SpecExecutor = _make_executor(transport)

    with pytest.raises(ParseError) as excinfo:
        executor.query(
            spec,
            build_spec_dataset_ref(spec),
            Query(filters={"LAWD_CD": "11110", "DEAL_YMD": "202401"}),
        )

    assert excinfo.value.provider == spec.provider
    assert excinfo.value.dataset_id == spec.id


def test_html_body_is_not_json() -> None:
    """Guard: the body used above really fails to decode as JSON."""
    with pytest.raises(json.JSONDecodeError):
        json.loads(_HTML)
