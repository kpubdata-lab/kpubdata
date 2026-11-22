"""Filter refusals name the provider and dataset, and lofin ``call_raw`` sends no duplicates.

#1090 made ``list()`` refuse non-scalar filter values, but the refusal from the
shared value check carried ``provider=None`` and ``dataset_id=None`` on every path,
unlike the rest of the errors (#1085, #1088). lofin ``call_raw`` matched its paging
names case-sensitively and never looked at ``Type``, so ``{"type": "xml",
"PINDEX": 9}`` was sent next to the SDK's ``Type=json&pIndex=1``.
"""

from __future__ import annotations

from typing import cast
from urllib.parse import parse_qsl, urlsplit

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.executor import SpecExecutor, build_spec_dataset_ref
from kpubdata.core.models import Query
from kpubdata.core.spec import load_spec_file
from kpubdata.exceptions import InvalidRequestError
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.providers.localdata.adapter import LocaldataAdapter
from kpubdata.providers.lofin.adapter import LofinAdapter
from kpubdata.providers.semas.adapter import SemasAdapter
from kpubdata.transport.http import HttpTransport
from tests.unit.core.test_executor import SPECS_DIR, FakeTransport, _make_executor
from tests.unit.providers.test_filter_value_validation import (
    ADAPTERS,
    RecordingTransport,
    _Adapter,
    _build,
    _query,
    _Stop,
)


@pytest.mark.parametrize("name", ADAPTERS)
def test_custom_adapter_value_refusal_names_provider_and_dataset(name: str) -> None:
    transport = RecordingTransport()
    adapter = cast(_Adapter, _build(name, transport))
    dataset = adapter.list_datasets()[0]

    with pytest.raises(InvalidRequestError) as excinfo:
        _ = adapter.query_records(dataset, _query(name, [1, 2], dataset))

    assert excinfo.value.provider == name
    assert excinfo.value.dataset_id == dataset.id
    assert transport.calls == []


def _family(
    name: str, transport: RecordingTransport
) -> DataGoAdapter | SemasAdapter | LocaldataAdapter:
    config = KPubDataConfig(provider_keys={name: "k"})
    http = cast(HttpTransport, cast(object, transport))
    if name == "datago":
        return DataGoAdapter(config=config, transport=http)
    if name == "semas":
        return SemasAdapter(config=config, transport=http)
    return LocaldataAdapter(config=config, transport=http)


@pytest.mark.parametrize("name", ["datago", "semas", "localdata"])
def test_datago_family_list_refusal_names_provider_and_dataset(name: str) -> None:
    transport = RecordingTransport()
    adapter = _family(name, transport)
    dataset = adapter.get_dataset("generic") if name == "datago" else adapter.list_datasets()[0]

    with pytest.raises(InvalidRequestError) as excinfo:
        _ = adapter.query_records(dataset, Query(filters={"zzfilter": [1]}))

    assert excinfo.value.provider == name
    assert excinfo.value.dataset_id == dataset.id
    assert transport.calls == []


@pytest.mark.parametrize("name", ["datago", "semas", "localdata"])
def test_datago_family_call_raw_refusal_names_provider_and_dataset(name: str) -> None:
    transport = RecordingTransport()
    adapter = _family(name, transport)
    dataset = adapter.get_dataset("generic") if name == "datago" else adapter.list_datasets()[0]
    params: dict[str, object] = {"zzfilter": [1]}
    if name == "datago":
        params["_base_url"] = "https://apis.data.go.kr/1/svc"

    with pytest.raises(InvalidRequestError) as excinfo:
        _ = adapter.call_raw(dataset, "x", params)

    assert excinfo.value.provider == name
    assert excinfo.value.dataset_id == dataset.id
    assert transport.calls == []


def test_spec_executor_refusal_names_provider_and_dataset() -> None:
    spec = load_spec_file(SPECS_DIR / "datago" / "apt_trade.yaml")
    transport = FakeTransport([])
    executor: SpecExecutor = _make_executor(transport)

    with pytest.raises(InvalidRequestError) as excinfo:
        executor.query(
            spec,
            build_spec_dataset_ref(spec),
            Query(filters={"LAWD_CD": "11110", "DEAL_YMD": "202401", "zzfilter": [1]}),
        )

    assert excinfo.value.provider == spec.provider
    assert excinfo.value.dataset_id == spec.id
    assert transport.calls == []


def test_spec_executor_call_raw_refusal_names_provider_and_dataset() -> None:
    spec = load_spec_file(SPECS_DIR / "datago" / "apt_trade.yaml")
    transport = FakeTransport([])
    executor: SpecExecutor = _make_executor(transport)

    with pytest.raises(InvalidRequestError) as excinfo:
        executor.request_raw(spec, {"zzfilter": [1]})

    assert excinfo.value.provider == spec.provider
    assert excinfo.value.dataset_id == spec.id
    assert transport.calls == []


def _lofin_raw(params: dict[str, object]) -> list[tuple[str, str]]:
    transport = RecordingTransport()
    adapter = cast(LofinAdapter, _build("lofin", transport))
    dataset = adapter.list_datasets()[0]
    with pytest.raises(_Stop):
        _ = adapter.call_raw(dataset, "list", params)
    _method, url, _params = transport.calls[0]
    return parse_qsl(urlsplit(url).query)


@pytest.mark.parametrize(
    ("params", "page", "size"),
    [
        pytest.param({"PINDEX": 9, "PSIZE": 7}, "9", "7", id="upper"),
        pytest.param({"pindex": "3", "psize": "5"}, "3", "5", id="lower"),
        pytest.param({"pIndex": "2", "pSize": "4"}, "2", "4", id="as-named"),
        pytest.param({"PAGE": "6", "Page_Size": "8"}, "6", "8", id="sdk-aliases"),
    ],
)
def test_lofin_call_raw_reads_paging_names_in_any_case(
    params: dict[str, object], page: str, size: str
) -> None:
    pairs = _lofin_raw({**params, "fyr": "2024"})
    names = [name.lower() for name, _value in pairs]

    assert names.count("pindex") == 1
    assert names.count("psize") == 1
    assert names.count("type") == 1
    assert ("pIndex", page) in pairs
    assert ("pSize", size) in pairs
    assert ("Type", "json") in pairs
    assert ("fyr", "2024") in pairs


@pytest.mark.parametrize("name", ["Type", "type", "TYPE"])
def test_lofin_call_raw_accepts_json_type_without_a_duplicate(name: str) -> None:
    pairs = _lofin_raw({name: "JSON"})

    assert [n.lower() for n, _v in pairs].count("type") == 1
    assert ("Type", "json") in pairs


@pytest.mark.parametrize("name", ["Type", "type"])
def test_lofin_call_raw_refuses_another_format_before_http(name: str) -> None:
    transport = RecordingTransport()
    adapter = cast(LofinAdapter, _build("lofin", transport))
    dataset = adapter.list_datasets()[0]

    with pytest.raises(InvalidRequestError, match=repr(name)) as excinfo:
        _ = adapter.call_raw(dataset, "list", {name: "xml", "PINDEX": 9})

    assert "xml" not in str(excinfo.value)
    assert excinfo.value.provider == "lofin"
    assert excinfo.value.dataset_id == dataset.id
    assert transport.calls == []


def test_lofin_call_raw_refuses_one_name_given_twice_before_http() -> None:
    transport = RecordingTransport()
    adapter = cast(LofinAdapter, _build("lofin", transport))
    dataset = adapter.list_datasets()[0]

    with pytest.raises(InvalidRequestError, match="PINDEX") as excinfo:
        _ = adapter.call_raw(dataset, "list", {"pIndex": "1", "PINDEX": "9"})

    assert excinfo.value.provider == "lofin"
    assert transport.calls == []
