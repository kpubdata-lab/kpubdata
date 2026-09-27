"""테스트 모듈.

이 파일은 ``tests/unit/providers/kosis/test_adapter.py`` 경로의 테스트 시나리오와 보조 객체를 정의한다.
회귀 방지와 공개 계약 검증을 위해 핵심 흐름, 예외, 가장자리 조건을 확인한다.
"""

from __future__ import annotations

import json
import logging
from importlib.resources import files
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.exceptions import AuthError, InvalidRequestError, ProviderResponseError
from kpubdata.providers._common import build_dataset_ref
from kpubdata.providers.kosis.adapter import KosisAdapter
from kpubdata.transport.http import HttpTransport


class FakeResponse:
    """
    FakeResponse 관련 역할을 캡슐화하는 클래스.

    이 클래스는 ``tests/unit/providers/kosis/test_adapter.py`` 모듈 안에서 FakeResponse의 상태와 동작을 함께 관리한다.
    주요 메서드: __init__.

    속성 설명:
        생성자와 클래스 본문에서 정의한 속성은 하위 메서드가 공통 문맥으로 재사용한다.
    """

    def __init__(self, payload: object) -> None:
        """
        인스턴스가 사용할 내부 상태를 초기화한다.

        매개변수:
            payload (object): 호출자가 제공하는 입력 값이다.

        반환값:
            None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

        예외:
            구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.
        """
        self.headers: dict[str, str] = {"content-type": "application/json"}
        self.text: str = json.dumps(payload)
        self.content: bytes = self.text.encode()


class FakeTransport:
    """
    FakeTransport 관련 역할을 캡슐화하는 클래스.

    이 클래스는 ``tests/unit/providers/kosis/test_adapter.py`` 모듈 안에서 FakeTransport의 상태와 동작을 함께 관리한다.
    주요 메서드: __init__, request.

    속성 설명:
        생성자와 클래스 본문에서 정의한 속성은 하위 메서드가 공통 문맥으로 재사용한다.
    """

    def __init__(self, responses: list[FakeResponse]) -> None:
        """
        인스턴스가 사용할 내부 상태를 초기화한다.

        매개변수:
            responses (list[FakeResponse]): 호출자가 제공하는 입력 값이다.

        반환값:
            None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

        예외:
            구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.
        """
        self._responses: list[FakeResponse] = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        """
        request 동작을 수행한다.

        매개변수:
            method (str): 호출자가 제공하는 입력 값이다.
            url (str): 호출자가 제공하는 입력 값이다.
            **kwargs (object): 호출자가 제공하는 입력 값이다.

        반환값:
            FakeResponse: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

        예외:
            구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._responses.pop(0)


def _build_adapter_with_transport(
    responses: list[FakeResponse],
    *,
    dataset_key: str = "population_migration",
) -> tuple[KosisAdapter, DatasetRef, FakeTransport]:
    """
    내부 헬퍼로서 build adapter with transport 처리를 담당한다.

    매개변수:
        responses (list[FakeResponse]): 호출자가 제공하는 입력 값이다.
        dataset_key (str): 호출자가 제공하는 입력 값이다.

    반환값:
        tuple[KosisAdapter, DatasetRef, FakeTransport]: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.
    """
    transport = FakeTransport(responses)
    adapter = KosisAdapter(
        config=KPubDataConfig(provider_keys={"kosis": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset(dataset_key)
    return adapter, dataset, transport


# test catalogue parses industrial production default query params 테스트가 검증하는 시나리오를 설명한다.
def test_catalogue_parses_industrial_production_default_query_params() -> None:
    """
    test catalogue parses industrial production default query params 시나리오를 검증한다.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    _, dataset, _ = _build_adapter_with_transport([], dataset_key="industrial_production")
    catalogue = cast(
        list[dict[str, object]],
        json.loads(
            files("kpubdata.providers.kosis").joinpath("catalogue.json").read_text(encoding="utf-8")
        ),
    )
    entry = next(entry for entry in catalogue if entry["dataset_key"] == "industrial_production")

    assert dataset.id == "kosis.industrial_production"
    assert dataset.raw_metadata["org_id"] == "101"
    assert dataset.raw_metadata["tbl_id"] == "DT_1J22003"
    assert dataset.raw_metadata["default_query_params"] == {
        "objL1": "T10",
        "itmId": "T",
        "prdSe": "M",
    }
    assert entry["default_query_params"] == {
        "objL1": "T10",
        "itmId": "T",
        "prdSe": "M",
    }


# test adapter docstring documents default query params merge rule 테스트가 검증하는 시나리오를 설명한다.
def test_adapter_docstring_documents_default_query_params_merge_rule() -> None:
    """
    test adapter docstring documents default query params merge rule 시나리오를 검증한다.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    assert KosisAdapter.__doc__ is not None
    assert "dataset default_query_params < query.filters (caller priority)" in KosisAdapter.__doc__


# test query records missing start date logs debug 테스트가 검증하는 시나리오를 설명한다.
def test_query_records_missing_start_date_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """
    test query records missing start date logs debug 시나리오를 검증한다.

    매개변수:
        caplog (pytest.LogCaptureFixture): 호출자가 제공하는 입력 값이다.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, dataset, _ = _build_adapter_with_transport([])

    caplog.set_level(logging.DEBUG, logger="kpubdata.provider.kosis")
    with pytest.raises(InvalidRequestError, match="start_date"):
        _ = adapter.query_records(dataset, Query(end_date="202401"))

    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "KOSIS invalid query: missing start_date"
    )
    assert record.__dict__["dataset_id"] == dataset.id


# test query records zero items logs debug 테스트가 검증하는 시나리오를 설명한다.
def test_query_records_zero_items_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """
    test query records zero items logs debug 시나리오를 검증한다.

    매개변수:
        caplog (pytest.LogCaptureFixture): 호출자가 제공하는 입력 값이다.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, dataset, _ = _build_adapter_with_transport([FakeResponse([])])

    caplog.set_level(logging.DEBUG, logger="kpubdata.provider.kosis")
    batch = adapter.query_records(dataset, Query(start_date="202401", end_date="202401"))

    assert batch.items == []
    record = next(
        record for record in caplog.records if record.getMessage() == "KOSIS envelope: zero items"
    )
    assert record.__dict__["dataset_id"] == dataset.id
    assert record.__dict__["page"] is None
    assert record.__dict__["page_size"] == 100
    assert record.__dict__["total_count"] == 0


# test population migration keeps hardcoded default query params 테스트가 검증하는 시나리오를 설명한다.
def test_population_migration_keeps_hardcoded_default_query_params() -> None:
    """
    test population migration keeps hardcoded default query params 시나리오를 검증한다.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, dataset, transport = _build_adapter_with_transport([FakeResponse([])])

    batch = adapter.query_records(dataset, Query(start_date="202401", end_date="202401"))

    assert batch.items == []
    request_url = cast(str, transport.calls[0]["url"])
    assert "objL1=ALL" in request_url
    assert "objL2=ALL" in request_url
    assert "itmId=ALL" in request_url
    assert "prdSe=M" in request_url


# test query records applies dataset default query params when filters absent 테스트가 검증하는 시나리오를 설명한다.
def test_query_records_applies_dataset_default_query_params_when_filters_absent() -> None:
    """
    test query records applies dataset default query params when filters absent 시나리오를 검증한다.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, dataset, transport = _build_adapter_with_transport(
        [FakeResponse([])],
        dataset_key="industrial_production",
    )

    _ = adapter.query_records(dataset, Query(start_date="202401", end_date="202401"))

    request_url = cast(str, transport.calls[0]["url"])
    assert "objL1=T10" in request_url
    assert "itmId=T" in request_url
    assert "prdSe=M" in request_url
    assert "objL2=ALL" not in request_url


# test query records merges default query params but query filters win 테스트가 검증하는 시나리오를 설명한다.
def test_query_records_merges_default_query_params_but_query_filters_win() -> None:
    """
    test query records merges default query params but query filters win 시나리오를 검증한다.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, dataset, transport = _build_adapter_with_transport(
        [FakeResponse([])],
        dataset_key="industrial_production",
    )

    _ = adapter.query_records(
        dataset,
        Query(
            start_date="202401",
            end_date="202401",
            filters={"objL1": "T20", "itmId": "X", "prdSe": "Q"},
        ),
    )

    request_url = cast(str, transport.calls[0]["url"])
    assert "objL1=T20" in request_url
    assert "itmId=X" in request_url
    assert "prdSe=Q" in request_url
    assert "objL1=T10" not in request_url
    assert "itmId=T" not in request_url


# test query records ignores non kosis default query param keys 테스트가 검증하는 시나리오를 설명한다.
def test_query_records_ignores_non_kosis_default_query_param_keys() -> None:
    """
    test query records ignores non kosis default query param keys 시나리오를 검증한다.

    반환값:
        None: 계산 결과 또는 하위 호출의 반환값을 돌려준다.

    예외:
        구현체 내부 또는 하위 의존성에서 발생한 예외를 그대로 전파할 수 있다.

    예시:
        테스트 이름이 설명하는 기대 동작이 회귀 없이 유지되는지 확인한다.
    """
    adapter, _, transport = _build_adapter_with_transport([FakeResponse([])])
    dataset = build_dataset_ref(
        "kosis",
        {
            "dataset_key": "custom_defaults",
            "name": "Custom Defaults",
            "representation": "api_json",
            "base_url": "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            "org_id": "101",
            "tbl_id": "DT_1J22003",
            "default_query_params": {
                "objL1": "T10",
                "itmId": "T",
                "unknown": "ignored",
                "apiKey": "ignored",
            },
        },
    )

    _ = adapter.query_records(dataset, Query(start_date="202401", end_date="202401"))

    request_url = cast(str, transport.calls[0]["url"])
    assert "objL1=T10" in request_url
    assert "itmId=T" in request_url
    assert "unknown=ignored" not in request_url
    assert request_url.count("apiKey=") == 1


# test raise for error payload returns none when err field absent 테스트가 검증하는 시나리오를 설명한다.
def test_raise_for_error_payload_returns_none_when_err_field_absent() -> None:
    """에러 필드 없는 딕셔너리 페이로드에서 _raise_for_error_payload가 None을 반환하는지 검증한다."""
    adapter, dataset, _ = _build_adapter_with_transport([])
    # 에러 없는 딕셔너리 — 예외 없이 반환돼야 한다 (이전 구현은 항상 ProviderResponseError 발생)
    result = adapter._raise_for_error_payload({"some_field": "some_value"}, dataset.id)
    assert result is None


# test raise for error payload raises auth error on code 30 테스트가 검증하는 시나리오를 설명한다.
def test_raise_for_error_payload_raises_auth_error_on_code_30() -> None:
    """err=30 페이로드에서 AuthError가 발생하는지 검증한다."""
    adapter, dataset, _ = _build_adapter_with_transport([])
    with pytest.raises(AuthError):
        adapter._raise_for_error_payload({"err": "30", "errMsg": "인증키 오류"}, dataset.id)


# test raise for error payload raises invalid request error on code 10 테스트가 검증하는 시나리오를 설명한다.
def test_raise_for_error_payload_raises_invalid_request_error_on_code_10() -> None:
    """err=10 페이로드에서 InvalidRequestError가 발생하는지 검증한다."""
    adapter, dataset, _ = _build_adapter_with_transport([])
    with pytest.raises(InvalidRequestError):
        adapter._raise_for_error_payload({"err": "10", "errMsg": "잘못된 요청"}, dataset.id)


# test raise for error payload raises provider response error on unknown code 테스트가 검증하는 시나리오를 설명한다.
def test_raise_for_error_payload_raises_provider_response_error_on_unknown_code() -> None:
    """알 수 없는 err 코드 페이로드에서 ProviderResponseError가 발생하는지 검증한다."""
    adapter, dataset, _ = _build_adapter_with_transport([])
    with pytest.raises(ProviderResponseError):
        adapter._raise_for_error_payload({"err": "99", "errMsg": "기타 오류"}, dataset.id)
