"""Unit tests for core/executor.py — verify observable behavior of the spec executor.

FakeTransport/FakeConfig substitute the corresponding interfaces of real
HttpTransport·KPubDataConfig while maintaining standard types (reuse pattern:
tests/unit/providers/datago/conftest.py).
"""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.executor import (
    SpecDatasetAdapter,
    SpecExecutor,
    build_spec_dataset_ref,
    check_payload_error,
    extract_items,
    extract_total_count,
)
from kpubdata.core.models import DatasetRef, Query, RecordBatch
from kpubdata.core.spec import SpecDefinition, load_spec_file
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    InvalidRequestError,
    ProviderResponseError,
    RateLimitError,
    ServiceUnavailableError,
    TransportError,
)

SPECS_DIR = Path(__file__).resolve().parents[3] / "src" / "kpubdata" / "specs"
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


class FakeResponse:
    """Mimics the minimal interface (content·headers) of httpx.Response."""

    def __init__(self, content: bytes, content_type: str = "application/json") -> None:
        self.content = content
        self.headers = {"content-type": content_type}


class FakeTransport:
    """Records requests and returns pre-prepared responses (or exceptions)."""

    def __init__(
        self,
        responses: list[FakeResponse] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self._responses = list(responses or [])
        self._error = error

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        json_body: object = None,
        dataset_id: str | None = None,
        provider: str | None = None,
        secret_values: tuple[str, ...] = (),
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "dataset_id": dataset_id,
                "provider": provider,
            }
        )
        if self._error is not None:
            raise self._error
        if not self._responses:
            raise AssertionError("FakeTransport에 준비된 응답이 없습니다.")
        return self._responses.pop(0)


class FakeConfig(KPubDataConfig):
    """Config with key lookup replaced by fixed values."""

    def get_provider_key(self, provider: str) -> str | None:
        return f"test-key-{provider}"

    def require_provider_key(self, provider: str) -> str:
        return f"test-key-{provider}"


def _golden_spec(dataset_key: str) -> SpecDefinition:
    """Load bundled golden spec."""
    return load_spec_file(SPECS_DIR / "datago" / f"{dataset_key}.yaml")


def _standard_envelope(
    items: list[dict[str, object]] | dict[str, object] | None,
    total_count: int | None = 30,
    result_code: str = "00",
) -> FakeResponse:
    """Create a data.go.kr standard envelope response."""
    body: dict[str, object] = {}
    if items is None:
        body["items"] = None
    else:
        body["items"] = {"item": items}
    if total_count is not None:
        body["totalCount"] = str(total_count)
    payload = {"response": {"header": {"resultCode": result_code, "resultMsg": "OK"}, "body": body}}
    return FakeResponse(json.dumps(payload).encode("utf-8"))


def _make_executor(transport: FakeTransport) -> SpecExecutor:
    return SpecExecutor(transport, FakeConfig())


def _ref(spec: SpecDefinition) -> DatasetRef:
    return build_spec_dataset_ref(spec)


@pytest.fixture()
def apt_spec() -> SpecDefinition:
    return _golden_spec("apt_trade")


@pytest.fixture()
def village_spec() -> SpecDefinition:
    return _golden_spec("village_fcst")


# ----------------------------------------------------------------------
# Parameter assembly
# ----------------------------------------------------------------------


def test_build_params_assembles_auth_format_pagination_filters(apt_spec: SpecDefinition) -> None:
    """Auth·format·pagination·filters are all assembled."""
    executor = _make_executor(FakeTransport())
    query = Query(filters={"LAWD_CD": "11110", "DEAL_YMD": "202401"}, page=2, page_size=50)
    params = executor.build_params(apt_spec, query)

    assert params["serviceKey"] == "test-key-datago"
    assert params["resultType"] == "json"
    assert params["pageNo"] == "2"
    assert params["numOfRows"] == "50"
    assert params["LAWD_CD"] == "11110"
    assert params["DEAL_YMD"] == "202401"


def test_build_params_reserved_keys_not_overwritten(apt_spec: SpecDefinition) -> None:
    """User filters do not overwrite auth/format/pagination parameters."""
    executor = _make_executor(FakeTransport())
    query = Query(filters={"serviceKey": "hijack", "pageNo": "999"})
    params = executor.build_params(apt_spec, query)
    assert params["serviceKey"] == "test-key-datago"
    assert params["pageNo"] == "1"


def test_build_params_max_size_clamp(apt_spec: SpecDefinition) -> None:
    """page_size is clamped if it exceeds max_size."""
    executor = _make_executor(FakeTransport())
    params = executor.build_params(apt_spec, Query(page=1, page_size=99999))
    assert int(params["numOfRows"]) == 1000


def test_build_params_unsupported_pagination_raises(apt_spec: SpecDefinition) -> None:
    """Unsupported pagination style raises NotImplementedError."""
    executor = _make_executor(FakeTransport())
    spec = replace(apt_spec, pagination=replace(apt_spec.pagination, type="date_window"))
    with pytest.raises(NotImplementedError, match="date_window"):
        executor.build_params(spec, Query(page=1))


# ----------------------------------------------------------------------
# query: envelope·pagination
# ----------------------------------------------------------------------


def test_query_multi_items_with_total_count(apt_spec: SpecDefinition) -> None:
    """next_page calculation based on total_count matches adapter semantics."""
    items = [{"아파트": "래미안", "거래금액": "120,000"} for _ in range(10)]
    transport = FakeTransport([_standard_envelope(items, total_count=30)])
    executor = _make_executor(transport)
    batch = executor.query(apt_spec, _ref(apt_spec), Query(page=1, page_size=10))
    assert len(batch.items) == 10
    assert batch.total_count == 30
    assert batch.next_page == 2
    call = transport.calls[0]
    assert (
        call["url"]
        == "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
    )
    assert call["provider"] == "datago"
    assert call["dataset_id"] == "datago.apt_trade"


def test_query_single_item_dict_wrapped(apt_spec: SpecDefinition) -> None:
    """Single item dict is normalized into a 1-item list."""
    transport = FakeTransport([_standard_envelope({"아파트": "단일"}, total_count=1)])
    executor = _make_executor(transport)
    batch = executor.query(apt_spec, _ref(apt_spec), Query(page=1, page_size=10))
    assert batch.items == [{"아파트": "단일"}]
    assert batch.next_page is None


def test_query_empty_items(apt_spec: SpecDefinition) -> None:
    """Empty page returns empty batch and next_page=None."""
    transport = FakeTransport([_standard_envelope(None, total_count=None)])
    executor = _make_executor(transport)
    batch = executor.query(apt_spec, _ref(apt_spec), Query(page=1, page_size=10))
    assert batch.items == []
    assert batch.total_count is None
    assert batch.next_page is None


def test_query_full_page_without_total_suggests_next(apt_spec: SpecDefinition) -> None:
    """Full page without total_count is treated as a signal for next page."""
    items = [{"no": i} for i in range(10)]
    transport = FakeTransport([_standard_envelope(items, total_count=None)])
    executor = _make_executor(transport)
    batch = executor.query(apt_spec, _ref(apt_spec), Query(page=1, page_size=10))
    assert batch.next_page == 2


def test_query_default_page_size_is_100(apt_spec: SpecDefinition) -> None:
    """Default page=1·page_size=100 is used when page is not specified."""
    transport = FakeTransport([_standard_envelope([{"x": 1}], total_count=1)])
    executor = _make_executor(transport)
    executor.query(apt_spec, _ref(apt_spec), Query())
    params = transport.calls[0]["params"]
    assert isinstance(params, dict)
    assert params["pageNo"] == "1"
    assert params["numOfRows"] == "100"


# ----------------------------------------------------------------------
# query: Error mapping
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected_exc"),
    [
        ("30", AuthError),
        ("31", AuthError),
        ("20", AuthError),
        ("32", AuthError),
        ("22", RateLimitError),
        ("10", InvalidRequestError),
        ("12", DatasetNotFoundError),
        ("01", ServiceUnavailableError),
        ("02", ServiceUnavailableError),
        ("99", ProviderResponseError),
    ],
)
def test_query_error_code_table(
    apt_spec: SpecDefinition, code: str, expected_exc: type[Exception]
) -> None:
    """resultCode→standard exception mapping table matches adapter."""
    payload = {
        "response": {
            "header": {"resultCode": code, "resultMsg": f"에러 {code}"},
            "body": {"items": None},
        }
    }
    transport = FakeTransport([FakeResponse(json.dumps(payload).encode())])
    executor = _make_executor(transport)
    with pytest.raises(expected_exc) as exc_info:
        executor.query(apt_spec, _ref(apt_spec), Query())
    assert getattr(exc_info.value, "provider_code", None) == code


@pytest.mark.parametrize("ok_code", ["000", "0"])
def test_query_ok_values_numeric_zero(apt_spec: SpecDefinition, ok_code: str) -> None:
    """ "000"/"0" success codes also pass through int normalization."""
    payload = {
        "response": {
            "header": {"resultCode": ok_code, "resultMsg": "OK"},
            "body": {"items": {"item": {"a": 1}}, "totalCount": "1"},
        }
    }
    transport = FakeTransport([FakeResponse(json.dumps(payload).encode())])
    executor = _make_executor(transport)
    batch = executor.query(apt_spec, _ref(apt_spec), Query())
    assert len(batch.items) == 1


def test_query_missing_result_code_raises(apt_spec: SpecDefinition) -> None:
    """Envelope without resultCode becomes ProviderResponseError."""
    transport = FakeTransport([FakeResponse(b'{"response": {"header": {}, "body": {}}}')])
    executor = _make_executor(transport)
    with pytest.raises(ProviderResponseError, match="에러 코드"):
        executor.query(apt_spec, _ref(apt_spec), Query())


def test_query_http_403_maps_to_auth_error(apt_spec: SpecDefinition) -> None:
    """Transport layer 403 becomes AuthError with usage application hint.

    Real transport does so by carrying ``status_code`` in the exception.
    Previously, fake only filled ``__cause__``, but transport breaks the
    exception chain when the request carries credentials — spec executor
    sends keys as params, so the chain is always broken. Fake's assumption
    of a chain did not match the real path.
    """
    transport_error = TransportError("forbidden", provider="datago", status_code=403)
    executor = _make_executor(FakeTransport(error=transport_error))
    with pytest.raises(AuthError, match="활용"):
        executor.query(apt_spec, _ref(apt_spec), Query())


def test_query_http_403_maps_to_auth_error_even_without_an_exception_chain(
    apt_spec: SpecDefinition,
) -> None:
    """Broken chain is the actual path — 403 hint must still appear."""
    transport_error = TransportError("forbidden", provider="datago", status_code=403)
    assert transport_error.__cause__ is None

    executor = _make_executor(FakeTransport(error=transport_error))

    with pytest.raises(AuthError, match="활용"):
        executor.query(apt_spec, _ref(apt_spec), Query())


def test_a_non_403_transport_error_is_not_turned_into_an_auth_error(
    apt_spec: SpecDefinition,
) -> None:
    executor = _make_executor(
        FakeTransport(error=TransportError("boom", provider="datago", status_code=503))
    )

    with pytest.raises(TransportError):
        executor.query(apt_spec, _ref(apt_spec), Query())


# ----------------------------------------------------------------------
# query: XML·fields normalization
# ----------------------------------------------------------------------


def test_query_xml_format_hint(village_spec: SpecDefinition) -> None:
    """format_hint=xml changes format parameter and parses XML response."""
    xml_payload = (
        "<response><header><resultCode>00</resultCode></header>"
        "<body><items><item><category>T1H</category><fcstValue>12.3</fcstValue></item></items>"
        "<totalCount>1</totalCount></body></response>"
    )
    transport = FakeTransport([FakeResponse(xml_payload.encode(), content_type="text/xml")])
    executor = _make_executor(transport)
    batch = executor.query(
        village_spec,
        _ref(village_spec),
        Query(filters={"base_date": "20250401", "base_time": "0500", "nx": 55, "ny": 127}),
        format_hint="xml",
    )
    params = transport.calls[0]["params"]
    assert isinstance(params, dict)
    assert params["dataType"] == "XML"
    assert params["base_date"] == "20250401"
    assert batch.items == [{"category": "T1H", "fcstValue": "12.3"}]
    assert batch.total_count == 1


def test_query_fields_normalization() -> None:
    """With fields declaration, rename·transform·casting is applied."""
    spec = load_spec_file(FIXTURES_DIR / "specs" / "valid_full.yaml")
    record = {"거래금액": "120,000", "년": "2024"}
    payload = {
        "response": {
            "header": {"resultCode": "00"},
            "body": {"items": {"item": record}, "totalCount": "1"},
        }
    }
    transport = FakeTransport([FakeResponse(json.dumps(payload).encode())])
    executor = _make_executor(transport)
    batch = executor.query(spec, _ref(spec), Query())
    item = batch.items[0]
    assert item["deal_amount"] == 120000
    assert "거래금액" not in item
    assert item["년"] == "2024"


def _valid_full_result(
    records: list[dict[str, object]], field_type: str = "integer"
) -> RecordBatch:
    """Normalize given records using valid_full spec and return the whole batch.

    Tests that look at ``validation`` need the batch, not only its items.
    """
    spec = load_spec_file(FIXTURES_DIR / "specs" / "valid_full.yaml")
    spec = replace(spec, fields=(replace(spec.fields[0], type=field_type),))
    payload = {
        "response": {
            "header": {"resultCode": "00"},
            "body": {"items": {"item": records}, "totalCount": str(len(records))},
        }
    }
    transport = FakeTransport([FakeResponse(json.dumps(payload).encode())])
    executor = _make_executor(transport)
    return executor.query(spec, _ref(spec), Query())


def _valid_full_batch(
    records: list[dict[str, object]], field_type: str = "integer"
) -> list[dict[str, object]]:
    """Normalize given records using valid_full spec and return result."""
    spec = load_spec_file(FIXTURES_DIR / "specs" / "valid_full.yaml")
    spec = replace(spec, fields=(replace(spec.fields[0], type=field_type),))
    payload = {
        "response": {
            "header": {"resultCode": "00"},
            "body": {"items": {"item": records}, "totalCount": str(len(records))},
        }
    }
    transport = FakeTransport([FakeResponse(json.dumps(payload).encode())])
    executor = _make_executor(transport)
    return list(executor.query(spec, _ref(spec), Query()).items)


class TestColumnConsistentCasting:
    """Casting succeeds column-wise, not row-wise (#452).

    Row-by-row casting allows same column to have both int and str,
    which table consumers (kpubdata-builder Silver etc) reject.
    """

    def test_all_castable_column_is_cast(self) -> None:
        items = _valid_full_batch([{"거래금액": "120,000"}, {"거래금액": "98,000"}])
        assert [item["deal_amount"] for item in items] == [120000, 98000]

    def test_one_uncastable_value_leaves_the_whole_column_alone(self) -> None:
        # Real case like apt_trade: most rows are numbers but some have names.
        items = _valid_full_batch(
            [{"거래금액": "120,000"}, {"거래금액": "협의"}, {"거래금액": "98,000"}]
        )
        values = [item["deal_amount"] for item in items]
        assert values == ["120000", "협의", "98000"]
        assert {type(value) for value in values} == {str}

    def test_nulls_do_not_block_casting(self) -> None:
        items = _valid_full_batch([{"거래금액": "120,000"}, {"거래금액": None}])
        assert [item["deal_amount"] for item in items] == [120000, None]

    def test_missing_field_does_not_block_casting(self) -> None:
        items = _valid_full_batch([{"거래금액": "120,000"}, {"년": "2024"}])
        assert items[0]["deal_amount"] == 120000
        assert "deal_amount" not in items[1]

    def test_rename_and_transform_still_apply_when_casting_is_skipped(self) -> None:
        # Even when casting is skipped, rename and transform still apply.
        items = _valid_full_batch([{"거래금액": "120,000"}, {"거래금액": "협의"}])
        assert all("거래금액" not in item for item in items)
        assert items[0]["deal_amount"] == "120000"

    def test_number_column_is_cast_when_all_values_are_numeric(self) -> None:
        items = _valid_full_batch([{"거래금액": "12.5"}, {"거래금액": "98"}], field_type="number")
        assert [item["deal_amount"] for item in items] == [12.5, 98.0]

    def test_number_column_is_left_raw_when_one_value_is_not_numeric(self) -> None:
        items = _valid_full_batch([{"거래금액": "12.5"}, {"거래금액": "N/A"}], field_type="number")
        assert [item["deal_amount"] for item in items] == ["12.5", "N/A"]

    def test_boolean_does_not_count_as_a_number_cast(self) -> None:
        items = _valid_full_batch([{"거래금액": True}, {"거래금액": "2"}], field_type="number")
        assert [item["deal_amount"] for item in items] == [True, "2"]


# ----------------------------------------------------------------------
# Unsupported envelope / SpecDatasetAdapter
# ----------------------------------------------------------------------


def test_query_unsupported_envelope_raises(apt_spec: SpecDefinition) -> None:
    """Envelope other than datago_standard raises NotImplementedError."""
    spec = replace(apt_spec, response=replace(apt_spec.response, envelope="seoul_service_row"))
    executor = _make_executor(FakeTransport())
    with pytest.raises(NotImplementedError, match="seoul_service_row"):
        executor.query(spec, _ref(spec), Query())


def test_spec_dataset_adapter_surface(
    apt_spec: SpecDefinition, village_spec: SpecDefinition
) -> None:
    """Adapter protocol surface (list/search/get/query/raw) works."""
    raw_payload = {"response": {"header": {"resultCode": "00"}, "body": {"items": None}}}
    transport = FakeTransport(
        [
            _standard_envelope([{"a": 1}], total_count=1),
            FakeResponse(json.dumps(raw_payload).encode()),
        ]
    )
    executor = _make_executor(transport)
    adapter = SpecDatasetAdapter("datago", [apt_spec, village_spec], executor)

    assert adapter.name == "datago"
    assert adapter.requires_api_key is True

    keys = {ref.dataset_key for ref in adapter.list_datasets()}
    assert keys == {"apt_trade", "village_fcst"}

    hits = adapter.search_datasets("예보")
    assert {ref.dataset_key for ref in hits} == {"village_fcst"}

    ref = adapter.get_dataset("apt_trade")
    assert ref.id == "datago.apt_trade"

    with pytest.raises(DatasetNotFoundError):
        adapter.get_dataset("nope")

    batch = adapter.query_records(ref, Query(page=1, page_size=10))
    assert len(batch.items) == 1

    raw = adapter.call_raw(ref, "raw", {"LAWD_CD": "11110"})
    assert isinstance(raw, dict) and "response" in raw


def test_spec_dataset_adapter_get_schema_is_none(apt_spec: SpecDefinition) -> None:
    """get_schema honestly returns None."""
    executor = _make_executor(FakeTransport())
    adapter = SpecDatasetAdapter("datago", [apt_spec], executor)
    assert adapter.get_schema(adapter.get_dataset("apt_trade")) is None


# ----------------------------------------------------------------------
# Executor scope extension: path_segment·index_range·pindex_psize·$root·
# array index·neis
# ----------------------------------------------------------------------


def _spec_from(data: dict[str, object]) -> SpecDefinition:
    from kpubdata.core.spec import from_mapping

    return from_mapping(data)


def test_build_url_path_template_bok_style() -> None:
    """path_template {key}/{start}/{end} substitution creates BOK-style URL."""
    spec = _spec_from(
        {
            "id": "bok.test_stat",
            "provider": "bok",
            "title": "테스트",
            "endpoint": {
                "base_url": "https://api.bok.go.kr/eco",
                "operation": "StatisticSearch",
                "path_template": "{base_url}/{key}/json/{operation}/{start}/{end}/AAA/110",
            },
            "auth": {
                "type": "path_segment",
                "param_name": "__path_key__",
                "provider_key": "datago",
            },
            "response": {
                "format": "json",
                "envelope": "bok_statistic_row",
                "items_path": "StatisticSearch.row",
                "error": {
                    "style": "result_code",
                    "code_path": "StatisticSearch.RESULT.CODE",
                    "ok_values": ["000"],
                },
            },
            "pagination": {"type": "index_range", "start_index_base": 1},
        }
    )
    executor = _make_executor(FakeTransport())
    url = executor.build_url(spec, page=2, page_size=10, api_key="KEY123")
    assert url == "https://api.bok.go.kr/eco/KEY123/json/StatisticSearch/11/20/AAA/110"

    # Parameter assembly: index_range does not put page in query
    # (reflected in path) and auth is pulled from path.
    params = executor.build_params(spec, Query(page=2, page_size=10))
    assert params["__path_key__"] == "test-key-datago"
    assert "pageNo" not in params


def test_pindex_psize_and_page_display_params() -> None:
    """lofin (pIndex/pSize) and law (page/display) query pagination is assembled."""
    base = {
        "id": "test.lofin_like",
        "provider": "test",
        "title": "t",
        "endpoint": {"base_url": "https://x.test/api", "operation": "AJGCF"},
        "auth": {"type": "none"},
        "response": {
            "format": "json",
            "envelope": "lofin_head_row",
            "items_path": "{operation}.1.row",
            "error": {"style": "result_code"},
        },
        "pagination": {"type": "pindex_psize"},
    }
    executor = _make_executor(FakeTransport())
    params = executor.build_params(_spec_from(base), Query(page=3, page_size=50))
    assert params["pIndex"] == "3"
    assert params["pSize"] == "50"

    law = dict(base, id="test.law_like", pagination={"type": "page_display"})
    params2 = executor.build_params(_spec_from(law), Query(page=2, page_size=30))
    assert params2["page"] == "2"
    assert params2["display"] == "30"


def test_extract_items_root_array_and_operation_template() -> None:
    """$ root array (kosis) and {operation} substitution (lofin) extraction works."""
    # kosis root array contract: _request returns ProviderResponseError, not dict.
    # (Executor contract expansion needed for kosis transition — keep
    # envelope state as-is).
    from kpubdata.core.executor import _dot_get

    assert _dot_get({"a": {"b": 1}}, "a.b") == 1  # Normal path returns recursively

    lofin_spec = _spec_from(
        {
            "id": "test.lofin_extract",
            "provider": "test",
            "title": "t",
            "endpoint": {"base_url": "https://x.test", "operation": "AJGCF"},
            "auth": {"type": "none"},
            "response": {
                "format": "json",
                "envelope": "lofin_head_row",
                "items_path": "{operation}.1.row",
                "total_count_path": "{operation}.0.head.0.list_total_count",
                "error": {
                    "style": "result_code",
                    "code_path": "RESULT.0.CODE",
                    "ok_values": ["000"],
                },
            },
            "pagination": {"type": "none"},
        }
    )
    lofin_payload = {
        "RESULT": [{"CODE": "000", "MESSAGE": "OK"}],
        "AJGCF": [
            {"head": [{"list_total_count": 2}]},
            {"row": [{"fyr": "2023"}, {"fyr": "2022"}]},
        ],
    }
    assert extract_items(lofin_spec, lofin_payload) == [{"fyr": "2023"}, {"fyr": "2022"}]
    assert extract_total_count(lofin_spec, lofin_payload) == 2
    check_payload_error(lofin_spec, lofin_payload)  # Success passes

    lofin_payload["RESULT"] = [{"CODE": "ERROR-300", "MESSAGE": "필수 누락"}]
    from kpubdata.exceptions import ProviderResponseError as PRE

    with pytest.raises(PRE):
        check_payload_error(lofin_spec, lofin_payload)


def test_extract_neis_double_list_merges_blocks() -> None:
    """NEIS double-list envelope merges rows per block."""
    spec = _spec_from(
        {
            "id": "test.neis_like",
            "provider": "test",
            "title": "t",
            "endpoint": {"base_url": "https://x.test", "operation": "schoolInfo"},
            "auth": {"type": "none"},
            "response": {
                "format": "json",
                "envelope": "neis_double_list",
                "items_path": "ignored",
                "error": {"style": "result_code"},
            },
            "pagination": {"type": "none"},
        }
    )
    payload = {
        "schoolInfo": [
            {"head": [{"list_total_count": 3}]},
            {"row": [{"name": "A"}, {"name": "B"}]},
            {"row": [{"name": "C"}]},
        ]
    }
    assert extract_items(spec, payload) == [{"name": "A"}, {"name": "B"}, {"name": "C"}]


def test_kosis_err_field_raises_on_error_payload() -> None:
    """kosis err_field style: err key presence raises ProviderResponseError."""
    spec = _spec_from(
        {
            "id": "test.kosis_err",
            "provider": "test",
            "title": "t",
            "endpoint": {"base_url": "https://x.test", "operation": "data"},
            "auth": {"type": "none"},
            "response": {
                "format": "json",
                "envelope": "kosis_top_array",
                "items_path": "$",
                "error": {"style": "err_field", "ok_values": []},
            },
            "pagination": {"type": "none"},
        }
    )
    with pytest.raises(ProviderResponseError, match="Provider 오류"):
        check_payload_error(spec, {"err": "LIST_OF_ORGANIZATION invalid"})


def test_seoul_info_codes_pass_error_check() -> None:
    """Seoul-series INFO-000/INFO-200 pass error check via ok_values."""
    spec = _spec_from(
        {
            "id": "test.seoul_like",
            "provider": "test",
            "title": "t",
            "endpoint": {"base_url": "https://x.test", "operation": "svc"},
            "auth": {"type": "none"},
            "response": {
                "format": "json",
                "envelope": "seoul_service_row",
                "items_path": "CycleStationParking.row",
                "error": {
                    "style": "result_code",
                    "code_path": "CycleStationParking.RESULT.CODE",
                    "ok_values": ["INFO-000", "INFO-200"],
                },
            },
            "pagination": {"type": "none"},
        }
    )
    check_payload_error(
        spec, {"CycleStationParking": {"RESULT": {"CODE": "INFO-000", "MESSAGE": "OK"}, "row": []}}
    )
    check_payload_error(
        spec, {"CycleStationParking": {"RESULT": {"CODE": "INFO-200", "MESSAGE": "no data"}}}
    )
    with pytest.raises(ProviderResponseError):
        check_payload_error(
            spec, {"CycleStationParking": {"RESULT": {"CODE": "ERROR-500", "MESSAGE": "boom"}}}
        )


class TestSpecRequestParameterMetadata:
    """Spec params exposed via DatasetRef.raw_metadata (#375).

    Consumers (Builder/Studio) could only learn filterable_fields via
    query_support.filterable_fields, but not which are required or what
    values to use. Expose spec info already present in request_parameters
    form (#374).
    """

    def test_required_parameter_is_exposed_with_example(self) -> None:
        ref = _ref(_golden_spec("apt_trade"))
        parameters = ref.raw_metadata["request_parameters"]
        assert isinstance(parameters, tuple)
        by_name = {str(entry["name"]): entry for entry in parameters}

        assert set(by_name) == {"LAWD_CD", "DEAL_YMD"}
        lawd = by_name["LAWD_CD"]
        assert lawd["required"] is True
        assert lawd["example"] == "11110"
        assert "지역코드" in str(lawd["description"])

    def test_alias_is_reported_as_the_name_callers_pass(self) -> None:
        # air_station's sidoName has an alias like station/term —
        # the name users must pass is 'alias'; the original API name is api_name.
        ref = _ref(_golden_spec("air_station"))
        parameters = ref.raw_metadata["request_parameters"]
        assert isinstance(parameters, tuple)
        by_name = {str(entry["name"]): entry for entry in parameters}

        assert "station" in by_name, sorted(by_name)
        assert by_name["station"]["api_name"] == "stationName"
        # Parameters without alias do not carry api_name (eliminate redundant info).
        assert "api_name" not in by_name["ver"]

    def test_enum_values_are_exposed(self) -> None:
        ref = _ref(_golden_spec("air_station"))
        parameters = ref.raw_metadata["request_parameters"]
        assert isinstance(parameters, tuple)
        term = next(entry for entry in parameters if entry["name"] == "term")
        assert term["enum"] == ["daily", "month", "3month"]

    def test_metadata_is_immutable(self) -> None:
        # raw_metadata is a shared reference — changes by consumers must not
        # leak to other consumers.
        ref = _ref(_golden_spec("apt_trade"))
        parameters = ref.raw_metadata["request_parameters"]
        assert isinstance(parameters, tuple)
        with pytest.raises(TypeError):
            cast(MutableMapping[str, object], parameters[0])["required"] = False

    def test_verified_at_is_exposed_for_freshness(self) -> None:
        spec = _golden_spec("apt_trade")
        ref = _ref(spec)
        assert spec.source is not None
        assert ref.raw_metadata["verified_at"] == spec.source.verified_at

    def test_filterable_fields_still_match_the_exposed_names(self) -> None:
        # Existing contract (query_support) and new metadata must not
        # diverge from each other.
        ref = _ref(_golden_spec("air_station"))
        parameters = ref.raw_metadata["request_parameters"]
        assert isinstance(parameters, tuple)
        assert ref.query_support is not None
        assert {str(entry["name"]) for entry in parameters} == set(
            ref.query_support.filterable_fields
        )


class TestSpecExecutorRecognisesGatewayRejections:
    """Spec-first path also reports gateway rejections per cause.

    #478 added this branch only to the datago **adapter**. ~20 other
    specs still failed with "error code not found in response envelope" —
    user-fixable issues (key unregistered, quota exceeded) appeared as
    parse errors.
    """

    @staticmethod
    def _spec() -> SpecDefinition:
        return _spec_from(
            {
                "id": "datago.gateway_probe",
                "provider": "datago",
                "title": "게이트웨이 거부 확인",
                "endpoint": {"base_url": "https://apis.data.go.kr/svc", "operation": "getList"},
                "auth": {"type": "query_param", "param_name": "serviceKey"},
                "response": {
                    "format": "json",
                    "envelope": "datago_standard",
                    "items_path": "response.body.items.item",
                    "error": {"style": "result_code", "code_path": "response.header.resultCode"},
                },
                "pagination": {
                    "type": "page_no_rows",
                    "page_param": "pageNo",
                    "size_param": "numOfRows",
                },
            }
        )

    @staticmethod
    def _gateway(code: str, *, auth_msg: str | None = None) -> dict[str, object]:
        header: dict[str, object] = {"errMsg": "SERVICE ERROR", "returnReasonCode": code}
        if auth_msg is not None:
            header["returnAuthMsg"] = auth_msg
        return {"OpenAPI_ServiceResponse": {"cmmMsgHeader": header}}

    def test_an_unregistered_key_is_an_auth_error(self) -> None:
        from kpubdata.core.executor import check_payload_error
        from kpubdata.exceptions import AuthError

        with pytest.raises(AuthError) as exc:
            check_payload_error(
                self._spec(), self._gateway("30", auth_msg="SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
            )

        assert exc.value.provider_code == "30"
        assert "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in str(exc.value)

    def test_an_exhausted_quota_is_a_rate_limit_error(self) -> None:
        from kpubdata.core.executor import check_payload_error
        from kpubdata.exceptions import RateLimitError

        with pytest.raises(RateLimitError) as exc:
            check_payload_error(self._spec(), self._gateway("22"))

        assert exc.value.provider_code == "22"

    def test_it_is_not_reported_as_a_missing_error_code(self) -> None:
        # Regression check: old message was "could not find error code".
        from kpubdata.core.executor import check_payload_error
        from kpubdata.exceptions import AuthError

        with pytest.raises(AuthError) as exc:
            check_payload_error(self._spec(), self._gateway("30"))

        assert "찾을 수 없습니다" not in str(exc.value)

    def test_a_normal_envelope_is_untouched(self) -> None:
        from kpubdata.core.executor import check_payload_error

        check_payload_error(self._spec(), {"response": {"header": {"resultCode": "00"}}})


class TestTheReportShowsTheRatioNotJustTheCount:
    """The failure count alone cannot say what is wrong (#572 follow-up).

    ``#574`` was already counting these when it wrote diagnostics into ``meta``; the
    typed report replaced that and dropped them.
    """

    def test_a_mostly_bad_column_reads_as_a_wrong_declaration(self) -> None:
        """10 of 12 non-null failing means the spec is wrong, not the data."""
        records = [{"거래금액": "협의"}] * 10 + [{"거래금액": "120,000"}] * 2
        batch = _valid_full_result(records)

        issue = batch.validation.issues_of("uncastable")[0]
        assert issue.failed_count == 10
        assert issue.non_null_count == 12
        assert issue.null_count == 0

    def test_nulls_are_counted_separately_from_failures(self) -> None:
        """A column that is mostly null and fails on the rest is its own problem.

        Nulls do not block casting, so they are not failures — but a report that folds
        them into the total hides how little data there was to judge.
        """
        records = [{"거래금액": None}] * 8 + [{"거래금액": "협의"}, {"거래금액": "120,000"}]
        batch = _valid_full_result(records)

        issue = batch.validation.issues_of("uncastable")[0]
        assert issue.failed_count == 1
        assert issue.null_count == 8
        assert issue.non_null_count == 2

    def test_issues_of_returns_only_that_kind(self) -> None:
        """The helper exists so the kind strings are not spelled out at each call site.

        A typo in an inline filter reads as "no issues of that kind", which is the same
        as clean.
        """
        batch = _valid_full_result(
            [{"거래금액": "협의", "신규필드": "값"}, {"거래금액": "98,000", "신규필드": "값2"}]
        )

        assert [i.kind for i in batch.validation.issues_of("uncastable")] == ["uncastable"]
        assert [i.field for i in batch.validation.issues_of("undeclared")] == ["신규필드"]
        assert batch.validation.issues_of("missing") == ()

    def test_counts_are_absent_rather_than_zero_when_not_applicable(self) -> None:
        """A missing or undeclared field has no column to count, and says so.

        Zero would claim the column was examined and found empty.
        """
        batch = _valid_full_result([{"거래금액": "120,000"}, {"년": "2024"}])

        missing = batch.validation.issues_of("missing")
        if missing:
            assert missing[0].non_null_count is None
            assert missing[0].null_count is None
