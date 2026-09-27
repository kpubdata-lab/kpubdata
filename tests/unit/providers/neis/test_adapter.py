"""NEIS adapter unit tests (#164)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import Query
from kpubdata.exceptions import AuthError, InvalidRequestError
from kpubdata.providers.neis.adapter import NeisAdapter
from kpubdata.transport.http import HttpTransport
from tests.unit.providers.datago.conftest import FakeResponse

_NEIS_FIXTURE_DIR = Path(__file__).parents[3] / "fixtures" / "neis"


def _load_neis_fixture(name: str) -> bytes:
    return (_NEIS_FIXTURE_DIR / name).read_bytes()


def _build_adapter(fixture_names: list[str]) -> tuple[NeisAdapter, object]:
    class _Transport:
        def __init__(self, names: list[str]) -> None:
            self._responses = [FakeResponse(_load_neis_fixture(n)) for n in names]
            self.calls: list[dict[str, object]] = []

        def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
            self.calls.append({"method": method, "url": url, **kwargs})
            return self._responses.pop(0)

    transport = _Transport(fixture_names)
    adapter = NeisAdapter(
        config=KPubDataConfig(provider_keys={"neis": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter, transport


def test_query_records_builds_neis_url() -> None:
    adapter, transport = _build_adapter(["meal_diet.json"])
    dataset = adapter.get_dataset("meal_diet")

    batch = adapter.query_records(
        dataset,
        Query(
            filters={"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7021108"},
            page_size=10,
        ),
    )

    call = transport.calls[0]
    url = str(call["url"])
    assert url.startswith("https://open.neis.go.kr/hub/mealServiceDietInfo?")
    assert "KEY=test-key" in url
    assert "Type=json" in url
    assert "pIndex=1" in url
    assert "pSize=10" in url
    assert "ATPT_OFCDC_SC_CODE=B10" in url
    assert "SD_SCHUL_CODE=7021108" in url

    assert len(batch.items) == 2
    assert batch.items[0]["SD_SCHUL_NM"] == "서울고등학교"
    assert "DDISH_NM" in batch.items[0]
    assert batch.total_count == 2
    assert batch.next_page is None


def test_query_records_missing_required_filter_raises() -> None:
    adapter, _ = _build_adapter(["meal_diet.json"])
    dataset = adapter.get_dataset("meal_diet")

    try:
        adapter.query_records(dataset, Query(filters={"SD_SCHUL_CODE": "7021108"}))
    except InvalidRequestError as exc:
        assert "ATPT_OFCDC_SC_CODE" in str(exc)
    else:
        raise AssertionError("필수 filter 누락이 예외로 나야 한다")


def test_query_records_empty_result_returns_empty_batch() -> None:
    adapter, _ = _build_adapter(["empty_result.json"])
    dataset = adapter.get_dataset("meal_diet")

    batch = adapter.query_records(
        dataset,
        Query(filters={"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7021108"}),
    )

    assert batch.items == []
    assert batch.total_count is None


def test_query_records_auth_error_raises_auth_error() -> None:
    adapter, _ = _build_adapter(["auth_error.json"])
    dataset = adapter.get_dataset("meal_diet")

    try:
        adapter.query_records(
            dataset,
            Query(filters={"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7021108"}),
        )
    except AuthError:
        pass
    else:
        raise AssertionError("ERROR-290은 AuthError로 매핑되어야 한다")


def test_call_raw_returns_full_envelope() -> None:
    adapter, _ = _build_adapter(["meal_diet.json"])
    dataset = adapter.get_dataset("meal_diet")

    payload = adapter.call_raw(
        dataset,
        "mealServiceDietInfo",
        {"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7021108"},
    )

    assert "mealServiceDietInfo" in cast(dict, payload)


def test_pagination_next_page_computed_from_total() -> None:
    adapter, _ = _build_adapter(["meal_diet.json"])
    dataset = adapter.get_dataset("meal_diet")

    batch = adapter.query_records(
        dataset,
        Query(
            filters={"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7021108"},
            page=1,
            page_size=1,
        ),
    )

    assert batch.next_page == 2


def test_school_info_parses_without_required_filters() -> None:
    """School basic info is queried with just an education-office code — no required filters (#218)."""
    adapter, _ = _build_adapter(["school_info.json"])
    dataset = adapter.get_dataset("school_info")

    batch = adapter.query_records(dataset, Query(filters={"ATPT_OFCDC_SC_CODE": "B10"}))

    assert len(batch.items) == 2
    assert batch.items[0]["SCHUL_NM"] == "서울중학교"
    assert batch.total_count == 2
