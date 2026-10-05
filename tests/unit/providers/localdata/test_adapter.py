"""Test module.

This file defines test scenarios and helper objects at
``tests/unit/providers/localdata/test_adapter.py``. It verifies core flows,
exceptions, and edge cases for regression prevention and public contract
validation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import MappingProxyType
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.exceptions import AuthError, ProviderResponseError
from kpubdata.providers.localdata.adapter import LocaldataAdapter
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
    return Path(__file__).resolve().parents[3] / "fixtures" / "localdata" / name


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
    payload = cast(object, json.loads(_fixture_path(name).read_text(encoding="utf-8")))
    if isinstance(payload, dict):
        return cast(dict[str, object], payload)
    raise ValueError(f"Fixture must be object: {name}")


class FakeResponse:
    """
    Class that encapsulates FakeResponse role and state.

    This class manages FakeResponse state and behavior together at
    ``tests/unit/providers/localdata/test_adapter.py``. Main method:
    __init__.

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
        self.text: str = json.dumps(payload)
        self.content: bytes = self.text.encode()


class FakeTransport:
    """
    Class that encapsulates FakeTransport role and state.

    This class manages FakeTransport state and behavior together at
    ``tests/unit/providers/localdata/test_adapter.py``. Main methods:
    __init__, request.

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
        return self._responses.pop(0)


def _build_adapter_with_transport(
    responses: list[FakeResponse],
) -> tuple[LocaldataAdapter, DatasetRef, FakeTransport]:
    """
    Internal helper to process build adapter with transport.

    Args:
        responses (list[FakeResponse]): Input value provided by caller.

    Returns:
        tuple[LocaldataAdapter, DatasetRef, FakeTransport]: Computed result
        or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.
    """
    transport = FakeTransport(responses)
    adapter = LocaldataAdapter(
        config=KPubDataConfig(provider_keys={"datago": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset("general_restaurant")
    return adapter, dataset, transport


def _build_dataset_adapter_with_transport(
    dataset_key: str,
    responses: list[FakeResponse],
) -> tuple[LocaldataAdapter, DatasetRef, FakeTransport]:
    """
    Internal helper to process build dataset adapter with transport.

    Args:
        dataset_key (str): Input value provided by caller.
        responses (list[FakeResponse]): Input value provided by caller.

    Returns:
        tuple[LocaldataAdapter, DatasetRef, FakeTransport]: Computed result
        or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.
    """
    transport = FakeTransport(responses)
    adapter = LocaldataAdapter(
        config=KPubDataConfig(provider_keys={"datago": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset(dataset_key)
    return adapter, dataset, transport


# Verifies scenario tested by test_query_records_parses_success_fixture.
def test_query_records_parses_success_fixture() -> None:
    """
    Verify test_query_records_parses_success_fixture scenario.

    Returns:
        None: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.

    Example:
        Verify expected behavior described by test name is maintained
        without regression.
    """
    payload = _load_fixture("general_restaurant_success.json")
    adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 3
    assert batch.total_count == 3
    assert batch.next_page is None
    assert batch.raw == payload
    assert batch.items[0]["BPLC_NM"] == "한밥식당"
    assert len(transport.calls) == 1


# Verifies scenario tested by test_query_records_raises_auth_error_on_auth_fixture.
def test_query_records_raises_auth_error_on_auth_fixture() -> None:
    """
    Verify test_query_records_raises_auth_error_on_auth_fixture scenario.

    Returns:
        None: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.

    Example:
        Verify expected behavior described by test name is maintained
        without regression.
    """
    payload = _load_fixture("error_auth.json")
    adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

    try:
        _ = adapter.query_records(dataset, Query())
    except AuthError as exc_info:
        assert exc_info.provider_code == "30"
        return

    raise AssertionError("AuthError was not raised")


# Verifies scenario tested by test_query_records_handles_empty_response.
def test_query_records_handles_empty_response() -> None:
    """
    Verify test_query_records_handles_empty_response scenario.

    Returns:
        None: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.

    Example:
        Verify expected behavior described by test name is maintained
        without regression.
    """
    payload = _load_fixture("empty_response.json")
    adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

    batch = adapter.query_records(dataset, Query())

    assert batch.items == []
    # The fixture carries ``totalCount: 0`` (#806).
    assert batch.total_count == 0
    assert batch.next_page is None


# Verifies scenario tested by test_query_records_handles_empty_response_logs_debug.
def test_query_records_handles_empty_response_logs_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Verify test_query_records_handles_empty_response_logs_debug scenario.

    Args:
        caplog (pytest.LogCaptureFixture): Input value provided by caller.

    Returns:
        None: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.

    Example:
        Verify expected behavior described by test name is maintained
        without regression.
    """
    payload = _load_fixture("empty_response.json")
    adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

    caplog.set_level(logging.DEBUG, logger="kpubdata.provider.localdata")
    batch = adapter.query_records(dataset, Query())

    assert batch.items == []
    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "Localdata envelope: zero items"
    )
    assert record.__dict__["dataset_id"] == dataset.id
    assert record.__dict__["page"] == 1
    assert record.__dict__["page_size"] == 100
    assert record.__dict__["total_count"] == 0


# Verifies scenario tested by test_query_records_sets_next_page_with_total_count.
def test_query_records_sets_next_page_with_total_count() -> None:
    """
    Verify test_query_records_sets_next_page_with_total_count scenario.

    Returns:
        None: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.

    Example:
        Verify expected behavior described by test name is maintained
        without regression.
    """
    payload = _load_fixture("general_restaurant_success.json")
    adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

    batch = adapter.query_records(dataset, Query(page=1, page_size=2))

    assert len(batch.items) == 3
    assert batch.total_count == 3
    assert batch.next_page == 2


# Verifies scenario tested by test_query_records_passes_local_code_filter.
def test_query_records_passes_local_code_filter() -> None:
    """
    Verify test_query_records_passes_local_code_filter scenario.

    Returns:
        None: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.

    Example:
        Verify expected behavior described by test name is maintained
        without regression.
    """
    payload = _load_fixture("general_restaurant_success.json")
    adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

    _ = adapter.query_records(dataset, Query(filters={"localCode": "41135"}))

    request_params = cast(dict[str, str], transport.calls[0]["params"])
    assert request_params["serviceKey"] == "test-key"
    assert request_params["type"] == "json"
    assert request_params["pageNo"] == "1"
    assert request_params["numOfRows"] == "100"
    assert request_params["localCode"] == "41135"


# Verifies scenario tested by test_rest_cafe_query_records_parses_success_fixture.
def test_rest_cafe_query_records_parses_success_fixture() -> None:
    """
    Verify test_rest_cafe_query_records_parses_success_fixture scenario.

    Returns:
        None: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.

    Example:
        Verify expected behavior described by test name is maintained
        without regression.
    """
    payload = _load_fixture("rest_cafe_success.json")
    adapter, dataset, _ = _build_dataset_adapter_with_transport(
        "rest_cafe", [FakeResponse(payload)]
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 3
    assert batch.items[0]["BPLC_NM"] == "카페모카"


# Verifies scenario tested by test_adapter_lists_all_datasets.
def test_adapter_lists_all_datasets() -> None:
    """
    Verify test_adapter_lists_all_datasets scenario.

    Returns:
        None: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.

    Example:
        Verify expected behavior described by test name is maintained
        without regression.
    """
    adapter = LocaldataAdapter(config=KPubDataConfig(provider_keys={"datago": "test-key"}))

    datasets = adapter.list_datasets()

    assert len(datasets) == 59
    assert [dataset.dataset_key for dataset in datasets] == [
        "general_restaurant",
        "rest_cafe",
        "bakery",
        "hospital",
        "clinic",
        "pharmacy",
        "animal_hospital",
        "optical_shop",
        "public_bath",
        "laundry",
        "barber_shop",
        "beauty_salon",
        "pet_grooming",
        "dance_academy",
        "karaoke",
        "singing_bar",
        "billiard_hall",
        "performance_hall",
        "movie_theater",
        "swimming_pool",
        "fitness_center",
        "ice_rink",
        "golf_course",
        "golf_practice_range",
        "horse_riding",
        "ski_resort",
        "affiliated_medical_institution",
        "postpartum_care",
        "dental_lab",
        "animal_import",
        "slaughterhouse",
        "hatchery",
        "youth_game_provider",
        "tourist_performance_hall",
        "tourism_business",
        "general_amusement_facility",
        "comprehensive_amusement_facility",
        "video_viewing_room",
        "tourist_accommodation",
        "tourist_pension",
        "online_music_service",
        "door_to_door_sales",
        "dance_hall",
        "yacht_marina",
        "comprehensive_sports_facility",
        "food_vending_machine",
        "milk_collection",
        "livestock_processing",
        "livestock_storage",
        "entertainment_bar",
        "tourist_restaurant",
        "tourist_entertainment_restaurant",
        "log_production",
        "sawmill",
        "high_pressure_gas",
        "groundwater_construction",
        "water_tank_cleaning",
        "publisher",
        "logistics_warehouse",
    ]


# Verifies scenario tested by test_build_request_url_missing_base_url_logs_debug.
def test_build_request_url_missing_base_url_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """
    Verify test_build_request_url_missing_base_url_logs_debug scenario.

    Args:
        caplog (pytest.LogCaptureFixture): Input value provided by caller.

    Returns:
        None: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.

    Example:
        Verify expected behavior described by test name is maintained
        without regression.
    """
    adapter, dataset, _ = _build_adapter_with_transport([])
    dataset = DatasetRef(
        id=dataset.id,
        provider=dataset.provider,
        dataset_key=dataset.dataset_key,
        name=dataset.name,
        representation=dataset.representation,
        operations=dataset.operations,
        raw_metadata=MappingProxyType(
            {k: v for k, v in dataset.raw_metadata.items() if k != "base_url"}
        ),
        query_support=dataset.query_support,
    )

    caplog.set_level(logging.DEBUG, logger="kpubdata.provider.localdata")
    with pytest.raises(ProviderResponseError, match="base_url"):
        _ = adapter.query_records(dataset, Query())

    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "Localdata dataset metadata missing base_url"
    )
    assert record.__dict__["dataset_id"] == dataset.id


# --- New dataset fixture parsing tests ---


_NEW_DATASETS = [
    ("bakery", "bakery_success.json", "중앙베이커리"),
    ("hospital", "hospital_success.json", "중앙내과의원"),
    ("clinic", "clinic_success.json", "대흥가정의원"),
    ("pharmacy", "pharmacy_success.json", "중앙약국"),
    ("animal_hospital", "animal_hospital_success.json", "중앙24시동물병원"),
    ("optical_shop", "optical_shop_success.json", "선화안경원"),
    ("public_bath", "public_bath_success.json", "중앙대중목욕탕"),
    ("laundry", "laundry_success.json", "깨끗한세탁소"),
    ("barber_shop", "barber_shop_success.json", "클래식이발관"),
    ("beauty_salon", "beauty_salon_success.json", "뷰티헤어살롱"),
    ("pet_grooming", "pet_grooming_success.json", "멍멍살롱중앙점"),
    ("dance_academy", "dance_academy_success.json", "대전리듬댄스학원"),
    ("karaoke", "karaoke_success.json", "노래천국"),
    ("singing_bar", "singing_bar_success.json", "은행스타유흥주점"),
    ("billiard_hall", "billiard_hall_success.json", "유천당구클럽"),
    ("performance_hall", "performance_hall_success.json", "중앙소극장"),
    ("movie_theater", "movie_theater_success.json", "중앙시네마"),
    ("swimming_pool", "swimming_pool_success.json", "산성아쿠아센터"),
    ("fitness_center", "fitness_center_success.json", "태평피트니스클럽"),
    ("ice_rink", "ice_rink_success.json", "대전아이스링크"),
    ("golf_course", "golf_course_success.json", "대전힐즈골프장"),
    ("golf_practice_range", "golf_practice_range_success.json", "문화스크린골프연습장"),
    ("horse_riding", "horse_riding_success.json", "보문승마클럽"),
    ("ski_resort", "ski_resort_success.json", "대전스노우리조트"),
    (
        "affiliated_medical_institution",
        "affiliated_medical_institution_success.json",
        "중앙부속의료기관",
    ),
    ("postpartum_care", "postpartum_care_success.json", "중앙산후조리업"),
    ("dental_lab", "dental_lab_success.json", "중앙치과기공소"),
    ("animal_import", "animal_import_success.json", "중앙동물수입업"),
    ("slaughterhouse", "slaughterhouse_success.json", "중앙도축업"),
    ("hatchery", "hatchery_success.json", "중앙부화업"),
    ("youth_game_provider", "youth_game_provider_success.json", "중앙청소년게임제공업"),
    ("tourist_performance_hall", "tourist_performance_hall_success.json", "중앙관광공연장업"),
    ("tourism_business", "tourism_business_success.json", "중앙관광사업자"),
    ("general_amusement_facility", "general_amusement_facility_success.json", "중앙일반유원시설업"),
    (
        "comprehensive_amusement_facility",
        "comprehensive_amusement_facility_success.json",
        "중앙종합유원시설업",
    ),
    ("video_viewing_room", "video_viewing_room_success.json", "중앙비디오물감상실업"),
    ("tourist_accommodation", "tourist_accommodation_success.json", "중앙관광숙박업"),
    ("tourist_pension", "tourist_pension_success.json", "중앙관광펜션업"),
    ("online_music_service", "online_music_service_success.json", "중앙온라인음악서비스제공업"),
    ("door_to_door_sales", "door_to_door_sales_success.json", "중앙방문판매업"),
    ("dance_hall", "dance_hall_success.json", "중앙무도장업"),
    ("yacht_marina", "yacht_marina_success.json", "중앙요트장업"),
    (
        "comprehensive_sports_facility",
        "comprehensive_sports_facility_success.json",
        "중앙종합체육시설업",
    ),
    ("food_vending_machine", "food_vending_machine_success.json", "중앙식품자동판매기영업"),
    ("milk_collection", "milk_collection_success.json", "중앙집유업"),
    ("livestock_processing", "livestock_processing_success.json", "중앙축산물가공업"),
    ("livestock_storage", "livestock_storage_success.json", "중앙축산물보관업"),
    ("entertainment_bar", "entertainment_bar_success.json", "중앙유흥주점영업"),
    ("tourist_restaurant", "tourist_restaurant_success.json", "중앙관광식당"),
    (
        "tourist_entertainment_restaurant",
        "tourist_entertainment_restaurant_success.json",
        "중앙관광유흥음식점업",
    ),
    ("log_production", "log_production_success.json", "중앙원목생산업"),
    ("sawmill", "sawmill_success.json", "중앙제재업"),
    ("high_pressure_gas", "high_pressure_gas_success.json", "중앙고압가스업"),
    ("groundwater_construction", "groundwater_construction_success.json", "중앙지하수시공업체"),
    ("water_tank_cleaning", "water_tank_cleaning_success.json", "중앙저수조청소업"),
    ("publisher", "publisher_success.json", "중앙출판사"),
    ("logistics_warehouse", "logistics_warehouse_success.json", "중앙물류창고업체"),
]


# Verifies scenario tested by test_new_dataset_query_records_parses_success_fixture.
@pytest.mark.parametrize(
    ("dataset_key", "fixture_name", "expected_first_name"),
    _NEW_DATASETS,
    ids=[d[0] for d in _NEW_DATASETS],
)
def test_new_dataset_query_records_parses_success_fixture(
    dataset_key: str,
    fixture_name: str,
    expected_first_name: str,
) -> None:
    """
    Verify test_new_dataset_query_records_parses_success_fixture scenario.

    Args:
        dataset_key (str): Input value provided by caller.
        fixture_name (str): Input value provided by caller.
        expected_first_name (str): Input value provided by caller.

    Returns:
        None: Computed result or return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.

    Example:
        Verify expected behavior described by test name is maintained
        without regression.
    """
    payload = _load_fixture(fixture_name)
    adapter, dataset, _ = _build_dataset_adapter_with_transport(
        dataset_key, [FakeResponse(payload)]
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 3
    assert batch.total_count == 3
    assert batch.items[0]["BPLC_NM"] == expected_first_name
