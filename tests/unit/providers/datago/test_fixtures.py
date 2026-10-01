"""Test module.

This module defines tests and helpers for the surrounding test suite.
"""

from __future__ import annotations

from typing import Protocol, cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.exceptions import (
    AuthError,
    InvalidRequestError,
    RateLimitError,
    ServiceUnavailableError,
)
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.transport.http import HttpTransport

from .conftest import FixtureTransport, load_fixture_bytes, load_json_fixture


class AdapterFactory(Protocol):
    """Tests for AdapterFactory.

    This class groups related test cases and helpers for AdapterFactory.
    """

    def __call__(
        self,
        fixture_names: list[str],
        content_type: str = "application/json",
    ) -> tuple[DataGoAdapter, DatasetRef, FixtureTransport]: ...


def _build_real_estate_adapter(
    fixture_name: str, dataset_key: str
) -> tuple[DataGoAdapter, DatasetRef]:
    """Validates the scenario described by the test name."""
    data = load_fixture_bytes(fixture_name)

    class _FakeResponse:
        """Tests for _FakeResponse.

        This class groups related test cases and helpers for _FakeResponse.
        """

        def __init__(self) -> None:
            """
            Initialize with payload.

            Returns:
                None: Result.

            Raises:
                Exceptions propagated."""
            self.headers: dict[str, str] = {"content-type": "application/json"}
            self.content: bytes = data
            self.text: str = data.decode("utf-8")

    class _FakeTransport:
        """Tests for _FakeTransport.

        This class groups related test cases and helpers for _FakeTransport.
        """

        def request(self, _method: str, _url: str, **_kwargs: object) -> _FakeResponse:
            """
            Execute a mock HTTP request.

            Args:
                _method (str): Input parameter.
                _url (str): Input parameter.
                **_kwargs (object): Input parameter.

            Returns:
                _FakeResponse: Result.

            Raises:
                Exceptions propagated."""
            return _FakeResponse()

    config = KPubDataConfig(provider_keys={"datago": "test-key"})
    adapter = DataGoAdapter(
        config=config,
        transport=cast(HttpTransport, cast(object, _FakeTransport())),
    )
    dataset = adapter.get_dataset(dataset_key)
    return adapter, dataset


# test fixture dur usjnt taboo parses Describes the scenario verified by the test.
def test_fixture_dur_usjnt_taboo_parses() -> None:
    """
    test fixture dur usjnt taboo parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_dur_usjnt_taboo.json", "dur_usjnt_taboo")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["ITEM_NAME"] == "샘플정A"
    assert "MIXTURE_ITEM_NAME" in batch.items[0]
    assert "PROHBT_CONTENT" in batch.items[0]
    assert batch.total_count == 2


# test fixture dur usjnt taboo call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_dur_usjnt_taboo_call_raw_returns_full_envelope() -> None:
    """
    test fixture dur usjnt taboo call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_dur_usjnt_taboo.json", "dur_usjnt_taboo")
    expected = load_json_fixture("success_dur_usjnt_taboo.json")

    payload = adapter.call_raw(dataset, "getUsjntTabooInfoList03", {"itemName": "샘플"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture dur older adult caution parses Describes the scenario verified by the test.
def test_fixture_dur_older_adult_caution_parses() -> None:
    """
    test fixture dur older adult caution parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_older_adult_caution.json", "dur_older_adult_caution"
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["ITEM_NAME"] == "샘플정E"
    assert "CLASS_NAME" in batch.items[0]
    assert "ODSN_ATENT_CN" in batch.items[0]
    assert batch.total_count == 2


# test fixture dur older adult caution call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_dur_older_adult_caution_call_raw_returns_full_envelope() -> None:
    """
    test fixture dur older adult caution call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_older_adult_caution.json", "dur_older_adult_caution"
    )
    expected = load_json_fixture("success_dur_older_adult_caution.json")

    payload = adapter.call_raw(dataset, "getOdsnAtentInfoList03", {"itemName": "샘플"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture dur product info parses Describes the scenario verified by the test.
def test_fixture_dur_product_info_parses() -> None:
    """
    test fixture dur product info parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_product_info.json", "dur_product_info"
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["ITEM_NAME"] == "샘플정G"
    assert "ETC_OTC_CODE" in batch.items[0]
    assert "CHART" in batch.items[0]
    assert batch.total_count == 2


# test fixture dur product info call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_dur_product_info_call_raw_returns_full_envelope() -> None:
    """
    test fixture dur product info call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_product_info.json", "dur_product_info"
    )
    expected = load_json_fixture("success_dur_product_info.json")

    payload = adapter.call_raw(dataset, "getDurPrdlstInfoList03", {"itemName": "샘플"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture single page Describes the scenario verified by the test.
def test_fixture_single_page(configured_adapter: AdapterFactory) -> None:
    """
    test fixture single page Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(["success_single_page.json"])

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 3
    assert batch.total_count == 3
    assert batch.next_page is None
    assert isinstance(batch.raw, dict)


# test fixture multi page pagination Describes the scenario verified by the test.
def test_fixture_multi_page_pagination(configured_adapter: AdapterFactory) -> None:
    """
    test fixture multi page pagination Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(
        ["success_multi_page_1.json", "success_multi_page_2.json"]
    )

    batch = adapter.query_records(dataset, Query(page_size=2))

    assert len(batch.items) == 2
    assert [item["stationName"] for item in batch.items] == ["종로구", "강남구"]
    assert batch.next_page == 2


# test fixture single item normalization Describes the scenario verified by the test.
def test_fixture_single_item_normalization(configured_adapter: AdapterFactory) -> None:
    """
    test fixture single item normalization Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(["success_single_item.json"])

    batch = adapter.query_records(dataset, Query())

    assert batch.items == [{"stationName": "종로구", "pm10Value": "45"}]
    assert batch.total_count == 1


# test fixture empty response Describes the scenario verified by the test.
def test_fixture_empty_response(configured_adapter: AdapterFactory) -> None:
    """
    test fixture empty response Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(["success_empty.json"])

    batch = adapter.query_records(dataset, Query())

    assert batch.items == []
    assert batch.total_count is None


# test fixture string numerics Describes the scenario verified by the test.
def test_fixture_string_numerics(configured_adapter: AdapterFactory) -> None:
    """
    test fixture string numerics Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(["success_string_numerics.json"])

    batch = adapter.query_records(dataset, Query(page=1, page_size=100))

    assert isinstance(batch.total_count, int)
    assert batch.total_count == 1


# test fixture auth error Describes the scenario verified by the test.
def test_fixture_auth_error(configured_adapter: AdapterFactory) -> None:
    """
    test fixture auth error Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(["error_auth_30.json"])

    with pytest.raises(AuthError) as excinfo:
        _ = adapter.query_records(dataset, Query())

    assert excinfo.value.provider_code == "30"


# test fixture rate limit Describes the scenario verified by the test.
def test_fixture_rate_limit(configured_adapter: AdapterFactory) -> None:
    """
    test fixture rate limit Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(["error_rate_limit_22.json"])

    with pytest.raises(RateLimitError) as excinfo:
        _ = adapter.query_records(dataset, Query())

    assert excinfo.value.provider_code == "22"
    assert excinfo.value.retryable is False


# test fixture invalid request Describes the scenario verified by the test.
def test_fixture_invalid_request(configured_adapter: AdapterFactory) -> None:
    """
    test fixture invalid request Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(["error_invalid_request_10.json"])

    with pytest.raises(InvalidRequestError):
        _ = adapter.query_records(dataset, Query())


# test fixture service unavailable Describes the scenario verified by the test.
def test_fixture_service_unavailable(configured_adapter: AdapterFactory) -> None:
    """
    test fixture service unavailable Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(["error_service_unavailable_01.json"])

    with pytest.raises(ServiceUnavailableError):
        _ = adapter.query_records(dataset, Query())


# test fixture xml response Describes the scenario verified by the test.
def test_fixture_xml_response(configured_adapter: AdapterFactory) -> None:
    """
    test fixture xml response Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    pytest.importorskip("xmltodict")
    adapter, dataset, _ = configured_adapter(["success_xml.xml"], "application/xml")

    batch = adapter.query_records(dataset, Query())

    assert [item["stationName"] for item in batch.items] == ["종로구", "강남구"]
    assert batch.total_count == 2


# test fixture records have korean text Describes the scenario verified by the test.
def test_fixture_records_have_korean_text(configured_adapter: AdapterFactory) -> None:
    """
    test fixture records have korean text Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(["success_single_page.json"])

    batch = adapter.query_records(dataset, Query())

    assert batch.items[0]["stationName"] == "종로구"
    assert batch.items[1]["stationName"] == "강남구"


# test fixture call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_call_raw_returns_full_envelope(configured_adapter: AdapterFactory) -> None:
    """
    test fixture call raw returns full envelope Validates the scenario described by the test name.

    Args:
        configured_adapter (AdapterFactory): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, _ = configured_adapter(["success_single_page.json"])
    expected = load_json_fixture("success_single_page.json")

    payload = adapter.call_raw(dataset, "getVilageFcst", {})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture apt rent parses Describes the scenario verified by the test.
def test_fixture_apt_rent_parses() -> None:
    """
    test fixture apt rent parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_apt_rent.json", "apt_rent")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "deposit" in batch.items[0]
    assert "monthlyRent" in batch.items[0]
    assert batch.total_count == 2


# test fixture offi trade parses Describes the scenario verified by the test.
def test_fixture_offi_trade_parses() -> None:
    """
    test fixture offi trade parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_offi_trade.json", "offi_trade")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "dealAmount" in batch.items[0]
    assert batch.total_count == 2


# test fixture offi rent parses Describes the scenario verified by the test.
def test_fixture_offi_rent_parses() -> None:
    """
    test fixture offi rent parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_offi_rent.json", "offi_rent")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "deposit" in batch.items[0]
    assert "monthlyRent" in batch.items[0]
    assert batch.total_count == 2


# test fixture rh trade parses Describes the scenario verified by the test.
def test_fixture_rh_trade_parses() -> None:
    """
    test fixture rh trade parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_rh_trade.json", "rh_trade")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "dealAmount" in batch.items[0]
    assert batch.total_count == 2


# test fixture rh rent parses Describes the scenario verified by the test.
def test_fixture_rh_rent_parses() -> None:
    """
    test fixture rh rent parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_rh_rent.json", "rh_rent")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "deposit" in batch.items[0]
    assert "monthlyRent" in batch.items[0]
    assert batch.total_count == 2


# test fixture sh trade parses Describes the scenario verified by the test.
def test_fixture_sh_trade_parses() -> None:
    """
    test fixture sh trade parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_sh_trade.json", "sh_trade")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "dealAmount" in batch.items[0]
    assert batch.total_count == 2


# test fixture sh rent parses Describes the scenario verified by the test.
def test_fixture_sh_rent_parses() -> None:
    """
    test fixture sh rent parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_sh_rent.json", "sh_rent")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "deposit" in batch.items[0]
    assert "monthlyRent" in batch.items[0]
    assert batch.total_count == 2


# test fixture tour kor area parses Describes the scenario verified by the test.
def test_fixture_tour_kor_area_parses() -> None:
    """
    test fixture tour kor area parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_tour_kor_area.json", "tour_kor_area")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["title"] == "경복궁"
    assert "contentid" in batch.items[0]
    assert batch.total_count == 2


# test fixture tour kor location parses Describes the scenario verified by the test.
def test_fixture_tour_kor_location_parses() -> None:
    """
    test fixture tour kor location parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_tour_kor_location.json", "tour_kor_location"
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "dist" in batch.items[0]
    assert batch.total_count == 2


# test fixture tour kor keyword parses Describes the scenario verified by the test.
def test_fixture_tour_kor_keyword_parses() -> None:
    """
    test fixture tour kor keyword parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_tour_kor_keyword.json", "tour_kor_keyword"
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "title" in batch.items[0]
    assert batch.total_count == 2


# test fixture tour kor festival parses Describes the scenario verified by the test.
def test_fixture_tour_kor_festival_parses() -> None:
    """
    test fixture tour kor festival parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_tour_kor_festival.json", "tour_kor_festival"
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "eventstartdate" in batch.items[0]
    assert "eventenddate" in batch.items[0]
    assert batch.total_count == 2


# test fixture metro fare parses Describes the scenario verified by the test.
def test_fixture_metro_fare_parses() -> None:
    """
    test fixture metro fare parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_metro_fare.json", "metro_fare")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "startStation" in batch.items[0]
    assert "endStation" in batch.items[0]
    assert "fareCard" in batch.items[0]
    assert batch.total_count == 2


# test fixture road traffic call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_road_traffic_call_raw_returns_full_envelope() -> None:
    """
    test fixture road traffic call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_road_traffic.json", "road_traffic")
    expected = load_json_fixture("success_road_traffic.json")

    payload = adapter.call_raw(dataset, "trafficInfo", {"type": "all", "drcType": "all"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    assert payload_dict["resultCode"] == "00"
    items = cast(list[dict[str, object]], payload_dict["items"])
    assert len(items) == 3
    first = items[0]
    assert first["roadName"] == "경부고속도로"
    assert first["linkId"] == "1610038501"


# test fixture road traffic list parses flat envelope Describes the scenario verified by the test.
def test_fixture_road_traffic_list_parses_flat_envelope() -> None:
    """
    test fixture road traffic list parses flat envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_road_traffic.json", "road_traffic")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 3
    assert batch.items[0]["roadName"] == "경부고속도로"
    assert "speed" in batch.items[0]
    assert "travelTime" in batch.items[0]
    assert batch.total_count == 3


# test fixture g2b catalog parses Describes the scenario verified by the test.
def test_fixture_g2b_catalog_parses() -> None:
    """
    test fixture g2b catalog parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_g2b_catalog.json", "g2b_catalog")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert "prdctIdntNo" in batch.items[0]
    assert "prdctClsfcNoNm" in batch.items[0]
    assert "cntrctCorpNm" in batch.items[0]
    assert batch.total_count == 7607


# test datago g2b catalog default filters Describes the scenario verified by the test.
def test_datago_g2b_catalog_default_filters_fill_required_param() -> None:
    """test_datago_g2b_catalog_default_filters_fill_required_param

    Validates the scenario described by the test name.
    """
    transport = FixtureTransport(fixture_names=["success_g2b_catalog.json"])
    config = KPubDataConfig(provider_keys={"datago": "test-key"})
    adapter = DataGoAdapter(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset("g2b_catalog")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    first_call = cast(dict[str, object], transport.calls[0])
    first_params = cast(dict[str, object], first_call["params"])
    assert first_params["inqryDiv"] == "1"

    # user filters override defaults.
    second_transport = FixtureTransport(fixture_names=["success_g2b_catalog.json"])
    second_adapter = DataGoAdapter(
        config=config,
        transport=cast(HttpTransport, cast(object, second_transport)),
    )
    _ = second_adapter.query_records(
        second_adapter.get_dataset("g2b_catalog"), Query(filters={"inqryDiv": "2"})
    )
    second_call = cast(dict[str, object], second_transport.calls[0])
    second_params = cast(dict[str, object], second_call["params"])
    assert second_params["inqryDiv"] == "2"


def test_datago_g2b_catalog_default_filters_call_raw() -> None:
    """call_raw path also default_filtersis applied."""
    transport = FixtureTransport(fixture_names=["success_g2b_catalog.json"])
    config = KPubDataConfig(provider_keys={"datago": "test-key"})
    adapter = DataGoAdapter(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset("g2b_catalog")

    adapter.call_raw(dataset, next(iter(dataset.operations)), params={})

    first_call = cast(dict[str, object], transport.calls[0])
    first_params = cast(dict[str, object], first_call["params"])
    assert first_params.get("inqryDiv") == "1"


def test_datago_g2b_catalog_call_raw_user_override() -> None:
    """test_datago_g2b_catalog_call_raw_user_override

    Validates the scenario described by the test name.
    """
    transport = FixtureTransport(fixture_names=["success_g2b_catalog.json"])
    config = KPubDataConfig(provider_keys={"datago": "test-key"})
    adapter = DataGoAdapter(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset("g2b_catalog")

    adapter.call_raw(dataset, next(iter(dataset.operations)), params={"inqryDiv": "2"})

    first_call = cast(dict[str, object], transport.calls[0])
    first_params = cast(dict[str, object], first_call["params"])
    assert first_params["inqryDiv"] == "2"


def test_datago_default_filters_case_insensitive_user_override() -> None:
    """test_datago_default_filters_case_insensitive_user_override

    Validates the scenario described by the test name.
    """
    transport = FixtureTransport(fixture_names=["success_g2b_catalog.json"])
    config = KPubDataConfig(provider_keys={"datago": "test-key"})
    adapter = DataGoAdapter(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset("g2b_catalog")

    # Verifies test behavior (see test name for details).
    adapter.query_records(dataset, Query(filters={"inqrydiv": "3"}))

    first_call = cast(dict[str, object], transport.calls[0])
    first_params = cast(dict[str, object], first_call["params"])
    # user lowercase key preserved default "inqryDiv"should not be duplicated
    assert first_params.get("inqrydiv") == "3"
    assert "inqryDiv" not in first_params


# test fixture dur age taboo parses Describes the scenario verified by the test.
def test_fixture_dur_age_taboo_parses() -> None:
    """
    test fixture dur age taboo parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_dur_age_taboo.json", "dur_age_taboo")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["ITEM_NAME"] == "샘플정G"
    assert "CLASS_NAME" in batch.items[0]
    assert "SPCIFY_AGRDE_TABOO_CN" in batch.items[0]
    assert batch.total_count == 2


# test fixture dur age taboo call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_dur_age_taboo_call_raw_returns_full_envelope() -> None:
    """
    test fixture dur age taboo call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_dur_age_taboo.json", "dur_age_taboo")
    expected = load_json_fixture("success_dur_age_taboo.json")

    payload = adapter.call_raw(dataset, "getSpcifyAgrdeTabooInfoList03", {"itemName": "샘플"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture dur dosage caution parses Describes the scenario verified by the test.
def test_fixture_dur_dosage_caution_parses() -> None:
    """
    test fixture dur dosage caution parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_dosage_caution.json", "dur_dosage_caution"
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["ITEM_NAME"] == "샘플정G"
    assert "CLASS_NAME" in batch.items[0]
    assert "CPCTY_ATENT_CN" in batch.items[0]
    assert batch.total_count == 2


# test fixture dur dosage caution call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_dur_dosage_caution_call_raw_returns_full_envelope() -> None:
    """
    test fixture dur dosage caution call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_dosage_caution.json", "dur_dosage_caution"
    )
    expected = load_json_fixture("success_dur_dosage_caution.json")

    payload = adapter.call_raw(dataset, "getCpctyAtentInfoList03", {"itemName": "샘플"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture dur medication period caution parses Describes the scenario verified by the test.
def test_fixture_dur_medication_period_caution_parses() -> None:
    """
    test fixture dur medication period caution parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_medication_period_caution.json",
        "dur_medication_period_caution",
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["ITEM_NAME"] == "샘플정I"
    assert "CLASS_NAME" in batch.items[0]
    assert "MDCTN_PD_ATENT_CN" in batch.items[0]
    assert batch.total_count == 2


# test fixture dur medication period caution call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_dur_medication_period_caution_call_raw_returns_full_envelope() -> None:
    """
    test fixture dur medication period caution call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_medication_period_caution.json",
        "dur_medication_period_caution",
    )
    expected = load_json_fixture("success_dur_medication_period_caution.json")

    payload = adapter.call_raw(dataset, "getMdctnPdAtentInfoList03", {"itemName": "샘플"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture dur efficacy duplication parses Describes the scenario verified by the test.
def test_fixture_dur_efficacy_duplication_parses() -> None:
    """
    test fixture dur efficacy duplication parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_efficacy_duplication.json", "dur_efficacy_duplication"
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["ITEM_NAME"] == "샘플정G"
    assert "SERS_NAME" in batch.items[0]
    assert "PROHBT_CONTENT" in batch.items[0]
    assert batch.total_count == 2


# test fixture dur efficacy duplication call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_dur_efficacy_duplication_call_raw_returns_full_envelope() -> None:
    """
    test fixture dur efficacy duplication call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_efficacy_duplication.json", "dur_efficacy_duplication"
    )
    expected = load_json_fixture("success_dur_efficacy_duplication.json")

    payload = adapter.call_raw(dataset, "getEfcyDplctInfoList03", {"itemName": "샘플"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture dur er tablet split caution parses Describes the scenario verified by the test.
def test_fixture_dur_er_tablet_split_caution_parses() -> None:
    """
    test fixture dur er tablet split caution parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_er_tablet_split_caution.json", "dur_er_tablet_split_caution"
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["ITEM_NAME"] == "샘플서방정A"
    assert "CLASS_NAME" in batch.items[0]
    assert "SEOBANGJEONG_PARTITN_ATENT_CN" in batch.items[0]
    assert batch.total_count == 2


# test fixture dur er tablet split caution call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_dur_er_tablet_split_caution_call_raw_returns_full_envelope() -> None:
    """
    test fixture dur er tablet split caution call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_er_tablet_split_caution.json", "dur_er_tablet_split_caution"
    )
    expected = load_json_fixture("success_dur_er_tablet_split_caution.json")

    payload = adapter.call_raw(
        dataset,
        "getSeobangjeongPartitnAtentInfoList03",
        {"itemName": "샘플"},
    )

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture dur pregnancy taboo parses Describes the scenario verified by the test.
def test_fixture_dur_pregnancy_taboo_parses() -> None:
    """
    test fixture dur pregnancy taboo parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_pregnancy_taboo.json", "dur_pregnancy_taboo"
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["ITEM_NAME"] == "샘플정I"
    assert "PREGNANT_GRADE" in batch.items[0]
    assert "PREGNANT_PROHBT_CN" in batch.items[0]
    assert batch.total_count == 2


# test fixture dur pregnancy taboo call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_dur_pregnancy_taboo_call_raw_returns_full_envelope() -> None:
    """
    test fixture dur pregnancy taboo call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter(
        "success_dur_pregnancy_taboo.json", "dur_pregnancy_taboo"
    )
    expected = load_json_fixture("success_dur_pregnancy_taboo.json")

    payload = adapter.call_raw(dataset, "getPwnmTabooInfoList03", {"itemName": "샘플"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture agri price parses Describes the scenario verified by the test.
def test_fixture_agri_price_parses() -> None:
    """
    test fixture agri price parses Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_agri_price.json", "agri_price")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 3
    assert batch.items[0]["item_nm"] == "쌀"
    assert "exmn_dd_prc" in batch.items[0]
    assert "sgg_nm" in batch.items[0]
    assert "grd_nm" in batch.items[0]
    assert batch.total_count == 3


# test fixture agri price call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_agri_price_call_raw_returns_full_envelope() -> None:
    """
    test fixture agri price call raw returns full envelope Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset = _build_real_estate_adapter("success_agri_price.json", "agri_price")
    expected = load_json_fixture("success_agri_price.json")

    payload = adapter.call_raw(dataset, "price", {"cond[exmn_ymd::GTE]": "20240101"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


def test_fixture_subway_passengers_parses() -> None:
    adapter, dataset = _build_real_estate_adapter(
        "success_subway_passengers.json", "subway_passengers"
    )

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 2
    assert batch.items[0]["stnNm"] == "남위례"
    assert batch.items[0]["lineNm"] == "8호선"
    assert "rideNope" in batch.items[0]
    assert "gffNope" in batch.items[0]
    assert batch.total_count == 2


def test_fixture_subway_passengers_call_raw_returns_full_envelope() -> None:
    adapter, dataset = _build_real_estate_adapter(
        "success_subway_passengers.json", "subway_passengers"
    )
    expected = load_json_fixture("success_subway_passengers.json")

    payload = adapter.call_raw(dataset, "getStnPsgr", {"pasngYmd": "20260521"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


def test_fixture_mid_fcst_parses() -> None:
    adapter, dataset = _build_real_estate_adapter("success_mid_fcst.json", "mid_fcst")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 1
    assert "wfSv" in batch.items[0]
    assert batch.total_count == 1


def test_fixture_mid_fcst_call_raw_returns_full_envelope() -> None:
    adapter, dataset = _build_real_estate_adapter("success_mid_fcst.json", "mid_fcst")
    expected = load_json_fixture("success_mid_fcst.json")

    payload = adapter.call_raw(dataset, "getMidFcst", {"stnId": "108", "tmFc": "2026052206"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


def test_fixture_mid_land_fcst_parses() -> None:
    adapter, dataset = _build_real_estate_adapter("success_mid_land_fcst.json", "mid_land_fcst")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 1
    assert batch.items[0]["regId"] == "11B00000"
    assert "rnSt4Am" in batch.items[0]
    assert "wf4Am" in batch.items[0]
    assert batch.total_count == 1


def test_fixture_mid_land_fcst_call_raw_returns_full_envelope() -> None:
    adapter, dataset = _build_real_estate_adapter("success_mid_land_fcst.json", "mid_land_fcst")
    expected = load_json_fixture("success_mid_land_fcst.json")

    payload = adapter.call_raw(
        dataset, "getMidLandFcst", {"regId": "11B00000", "tmFc": "2026052206"}
    )

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


def test_fixture_mid_ta_parses() -> None:
    adapter, dataset = _build_real_estate_adapter("success_mid_ta.json", "mid_ta")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 1
    assert batch.items[0]["regId"] == "11D20501"
    assert "taMin4" in batch.items[0]
    assert "taMax4" in batch.items[0]
    assert batch.total_count == 1


def test_fixture_mid_ta_call_raw_returns_full_envelope() -> None:
    adapter, dataset = _build_real_estate_adapter("success_mid_ta.json", "mid_ta")
    expected = load_json_fixture("success_mid_ta.json")

    payload = adapter.call_raw(dataset, "getMidTa", {"regId": "11D20501", "tmFc": "2026052206"})

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


def test_fixture_mid_sea_fcst_parses() -> None:
    adapter, dataset = _build_real_estate_adapter("success_mid_sea_fcst.json", "mid_sea_fcst")

    batch = adapter.query_records(dataset, Query())

    assert len(batch.items) == 1
    assert batch.items[0]["regId"] == "12A20000"
    assert "wf4Am" in batch.items[0]
    assert "wh4AAm" in batch.items[0]
    assert batch.total_count == 1


def test_fixture_mid_sea_fcst_call_raw_returns_full_envelope() -> None:
    adapter, dataset = _build_real_estate_adapter("success_mid_sea_fcst.json", "mid_sea_fcst")
    expected = load_json_fixture("success_mid_sea_fcst.json")

    payload = adapter.call_raw(
        dataset, "getMidSeaFcst", {"regId": "12A20000", "tmFc": "2026052206"}
    )

    assert payload == expected
    payload_dict = cast(dict[str, object], payload)
    response = payload_dict["response"]
    assert isinstance(response, dict)
    assert "header" in response
    assert "body" in response


# test fixture bond price parses Describes the scenario verified by the test.
def test_fixture_bond_price_parses() -> None:
    """bond_price_info fixturenormalized to standard envelope (#163)."""
    adapter, dataset = _build_real_estate_adapter("success_bond_price.json", "bond_price")

    batch = adapter.query_records(dataset, Query(filters={"basDt": "20260102"}))

    assert len(batch.items) == 2
    assert batch.items[0]["itmsNm"] == "국고채권 3년"
    assert "clpr" in batch.items[0]
    assert "yply" in batch.items[0]
    assert batch.total_count == 2


# test fixture bond price call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_bond_price_call_raw_returns_full_envelope() -> None:
    """test_fixture_bond_price_call_raw_returns_full_envelope

    Validates the scenario described by the test name.
    """
    adapter, dataset = _build_real_estate_adapter("success_bond_price.json", "bond_price")
    expected = load_json_fixture("success_bond_price.json")

    payload = adapter.call_raw(dataset, "getBondPriceInfo", {"basDt": "20260102"})

    assert payload == expected


# test fixture sports facility parses Describes the scenario verified by the test.
def test_fixture_sports_facility_parses() -> None:
    """national_sports_facilities fixturenormalized to standard envelope (#166)."""
    adapter, dataset = _build_real_estate_adapter("success_sports_facility.json", "sports_facility")

    batch = adapter.query_records(dataset, Query(filters={"sidoNm": "경기도"}))

    assert len(batch.items) == 2
    assert batch.items[0]["faciNm"] == "부천종합운동장"
    assert "indutyNm" in batch.items[0]
    assert batch.total_count == 2


# test fixture sports facility call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_sports_facility_call_raw_returns_full_envelope() -> None:
    """test_fixture_sports_facility_call_raw_returns_full_envelope

    Validates the scenario described by the test name.
    """
    adapter, dataset = _build_real_estate_adapter("success_sports_facility.json", "sports_facility")
    expected = load_json_fixture("success_sports_facility.json")

    payload = adapter.call_raw(dataset, "TODZ_API_SFMS_FACI", {"sidoNm": "경기도"})

    assert payload == expected


# test fixture culture facility parses Describes the scenario verified by the test.
def test_fixture_culture_facility_parses() -> None:
    """culture_facilities_search fixturenormalized to standard envelope (#167)."""
    adapter, dataset = _build_real_estate_adapter(
        "success_culture_facility.json", "culture_facility"
    )

    batch = adapter.query_records(dataset, Query(filters={"faciCl": "공연장"}))

    assert len(batch.items) == 2
    assert batch.items[0]["faciNm"] == "세종문화회관"
    assert "la" in batch.items[0]
    assert batch.total_count == 2


# test fixture dataset call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_new_datasets_call_raw_return_full_envelope() -> None:
    """test_fixture_new_datasets_call_raw_return_full_envelope

    Validates the scenario described by the test name.
    """
    cases = [
        ("success_culture_facility.json", "culture_facility", "cultureartspaces/performingplace"),
    ]
    for fixture, key, operation in cases:
        adapter, dataset = _build_real_estate_adapter(fixture, key)
        expected = load_json_fixture(fixture)
        payload = adapter.call_raw(dataset, operation, {})
        assert payload == expected


# test fixture airkorea station realtime parses Describes the scenario verified by the test.
def test_fixture_airkorea_station_realtime_parses() -> None:
    """AirKorea station real-time fixturenormalized to standard envelope (#224)."""
    adapter, dataset = _build_real_estate_adapter(
        "success_airkorea_station_realtime.json", "airkorea_station_realtime"
    )

    batch = adapter.query_records(dataset, Query(filters={"stationName": "강남구"}))

    assert len(batch.items) == 2
    assert batch.items[0]["pm10Value"] == "42"
    assert batch.items[0]["khaiValue"] == "72"
    assert batch.total_count == 2


# test fixture airkorea forecast parses Describes the scenario verified by the test.
def test_fixture_airkorea_forecast_parses() -> None:
    """AirKorea forecast notice fixturenormalized to standard envelope (#224)."""
    adapter, dataset = _build_real_estate_adapter(
        "success_airkorea_forecast.json", "airkorea_forecast"
    )

    batch = adapter.query_records(dataset, Query(filters={"informCode": "PM10"}))

    assert len(batch.items) == 2
    assert "informGrade" in batch.items[0]
    assert batch.total_count == 2


# test fixture asos daily parses Describes the scenario verified by the test.
def test_fixture_asos_daily_parses() -> None:
    """synoptic_meteorology_daily fixturenormalized to standard envelope (#217)."""
    adapter, dataset = _build_real_estate_adapter("success_asos_daily.json", "asos_daily")

    batch = adapter.query_records(
        dataset,
        Query(filters={"stnIds": "108", "startDt": "20260331", "endDt": "20260401"}),
    )

    assert len(batch.items) == 2
    assert batch.items[0]["stnNm"] == "서울"
    assert batch.items[0]["avgTa"] == "11.2"
    assert "sumRn" in batch.items[0]
    assert batch.total_count == 2


# test fixture asos hourly parses Describes the scenario verified by the test.
def test_fixture_asos_hourly_parses() -> None:
    """synoptic_meteorology_hourly fixturenormalized to standard envelope (#217)."""
    adapter, dataset = _build_real_estate_adapter("success_asos_hourly.json", "asos_hourly")

    batch = adapter.query_records(
        dataset,
        Query(filters={"stnIds": "108", "startDt": "20260401", "endDt": "20260401"}),
    )

    assert len(batch.items) == 2
    assert batch.items[0]["tm"] == "2026-04-01 09:00"
    assert batch.total_count == 2


# test fixture asos call raw returns full envelope Describes the scenario verified by the test.
def test_fixture_asos_call_raw_returns_full_envelope() -> None:
    """ASOS datasetof call_rawreturns full envelope (#217)."""
    for key, fixture in (
        ("asos_daily", "success_asos_daily.json"),
        ("asos_hourly", "success_asos_hourly.json"),
    ):
        adapter, dataset = _build_real_estate_adapter(fixture, key)
        expected = load_json_fixture(fixture)
        payload = adapter.call_raw(
            dataset,
            "getWthrDataList",
            {"stnIds": "108", "startDt": "20260331", "endDt": "20260401"},
        )
        assert payload == expected
