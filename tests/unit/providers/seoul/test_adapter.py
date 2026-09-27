"""Test module.

This file defines test scenarios and helper objects at
``tests/unit/providers/seoul/test_adapter.py``.
It verifies core flows, exceptions, and edge cases for regression
prevention and public contract validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import Query
from kpubdata.exceptions import AuthError, InvalidRequestError, ProviderResponseError
from kpubdata.providers.seoul.adapter import SeoulAdapter
from kpubdata.transport.http import HttpTransport


def _fixture_path(name: str) -> Path:
    """
    Internal helper to process fixture path.

    Args:
        name (str): Input value provided by caller.

    Returns:
        Path: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.
    """
    return Path(__file__).resolve().parents[3] / "fixtures" / "seoul" / name


def _load_fixture(name: str) -> dict[str, object]:
    """
    Internal helper to process load fixture.

    Args:
        name (str): Input value provided by caller.

    Returns:
        dict[str, object]: Computed result or return value from downstream
        calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.
    """
    return cast(dict[str, object], json.loads(_fixture_path(name).read_text(encoding="utf-8")))


class FakeResponse:
    """
    Class that encapsulates FakeResponse role and state.

    This class manages FakeResponse state and behavior together at
    ``tests/unit/providers/seoul/test_adapter.py``. Main method: __init__.

    Attributes:
        Properties defined in constructor and class body are shared as
        common context by downstream methods.
    """

    def __init__(self, payload: dict[str, object]) -> None:
        """
        Initialize internal state for instance.

        Args:
            payload (dict[str, object]): Input value provided by caller.

        Returns:
            None: Computed result or return value from downstream calls.

        Raises:
            Exceptions from implementation or downstream dependencies may be
            raised as-is.
        """
        self.headers: dict[str, str] = {"content-type": "application/json"}
        self.text: str = json.dumps(payload, ensure_ascii=False)
        self.content: bytes = self.text.encode("utf-8")


class FakeTransport:
    """
    Class that encapsulates FakeTransport role and state.

    This class manages FakeTransport state and behavior together at
    ``tests/unit/providers/seoul/test_adapter.py``. Main methods: __init__, request.

    Attributes:
        Properties defined in constructor and class body are shared as
        common context by downstream methods.
    """

    def __init__(self, responses: list[FakeResponse]) -> None:
        """
        Initialize internal state for instance.

        Args:
            responses (list[FakeResponse]): Input value provided by caller.

        Returns:
            None: Computed result or return value from downstream calls.

        Raises:
            Exceptions from implementation or downstream dependencies may be
            raised as-is.
        """
        self._responses: list[FakeResponse] = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        """
        Perform request operation.

        Args:
            method (str): Input value provided by caller.
            url (str): Input value provided by caller.
            **kwargs (object): Input value provided by caller.

        Returns:
            FakeResponse: Computed result or return value from downstream
            calls.

        Raises:
            Exceptions from implementation or downstream dependencies may be
            raised as-is.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No fixture responses remaining")
        return self._responses.pop(0)


def _build_adapter(
    responses: list[FakeResponse],
    *,
    config: KPubDataConfig | None = None,
) -> tuple[SeoulAdapter, FakeTransport]:
    """
    Internal helper to process build adapter.

    매개변수:
        responses (list[FakeResponse]): 호출자가 제공하는 입력 값이다.
        config (KPubDataConfig | None): 호출자가 제공하는 입력 값이다.

    반환값:
        tuple[SeoulAdapter, FakeTransport]: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.
    """
    transport = FakeTransport(responses)
    adapter = SeoulAdapter(
        config=config or KPubDataConfig(provider_keys={"seoul": "test-seoul-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter, transport


# Verifies scenario tested by test_query_records_builds_subway_url_with_path_key.
def test_query_records_builds_subway_url_with_path_key() -> None:
    """
    Verify test_query_records_builds_subway_url_with_path_key scenario.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, transport = _build_adapter(
        [FakeResponse(_load_fixture("subway_realtime_arrival_success.json"))]
    )
    dataset = adapter.get_dataset("subway_realtime_arrival")

    _ = adapter.query_records(dataset, Query(filters={"stationName": "강남"}))

    assert transport.calls[0]["url"] == (
        "http://swopenAPI.seoul.go.kr/api/subway/test-seoul-key/json/"
        "realtimeStationArrival/1/100/%EA%B0%95%EB%82%A8"
    )


# Verifies scenario tested by test_query_records_builds_bike_url_with_path_key.
def test_query_records_builds_bike_url_with_path_key() -> None:
    """
    Verify test_query_records_builds_bike_url_with_path_key scenario.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, transport = _build_adapter(
        [FakeResponse(_load_fixture("bike_rent_month_success.json"))]
    )
    dataset = adapter.get_dataset("bike_rent_month")

    _ = adapter.query_records(dataset, Query(filters={"RENT_NM": "202401"}, page_size=10))

    assert transport.calls[0]["url"] == (
        "http://openapi.seoul.go.kr:8088/test-seoul-key/json/tbCycleRentUseMonthInfo/1/10/202401"
    )


# Verifies scenario tested by test_query_records_parses_successful_envelope.
def test_query_records_parses_successful_envelope() -> None:
    """
    Verify test_query_records_parses_successful_envelope scenario.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, _ = _build_adapter(
        [FakeResponse(_load_fixture("subway_realtime_arrival_success.json"))]
    )
    dataset = adapter.get_dataset("subway_realtime_arrival")

    batch = adapter.query_records(
        dataset, Query(filters={"stationName": "강남"}, page=1, page_size=2)
    )

    assert len(batch.items) == 2
    assert batch.items[0]["statnNm"] == "강남"
    assert batch.total_count == 2
    assert batch.next_page is None


# Verifies scenario tested by test_info_100_raises_auth_error.
def test_info_100_raises_auth_error() -> None:
    """
    Verify test_info_100_raises_auth_error scenario.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, _ = _build_adapter([FakeResponse(_load_fixture("error_auth.json"))])
    dataset = adapter.get_dataset("subway_realtime_arrival")

    with pytest.raises(AuthError) as exc_info:
        _ = adapter.query_records(dataset, Query(filters={"stationName": "강남"}))

    assert exc_info.value.provider_code == "INFO-100"


# Verifies scenario tested by test_info_200_returns_empty_record_batch.
def test_info_200_returns_empty_record_batch() -> None:
    """
    Verify test_info_200_returns_empty_record_batch scenario.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, _ = _build_adapter([FakeResponse(_load_fixture("empty_response.json"))])
    dataset = adapter.get_dataset("subway_realtime_arrival")

    batch = adapter.query_records(dataset, Query(filters={"stationName": "강남"}))

    assert batch.items == []
    assert batch.total_count is None
    assert batch.next_page is None


# Verifies scenario tested by test_call_raw_returns_raw_payload.
def test_call_raw_returns_raw_payload() -> None:
    """
    Verify test_call_raw_returns_raw_payload scenario.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    payload = _load_fixture("bike_rent_month_success.json")
    adapter, _ = _build_adapter([FakeResponse(payload)])
    dataset = adapter.get_dataset("bike_rent_month")

    raw = adapter.call_raw(
        dataset,
        "tbCycleRentUseMonthInfo",
        {"RENT_NM": "202401", "page_no": 1, "page_size": 5},
    )

    assert raw == payload


# Verifies scenario tested by test_pagination_uses_index_window_in_url.
def test_pagination_uses_index_window_in_url() -> None:
    """
    Verify test_pagination_uses_index_window_in_url scenario.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, transport = _build_adapter(
        [FakeResponse(_load_fixture("bike_rent_month_success.json"))]
    )
    dataset = adapter.get_dataset("bike_rent_month")

    _ = adapter.query_records(dataset, Query(filters={"RENT_NM": "202401"}, page=2, page_size=10))

    assert "/11/20/202401" in cast(str, transport.calls[0]["url"])


# Verifies scenario tested by test_error_code_mapping_table.
@pytest.mark.parametrize(
    ("code", "expected_exception"),
    [
        ("INFO-300", AuthError),
        ("INFO-400", InvalidRequestError),
        ("INFO-500", ProviderResponseError),
        ("ERROR-300", InvalidRequestError),
        ("ERROR-336", InvalidRequestError),
        ("ERROR-600", ProviderResponseError),
        ("UNKNOWN-999", ProviderResponseError),
    ],
)
def test_error_code_mapping_table(code: str, expected_exception: type[Exception]) -> None:
    """
    Verify test_error_code_mapping_table scenario.

    매개변수:
        code (str): 호출자가 제공하는 입력 값이다.
        expected_exception (type[Exception]): 호출자가 제공하는 입력 값이다.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    payload: dict[str, object] = {
        "realtimeStationArrival": {
            "list_total_count": 0,
            "RESULT": {"CODE": code, "MESSAGE": f"error: {code}"},
            "row": [],
        }
    }
    adapter, _ = _build_adapter([FakeResponse(payload)])
    dataset = adapter.get_dataset("subway_realtime_arrival")

    with pytest.raises(expected_exception) as exc_info:
        _ = adapter.query_records(dataset, Query(filters={"stationName": "강남"}))

    provider_error = exc_info.value
    assert getattr(provider_error, "provider_code", None) == code


# Verifies scenario tested by test_config_from_env_injects_seoul_api_key.
def test_config_from_env_injects_seoul_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify test_config_from_env_injects_seoul_api_key scenario.

    매개변수:
        monkeypatch (pytest.MonkeyPatch): 호출자가 제공하는 입력 값이다.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    monkeypatch.setenv("KPUBDATA_SEOUL_API_KEY", "env-seoul-key")
    adapter, transport = _build_adapter(
        [FakeResponse(_load_fixture("subway_realtime_arrival_success.json"))],
        config=KPubDataConfig.from_env(),
    )
    dataset = adapter.get_dataset("subway_realtime_arrival")

    _ = adapter.query_records(dataset, Query(filters={"stationName": "강남"}))

    assert "/env-seoul-key/json/" in cast(str, transport.calls[0]["url"])


# Verifies scenario tested by test_page_size_over_1000_raises_invalid_request.
def test_page_size_over_1000_raises_invalid_request() -> None:
    """
    Verify test_page_size_over_1000_raises_invalid_request scenario.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, _ = _build_adapter([])
    dataset = adapter.get_dataset("bike_rent_month")

    with pytest.raises(InvalidRequestError, match="page_size must be <= 1000"):
        _ = adapter.query_records(dataset, Query(filters={"RENT_NM": "202401"}, page_size=1001))


# Verifies scenario tested by test_query_records_builds_park_info_url.
def test_query_records_builds_park_info_url() -> None:
    """
    Verify test_query_records_builds_park_info_url scenario.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, transport = _build_adapter([FakeResponse(_load_fixture("park_info.json"))])
    dataset = adapter.get_dataset("park_info")

    _ = adapter.query_records(dataset, Query(page_size=10))

    assert transport.calls[0]["url"] == (
        "http://openapi.seoul.go.kr:8088/test-seoul-key/json/GetParkInfo/1/10"
    )


# Verifies scenario tested by test_query_records_parses_park_info_response.
def test_query_records_parses_park_info_response() -> None:
    """
    Verify test_query_records_parses_park_info_response scenario.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, _ = _build_adapter([FakeResponse(_load_fixture("park_info.json"))])
    dataset = adapter.get_dataset("park_info")

    batch = adapter.query_records(dataset, Query(page=1, page_size=10))

    assert len(batch.items) == 1
    assert batch.items[0]["PARKING_NAME"] == "샘플 공영주차장"
    assert batch.total_count == 1


def test_query_records_builds_park_usage_url() -> None:
    adapter, transport = _build_adapter([FakeResponse(_load_fixture("park_usage.json"))])
    dataset = adapter.get_dataset("park_usage")

    _ = adapter.query_records(dataset, Query(page_size=10))

    assert transport.calls[0]["url"] == (
        "http://openapi.seoul.go.kr:8088/test-seoul-key/json/SearchParkInfoService/1/10"
    )


def test_query_records_parses_park_usage_response() -> None:
    adapter, _ = _build_adapter([FakeResponse(_load_fixture("park_usage.json"))])
    dataset = adapter.get_dataset("park_usage")

    batch = adapter.query_records(dataset, Query(page=1, page_size=10))

    assert len(batch.items) == 1
    assert batch.items[0]["P_PARK"] == "샘플 공원"


def test_query_records_builds_citydata_url_with_area_path() -> None:
    adapter, transport = _build_adapter([FakeResponse(_load_fixture("citydata.json"))])
    dataset = adapter.get_dataset("citydata")

    _ = adapter.query_records(dataset, Query(filters={"area": "광화문·덕수궁"}, page_size=1))

    assert transport.calls[0]["url"] == (
        "http://openapi.seoul.go.kr:8088/test-seoul-key/json/citydata_ppltn/1/1/"
        "%EA%B4%91%ED%99%94%EB%AC%B8%C2%B7%EB%8D%95%EC%88%98%EA%B6%81"
    )


def test_query_records_parses_citydata_top_level_response() -> None:
    adapter, _ = _build_adapter([FakeResponse(_load_fixture("citydata.json"))])
    dataset = adapter.get_dataset("citydata")

    batch = adapter.query_records(dataset, Query(filters={"area": "광화문·덕수궁"}, page_size=1))

    assert len(batch.items) == 1
    assert batch.items[0]["AREA_NM"] == "광화문·덕수궁"
    assert batch.total_count == 1
