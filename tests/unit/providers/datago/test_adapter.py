"""Test module.

This file defines test scenarios and helper objects for the
tests/unit/providers/datago/test_adapter.py path. It validates core flows,
exceptions, and edge conditions to prevent regressions and verify the
public contract."""

from __future__ import annotations

import json
import logging
from types import MappingProxyType
from typing import Protocol, cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.capability import Operation, PaginationMode
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.representation import Representation
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    InvalidRequestError,
    RateLimitError,
    ServiceUnavailableError,
    TransportError,
)
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.transport.http import HttpTransport

REAL_ESTATE_DATASET_KEYS = [
    "apt_rent",
    "offi_trade",
    "offi_rent",
    "rh_trade",
    "rh_rent",
    "sh_trade",
    "sh_rent",
]


class FakeResponse:
    """Tests for FakeResponse.

    This class groups related test cases and helpers for FakeResponse.
    """

    def __init__(self, payload: object, content_type: str = "application/json") -> None:
        """
        Initialize with payload.

        Args:
            payload (object): Input parameter.
            content_type (str): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        self.headers: dict[str, str] = {"content-type": content_type}
        self.text: str = json.dumps(payload)
        self.content: bytes = self.text.encode()


class FakeTransport:
    """Tests for FakeTransport.

    This class groups related test cases and helpers for FakeTransport.
    """

    def __init__(self, responses: list[FakeResponse]) -> None:
        """
        Initialize with payload.

        Args:
            responses (list[FakeResponse]): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        self._responses: list[FakeResponse] = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        """
        Execute a mock HTTP request.

        Args:
            method (str): Input parameter.
            url (str): Input parameter.
            **kwargs (object): Input parameter.

        Returns:
            FakeResponse: Result.

        Raises:
            Exceptions propagated."""
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._responses.pop(0)


def _success_payload(
    *,
    items: object,
    total_count: object,
    num_of_rows: object,
    page_no: object,
) -> dict[str, object]:
    """
    Build success response payload.

    Args:
        items (object): Input parameter.
        total_count (object): Input parameter.
        num_of_rows (object): Input parameter.
        page_no (object): Input parameter.

    Returns:
        dict[str, object]: Result.

    Raises:
        Exceptions propagated."""
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "items": {"item": items},
                "totalCount": total_count,
                "numOfRows": num_of_rows,
                "pageNo": page_no,
            },
        }
    }


def _error_payload(code: str, msg: str = "ERROR") -> dict[str, object]:
    """
    Build error response payload.

    Args:
        code (str): Input parameter.
        msg (str): Input parameter.

    Returns:
        dict[str, object]: Result.

    Raises:
        Exceptions propagated."""
    return {
        "response": {
            "header": {"resultCode": code, "resultMsg": msg},
            "body": {"items": {"item": []}, "totalCount": 0, "numOfRows": 10, "pageNo": 1},
        }
    }


def _build_adapter_with_transport(
    responses: list[FakeResponse],
) -> tuple[DataGoAdapter, DatasetRef, FakeTransport]:
    """
    Build adapter with transport.

    Args:
        responses (list[FakeResponse]): Input parameter.

    Returns:
        tuple[DataGoAdapter, DatasetRef, FakeTransport]: Result.

    Raises:
        Exceptions propagated."""
    transport = FakeTransport(responses)
    config = KPubDataConfig(provider_keys={"datago": "test-key"})
    adapter = DataGoAdapter(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset("metro_fare")
    return adapter, dataset, transport


class AdapterFactory(Protocol):
    """Tests for AdapterFactory.

    This class groups related test cases and helpers for AdapterFactory.
    """

    def __call__(
        self,
        fixture_names: list[str],
        content_type: str = "application/json",
    ) -> tuple[DataGoAdapter, DatasetRef, object]: ...


class TestDataGoAdapterDiscovery:
    """Tests for TestDataGoAdapterDiscovery.

    This class groups related test cases and helpers for TestDataGoAdapterDiscovery.
    """

    # test default catalogue loads Describes the scenario verified by the test.
    def test_default_catalogue_loads(self) -> None:
        """
        Verify default catalogue loads.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        datasets = adapter.list_datasets()
        assert datasets
        assert all(isinstance(dataset, DatasetRef) for dataset in datasets)

    # test list datasets returns copy Describes the scenario verified by the test.
    def test_list_datasets_returns_copy(self) -> None:
        """
        Verify list_datasets returns copy.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        first = adapter.list_datasets()
        second = adapter.list_datasets()

        assert first == second
        assert first is not second

    # test list datasets all datago provider Describes the scenario verified by the test.
    def test_list_datasets_all_datago_provider(self) -> None:
        """
        Verify all have datago provider.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        datasets = adapter.list_datasets()
        assert all(dataset.provider == "datago" for dataset in datasets)

    # test list datasets ids prefixed Describes the scenario verified by the test.
    def test_list_datasets_ids_prefixed(self) -> None:
        """
        Verify IDs prefixed.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        datasets = adapter.list_datasets()
        assert all(dataset.id.startswith("datago.") for dataset in datasets)

    # test get dataset found Describes the scenario verified by the test.
    def test_get_dataset_found(self) -> None:
        """
        Verify get_dataset returns dataset.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        dataset = adapter.get_dataset("metro_fare")
        assert dataset.id == "datago.metro_fare"
        assert dataset.dataset_key == "metro_fare"

    # test get dataset not found Describes the scenario verified by the test.
    def test_get_dataset_not_found(self) -> None:
        """
        Verify get_dataset raises.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        with pytest.raises(DatasetNotFoundError):
            _ = adapter.get_dataset("does_not_exist")

    # test constructor override catalogue Describes the scenario verified by the test.
    def test_constructor_override_catalogue(self) -> None:
        """
        Verify constructor overrides catalogue.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        custom_dataset = DatasetRef(
            id="datago.custom",
            provider="datago",
            dataset_key="custom",
            name="Custom Dataset",
            representation=Representation.API_JSON,
            operations=frozenset(),
            raw_metadata=MappingProxyType({"base_url": "https://example.test"}),
        )
        adapter = DataGoAdapter(catalogue=[custom_dataset])

        assert adapter.list_datasets() == [custom_dataset]

    # test search datasets match Describes the scenario verified by the test.
    def test_search_datasets_match(self) -> None:
        """
        Verify search_datasets matches.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        results = adapter.search_datasets("fare")
        assert results
        assert any(dataset.dataset_key == "metro_fare" for dataset in results)

    # test search datasets no match Describes the scenario verified by the test.
    def test_search_datasets_no_match(self) -> None:
        """
        Verify search_datasets no match.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        assert adapter.search_datasets("zzzzzz-not-a-dataset") == []

    # test no api key required for discovery Describes the scenario verified by the test.
    def test_no_api_key_required_for_discovery(self) -> None:
        """
        Verify no API key needed.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        datasets = adapter.list_datasets()
        assert datasets

        dataset = adapter.get_dataset("metro_fare")
        assert dataset.id == "datago.metro_fare"


class TestDataGoAdapterRealEstateDatasets:
    """Tests for TestDataGoAdapterRealEstateDatasets.

    This class groups related test cases and helpers for TestDataGoAdapterRealEstateDatasets.
    """

    # test catalogue contains all real estate datasets Describes the scenario verified by the test.
    def test_catalogue_contains_all_real_estate_datasets(self) -> None:
        """
        Verify catalogue complete.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        dataset_keys = {dataset.dataset_key for dataset in adapter.list_datasets()}

        assert set(REAL_ESTATE_DATASET_KEYS).issubset(dataset_keys)

    # test get dataset for each real estate key Describes the scenario verified by the test.
    @pytest.mark.parametrize("dataset_key", REAL_ESTATE_DATASET_KEYS)
    def test_get_dataset_for_each_real_estate_key(self, dataset_key: str) -> None:
        """
        Verify get each dataset.

        Args:
            dataset_key (str): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        dataset = adapter.get_dataset(dataset_key)

        assert dataset.id == f"datago.{dataset_key}"
        assert dataset.dataset_key == dataset_key

    # test real estate datasets have correct operations Describes the scenario verified by the test.
    @pytest.mark.parametrize("dataset_key", REAL_ESTATE_DATASET_KEYS)
    def test_real_estate_datasets_have_correct_operations(self, dataset_key: str) -> None:
        """
        Verify operations correct.

        Args:
            dataset_key (str): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        dataset = adapter.get_dataset(dataset_key)

        assert Operation.LIST in dataset.operations
        assert Operation.RAW in dataset.operations

    # test real estate datasets have offset pagination Describes the scenario verified by the test.
    @pytest.mark.parametrize("dataset_key", REAL_ESTATE_DATASET_KEYS)
    def test_real_estate_datasets_have_offset_pagination(self, dataset_key: str) -> None:
        """
        Verify offset pagination.

        Args:
            dataset_key (str): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        dataset = adapter.get_dataset(dataset_key)

        assert dataset.query_support is not None
        assert dataset.query_support.pagination is PaginationMode.OFFSET
        assert dataset.query_support.max_page_size == 1000

    # test search datasets finds real estate Describes the scenario verified by the test.
    def test_search_datasets_finds_real_estate(self) -> None:
        """
        Verify finds real estate.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        results = adapter.search_datasets("실거래")
        result_keys = {dataset.dataset_key for dataset in results}

        assert set(REAL_ESTATE_DATASET_KEYS).issubset(result_keys)


class TestDataGoAdapterQueryRecords:
    """Tests for TestDataGoAdapterQueryRecords.

    This class groups related test cases and helpers for TestDataGoAdapterQueryRecords.
    """

    # test query records single page Describes the scenario verified by the test.
    def test_query_records_single_page(self) -> None:
        """
        Verify single page.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(
            items=[{"id": 1}, {"id": 2}, {"id": 3}],
            total_count=3,
            num_of_rows=100,
            page_no=1,
        )
        adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

        batch = adapter.query_records(dataset, Query())

        assert len(batch.items) == 3
        assert batch.total_count == 3
        assert batch.next_page is None
        assert isinstance(batch.raw, dict)
        assert len(transport.calls) == 1

    # test query records sets next page when more pages exist Describes the scenario verified by the test.
    def test_query_records_sets_next_page_when_more_pages_exist(self) -> None:
        """
        Verify next_page when more.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(
            items=[{"id": 1}, {"id": 2}],
            total_count=5,
            num_of_rows=2,
            page_no=1,
        )
        adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

        batch = adapter.query_records(dataset, Query(page_size=2))

        assert [item["id"] for item in batch.items] == [1, 2]
        assert batch.total_count == 5
        assert batch.next_page == 2
        assert len(transport.calls) == 1

    # test query records sets next page without total count for full page Describes the scenario verified by the test.
    def test_query_records_sets_next_page_without_total_count_for_full_page(self) -> None:
        """
        Verify next_page full page.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(
            items=[{"id": 1}, {"id": 2}], total_count=None, num_of_rows=2, page_no=1
        )
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

        batch = adapter.query_records(dataset, Query(page_size=2))

        assert batch.total_count is None
        assert batch.next_page == 2

    # test query records raw is single payload dict Describes the scenario verified by the test.
    def test_query_records_raw_is_single_payload_dict(self) -> None:
        """
        Verify raw is dict.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(items=[{"id": 1}], total_count=1, num_of_rows=1, page_no=1)
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

        batch = adapter.query_records(dataset, Query(page_size=1))

        assert batch.raw == payload

    # test query records single item dict Describes the scenario verified by the test.
    def test_query_records_single_item_dict(self) -> None:
        """
        Verify single item.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(items={"id": 1}, total_count=1, num_of_rows=100, page_no=1)
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

        batch = adapter.query_records(dataset, Query())

        assert batch.items == [{"id": 1}]
        assert batch.total_count == 1

    # test query records empty items Describes the scenario verified by the test.
    def test_query_records_empty_items(self) -> None:
        """
        Verify empty items.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(items=None, total_count=0, num_of_rows=100, page_no=1)
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

        batch = adapter.query_records(dataset, Query())

        assert batch.items == []
        assert batch.total_count is None

    # test query records empty items logs debug Describes the scenario verified by the test.
    def test_query_records_empty_items_logs_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        Verify empty logged.

        Args:
            caplog (pytest.LogCaptureFixture): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(items=None, total_count=0, num_of_rows=100, page_no=1)
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

        caplog.set_level(logging.DEBUG, logger="kpubdata.provider.datago")
        _ = adapter.query_records(dataset, Query())

        record = next(
            record
            for record in caplog.records
            if record.getMessage() == "Datago envelope: zero items"
        )
        assert record.__dict__["dataset_id"] == dataset.id
        assert record.__dict__["page"] == 1
        assert record.__dict__["page_size"] == 100
        assert record.__dict__["total_count"] == 0

    # test query records string numerics Describes the scenario verified by the test.
    def test_query_records_string_numerics(self) -> None:
        """
        Verify string numerics.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(
            items=[{"id": 1}], total_count="1", num_of_rows="100", page_no="1"
        )
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

        batch = adapter.query_records(dataset, Query(page=1, page_size=100))

        assert batch.total_count == 1
        assert len(batch.items) == 1

    # test query records auth error 30 Describes the scenario verified by the test.
    def test_query_records_auth_error_30(self) -> None:
        """
        Verify auth error.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(_error_payload("30"))])

        with pytest.raises(AuthError):
            _ = adapter.query_records(dataset, Query())

    # test query records rate limit 22 Describes the scenario verified by the test.
    def test_query_records_rate_limit_22(self) -> None:
        """
        Verify rate limit.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(_error_payload("22"))])

        with pytest.raises(RateLimitError) as excinfo:
            _ = adapter.query_records(dataset, Query())

        assert excinfo.value.retryable is False

    # test query records invalid request 10 Describes the scenario verified by the test.
    def test_query_records_invalid_request_10(self) -> None:
        """
        Verify invalid request.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(_error_payload("10"))])

        with pytest.raises(InvalidRequestError):
            _ = adapter.query_records(dataset, Query())

    # test query records dataset not found 12 Describes the scenario verified by the test.
    def test_query_records_dataset_not_found_12(self) -> None:
        """
        Verify dataset not found.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(_error_payload("12"))])

        with pytest.raises(DatasetNotFoundError):
            _ = adapter.query_records(dataset, Query())

    # test query records service unavailable 01 Describes the scenario verified by the test.
    def test_query_records_service_unavailable_01(self) -> None:
        """
        Verify service unavailable.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(_error_payload("01"))])

        with pytest.raises(ServiceUnavailableError):
            _ = adapter.query_records(dataset, Query())

    # test query records http 403 wraps with activation hint Describes the scenario verified by the test.
    def test_query_records_http_403_wraps_with_activation_hint(self) -> None:
        """
        Verify HTTP 403 hint.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""

        class ForbiddenTransport:
            """Tests for ForbiddenTransport.

            This class groups related test cases and helpers for ForbiddenTransport.
            """

            def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
                """
                Execute a mock HTTP request.

                Args:
                    method (str): Input parameter.
                    url (str): Input parameter.
                    **kwargs (object): Input parameter.

                Returns:
                    FakeResponse: Result.

                Raises:
                    Exceptions propagated."""
                del method, url, kwargs
                # Verifies test behavior (see test name for details).
                # Verifies test behavior (see test name for details).
                # path always ``from None`` is.
                raise TransportError(
                    "HTTP status error 403 for GET https://apis.data.go.kr/test",
                    provider="datago",
                    status_code=403,
                ) from None

        adapter = DataGoAdapter(
            config=KPubDataConfig(provider_keys={"datago": "test-key"}),
            transport=cast(HttpTransport, cast(object, ForbiddenTransport())),
        )
        dataset = adapter.get_dataset("metro_fare")

        with pytest.raises(AuthError) as excinfo:
            _ = adapter.query_records(dataset, Query())

        assert "활용신청" in str(excinfo.value)
        assert "https://www.data.go.kr" in str(excinfo.value)
        assert excinfo.value.status_code == 403
        assert excinfo.value.dataset_id == dataset.id

    # test query records accepts three digit success code 000 Describes the scenario verified by the test.
    def test_query_records_accepts_three_digit_success_code_000(self) -> None:
        """
        test query records accepts three digit success code 000 Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = {
            "response": {
                "header": {"resultCode": "000", "resultMsg": "OK"},
                "body": {
                    "items": {"item": [{"dealAmount": "82,500", "aptNm": "래미안"}]},
                    "totalCount": 1,
                    "numOfRows": 100,
                    "pageNo": 1,
                },
            }
        }
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

        batch = adapter.query_records(dataset, Query(page=1, page_size=100))

        assert len(batch.items) == 1
        assert batch.items[0]["aptNm"] == "래미안"

    # test query records accepts two digit success code 00 Describes the scenario verified by the test.
    def test_query_records_accepts_two_digit_success_code_00(self) -> None:
        """
        test query records accepts two digit success code 00 Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(items=[{"id": 1}], total_count=1, num_of_rows=100, page_no=1)
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

        batch = adapter.query_records(dataset, Query(page=1, page_size=100))

        assert len(batch.items) == 1

    # test query records filters passed Describes the scenario verified by the test.
    def test_query_records_filters_passed(self) -> None:
        """
        test query records filters passed Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(items=[{"id": 1}], total_count=1, num_of_rows=100, page_no=1)
        adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

        _ = adapter.query_records(dataset, Query(filters={"stationName": "Seoul", "page": 1}))

        params = transport.calls[0]["params"]
        assert isinstance(params, dict)
        assert params["stationName"] == "Seoul"
        assert params["page"] == "1"

    # test query records reserved keys protected Describes the scenario verified by the test.
    def test_query_records_reserved_keys_protected(self) -> None:
        """
        test query records reserved keys protected Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(items=[{"id": 1}], total_count=1, num_of_rows=100, page_no=1)
        adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

        _ = adapter.query_records(
            dataset,
            Query(
                filters={
                    "serviceKey": "bad-key",
                    "pageNo": "999",
                    "numOfRows": "999",
                    "x": "ok",
                }
            ),
        )

        params = transport.calls[0]["params"]
        assert isinstance(params, dict)
        assert params["serviceKey"] == "test-key"
        assert params["pageNo"] == "1"
        assert params["numOfRows"] == "100"
        assert params["x"] == "ok"

    @pytest.mark.parametrize(
        ("dataset_key", "expected_date_cd"),
        [("asos_daily", "DAY"), ("asos_hourly", "HR")],
    )
    def test_query_records_applies_unoverrideable_fixed_query_params(
        self, dataset_key: str, expected_date_cd: str
    ) -> None:
        """Validates the scenario described by the test name."""
        payload = _success_payload(items=[{"id": 1}], total_count=1, num_of_rows=100, page_no=1)
        adapter, _, transport = _build_adapter_with_transport([FakeResponse(payload)])
        dataset = adapter.get_dataset(dataset_key)

        _ = adapter.query_records(
            dataset,
            Query(filters={"dataCd": "wrong", "dateCd": "wrong", "stnIds": "108"}),
        )

        params = transport.calls[0]["params"]
        assert isinstance(params, dict)
        assert params["dataCd"] == "ASOS"
        assert params["dateCd"] == expected_date_cd

    def test_query_records_does_not_add_fixed_query_params_to_other_dataset(self) -> None:
        """test_query_records_does_not_add_fixed_query_params_to_other_dataset

        Validates the scenario described by the test name.
        """
        payload = _success_payload(items=[{"id": 1}], total_count=1, num_of_rows=100, page_no=1)
        adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

        _ = adapter.query_records(dataset, Query())

        params = transport.calls[0]["params"]
        assert isinstance(params, dict)
        assert "dataCd" not in params
        assert "dateCd" not in params


class TestDataGoAdapterCallRaw:
    """Tests for TestDataGoAdapterCallRaw.

    This class groups related test cases and helpers for TestDataGoAdapterCallRaw.
    """

    # test call raw returns full payload Describes the scenario verified by the test.
    def test_call_raw_returns_full_payload(self) -> None:
        """
        test call raw returns full payload Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(items=[{"id": 1}], total_count=1, num_of_rows=1, page_no=1)
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

        result = adapter.call_raw(dataset, "getVilageFcst", {"base_date": "20250101"})

        assert result == payload

    # test call raw custom operation Describes the scenario verified by the test.
    def test_call_raw_custom_operation(self) -> None:
        """
        test call raw custom operation Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        payload = _success_payload(items=[{"id": 1}], total_count=1, num_of_rows=1, page_no=1)
        adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

        _ = adapter.call_raw(dataset, "customOperation", {"foo": "bar"})

        url = transport.calls[0]["url"]
        assert isinstance(url, str)
        assert url.endswith("/customOperation")

    # test call raw error mapped Describes the scenario verified by the test.
    def test_call_raw_error_mapped(self) -> None:
        """
        test call raw error mapped Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(_error_payload("30"))])

        with pytest.raises(AuthError):
            _ = adapter.call_raw(dataset, "getVilageFcst", {})


class TestDataGoAdapterCatalogueOperations:
    """Tests for TestDataGoAdapterCatalogueOperations.

    This class groups related test cases and helpers for TestDataGoAdapterCatalogueOperations.
    """

    # test default catalogue has operations Describes the scenario verified by the test.
    def test_default_catalogue_has_operations(self) -> None:
        """
        test default catalogue has operations Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        datasets = [d for d in adapter.list_datasets() if not d.raw_metadata.get("generic")]
        assert datasets
        for dataset in datasets:
            assert Operation.LIST in dataset.operations
            assert Operation.RAW in dataset.operations

    # test default catalogue has query support Describes the scenario verified by the test.
    def test_default_catalogue_has_query_support(self) -> None:
        """
        test default catalogue has query support Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()

        datasets = [d for d in adapter.list_datasets() if not d.raw_metadata.get("generic")]
        assert datasets
        for dataset in datasets:
            assert dataset.query_support is not None
            assert dataset.query_support.pagination is PaginationMode.OFFSET
            assert dataset.query_support.max_page_size == 1000

    def test_air_quality_declares_required_request_parameter(self) -> None:
        """test_air_quality_declares_required_request_parameter

        Validates the scenario described by the test name.
        """
        adapter = DataGoAdapter()

        dataset = adapter.get_dataset("air_quality")
        params = dataset.raw_metadata.get("request_parameters")
        assert isinstance(params, list)
        by_name = {p["name"]: p for p in params if isinstance(p, dict)}
        assert "sidoName" in by_name
        assert by_name["sidoName"]["required"] is True
        assert by_name["sidoName"]["example"] == "서울"
        # secret params not added here.
        assert "serviceKey" not in by_name

    def test_airkorea_station_realtime_declares_official_required_parameters(self) -> None:
        """test_airkorea_station_realtime_declares_official_required_parameters

        Validates the scenario described by the test name.
        """
        adapter = DataGoAdapter()

        dataset = adapter.get_dataset("airkorea_station_realtime")
        params = dataset.raw_metadata.get("request_parameters")
        assert isinstance(params, list)
        by_name = {param["name"]: param for param in params if isinstance(param, dict)}
        assert by_name["stationName"]["required"] is True
        assert by_name["dataTerm"] == {
            "name": "dataTerm",
            "required": True,
            "description": "요청 데이터기간 (DAILY, MONTH, 3MONTH)",
            "example": "DAILY",
        }
        assert "ver" not in by_name
        assert "returnType" not in by_name

    def test_air_quality_declares_application_requirement(self) -> None:
        """test_air_quality_declares_application_requirement

        Validates the scenario described by the test name.
        """
        adapter = DataGoAdapter()

        dataset = adapter.get_dataset("air_quality")
        application = dataset.raw_metadata.get("application")
        assert isinstance(application, dict)
        assert application["required"] is True
        assert application["url"] == "https://www.data.go.kr/data/15073861/openapi.do"

    def test_high_confidence_catalogue_metadata_is_preserved(self) -> None:
        """test_high_confidence_catalogue_metadata_is_preserved

        Validates the scenario described by the test name.
        """
        adapter = DataGoAdapter()

        # village_fcst was retired from the catalogue on main; ultra_srt_ncst is
        # the surviving dataset on that endpoint.
        for key in ("ultra_srt_ncst",):
            assert adapter.get_dataset(key).raw_metadata["base_url"] == (
                "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
            )
        for key in ("air_quality", "airkorea_station_realtime", "airkorea_forecast"):
            assert adapter.get_dataset(key).raw_metadata["base_url"] == (
                "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc"
            )

        required_names = {
            "ultra_srt_ncst": ["base_date", "base_time", "nx", "ny"],
            "mid_fcst": ["stnId", "tmFc"],
            "asos_daily": ["startDt", "endDt", "stnIds"],
            "asos_hourly": ["startDt", "startHh", "endDt", "endHh", "stnIds"],
        }
        for key, names in required_names.items():
            params = adapter.get_dataset(key).raw_metadata["request_parameters"]
            assert isinstance(params, list)
            assert {param["name"] for param in params} == set(names)
            assert all(param["required"] is True for param in params)

        assert adapter.get_dataset("airkorea_forecast").raw_metadata["request_parameters"] == []
        hourly = adapter.get_dataset("asos_hourly")
        assert hourly.source_url == (
            "https://www.data.go.kr/tcs/dss/selectApiDataDetailView.do?publicDataPk=15057210"
        )
        application = hourly.raw_metadata["application"]
        assert application == {
            "required": True,
            "url": "https://www.data.go.kr/tcs/dss/selectApiDataDetailView.do?publicDataPk=15057210",
        }

    def test_required_query_filters_match_the_documented_request_parameters(self) -> None:
        """test_required_query_filters_match_the_documented_request_parameters

        Validates the scenario described by the test name.
        """
        import json
        from pathlib import Path

        catalogue_path = (
            Path(__file__).parents[4]
            / "src"
            / "kpubdata"
            / "providers"
            / "datago"
            / "catalogue.json"
        )
        catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))

        desynced = {}
        for entry in catalogue:
            params = entry.get("request_parameters")
            if params is None:
                continue
            documented = sorted(p["name"] for p in params if p.get("required"))
            declared = sorted(entry.get("required_query_filters") or [])
            if documented != declared:
                desynced[entry["dataset_key"]] = (declared, documented)

        assert not desynced, f"required_query_filters out of sync: {desynced}"


class TestDataGoAdapterXml:
    """Tests for TestDataGoAdapterXml.

    This class groups related test cases and helpers for TestDataGoAdapterXml.
    """

    # test query records xml multi item Describes the scenario verified by the test.
    def test_query_records_xml_multi_item(self, configured_adapter: AdapterFactory) -> None:
        """
        test query records xml multi item Validates the scenario described by the test name.

        Args:
            configured_adapter (AdapterFactory): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, dataset, _ = configured_adapter(["success_xml.xml"], content_type="text/xml")
        batch = adapter.query_records(dataset, Query())

        assert len(batch.items) == 2
        assert batch.items[0]["stationName"] == "종로구"
        assert batch.items[1]["stationName"] == "강남구"
        assert batch.total_count == 2

    # test query records xml single item Describes the scenario verified by the test.
    def test_query_records_xml_single_item(self, configured_adapter: AdapterFactory) -> None:
        """
        test query records xml single item Validates the scenario described by the test name.

        Args:
            configured_adapter (AdapterFactory): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, dataset, _ = configured_adapter(
            ["success_xml_single_item.xml"], content_type="text/xml"
        )
        batch = adapter.query_records(dataset, Query())

        assert len(batch.items) == 1
        assert batch.items[0]["stationName"] == "종로구"
        assert batch.total_count == 1

    # test call raw xml response Describes the scenario verified by the test.
    def test_call_raw_xml_response(self, configured_adapter: AdapterFactory) -> None:
        """
        test call raw xml response Validates the scenario described by the test name.

        Args:
            configured_adapter (AdapterFactory): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, dataset, _ = configured_adapter(["success_xml.xml"], content_type="text/xml")
        result = adapter.call_raw(dataset, "getVilageFcst", {})

        assert isinstance(result, dict)
        assert result["response"]["header"]["resultCode"] == "00"

    # test xml error maps to exception Describes the scenario verified by the test.
    def test_xml_error_maps_to_exception(self, configured_adapter: AdapterFactory) -> None:
        """
        test xml error maps to exception Validates the scenario described by the test name.

        Args:
            configured_adapter (AdapterFactory): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter, dataset, _ = configured_adapter(["error_xml_auth_30.xml"], content_type="text/xml")
        with pytest.raises(AuthError):
            _ = adapter.query_records(dataset, Query())


class TestDataGoAdapterGetSchema:
    """Tests for TestDataGoAdapterGetSchema.

    This class groups related test cases and helpers for TestDataGoAdapterGetSchema.
    """

    # test get schema returns none without fields Describes the scenario verified by the test.
    def test_get_schema_returns_none_without_fields(self) -> None:
        """
        test get schema returns none without fields Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        adapter = DataGoAdapter()
        dataset = adapter.get_dataset("metro_fare")
        schema = adapter.get_schema(dataset)
        assert schema is None

    # test get schema returns descriptor with fields Describes the scenario verified by the test.
    def test_get_schema_returns_descriptor_with_fields(self) -> None:
        """
        test get schema returns descriptor with fields Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        custom_dataset = DatasetRef(
            id="datago.test_schema",
            provider="datago",
            dataset_key="test_schema",
            name="Test Schema Dataset",
            representation=Representation.API_JSON,
            operations=frozenset(),
            raw_metadata=MappingProxyType(
                {
                    "base_url": "https://example.test",
                    "fields": [
                        {
                            "name": "stationName",
                            "title": "측정소명",
                            "type": "string",
                            "description": "Name of monitoring station",
                        },
                        {
                            "name": "pm10Value",
                            "title": "미세먼지 농도",
                            "type": "string",
                            "description": "PM10 concentration",
                            "nullable": True,
                        },
                    ],
                }
            ),
        )
        adapter = DataGoAdapter(catalogue=[custom_dataset])
        schema = adapter.get_schema(custom_dataset)

        assert schema is not None
        assert schema.dataset is custom_dataset
        assert len(schema.fields) == 2
        assert schema.fields[0].name == "stationName"
        assert schema.fields[0].title == "측정소명"
        assert schema.fields[0].type == "string"
        assert schema.fields[0].description == "Name of monitoring station"
        assert schema.fields[0].nullable is None
        assert schema.fields[1].name == "pm10Value"
        assert schema.fields[1].nullable is True
        assert schema.raw["source"] == "catalogue"

    # test get schema skips invalid field entries Describes the scenario verified by the test.
    def test_get_schema_skips_invalid_field_entries(self) -> None:
        """
        test get schema skips invalid field entries Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        custom_dataset = DatasetRef(
            id="datago.test_bad_fields",
            provider="datago",
            dataset_key="test_bad_fields",
            name="Test Bad Fields",
            representation=Representation.API_JSON,
            operations=frozenset(),
            raw_metadata=MappingProxyType(
                {
                    "base_url": "https://example.test",
                    "fields": [
                        {"name": "valid_field", "type": "string"},
                        "not_a_dict",
                        {"title": "missing_name"},
                        {"name": "", "type": "string"},
                    ],
                }
            ),
        )
        adapter = DataGoAdapter(catalogue=[custom_dataset])
        schema = adapter.get_schema(custom_dataset)

        assert schema is not None
        assert len(schema.fields) == 1
        assert schema.fields[0].name == "valid_field"

    # test get schema empty fields returns none Describes the scenario verified by the test.
    def test_get_schema_empty_fields_returns_none(self) -> None:
        """
        test get schema empty fields returns none Validates the scenario described by the test name.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        custom_dataset = DatasetRef(
            id="datago.test_empty",
            provider="datago",
            dataset_key="test_empty",
            name="Test Empty Fields",
            representation=Representation.API_JSON,
            operations=frozenset(),
            raw_metadata=MappingProxyType(
                {
                    "base_url": "https://example.test",
                    "fields": [],
                }
            ),
        )
        adapter = DataGoAdapter(catalogue=[custom_dataset])
        schema = adapter.get_schema(custom_dataset)
        assert schema is None


class TestDataGoGatewayErrors:
    """Tests for TestDataGoGatewayErrors.

    This class groups related test cases and helpers for TestDataGoGatewayErrors.
    """

    def test_unregistered_service_key_raises_auth_error(
        self, configured_adapter: AdapterFactory
    ) -> None:
        adapter, dataset, _ = configured_adapter(
            ["error_gateway_key_not_registered.xml"], content_type="text/xml"
        )

        with pytest.raises(AuthError) as exc:
            adapter.query_records(dataset, Query())

        assert "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in str(exc.value)
        assert exc.value.provider_code == "30"

    def test_quota_exceeded_raises_rate_limit_error(
        self, configured_adapter: AdapterFactory
    ) -> None:
        from kpubdata.exceptions import RateLimitError

        adapter, dataset, _ = configured_adapter(
            ["error_gateway_quota_exceeded.xml"], content_type="text/xml"
        )

        with pytest.raises(RateLimitError) as exc:
            adapter.query_records(dataset, Query())

        assert exc.value.provider_code == "22"

    def test_unregistered_ip_raises_auth_error(self, configured_adapter: AdapterFactory) -> None:
        adapter, dataset, _ = configured_adapter(
            ["error_gateway_unregistered_ip.xml"], content_type="text/xml"
        )

        with pytest.raises(AuthError) as exc:
            adapter.query_records(dataset, Query())

        assert exc.value.provider_code == "32"

    def test_a_gateway_error_is_not_reported_as_a_malformed_envelope(
        self, configured_adapter: AdapterFactory
    ) -> None:
        # Regression prevention: Previous behavior was "Malformed response envelope: missing response"was.
        adapter, dataset, _ = configured_adapter(
            ["error_gateway_key_not_registered.xml"], content_type="text/xml"
        )

        with pytest.raises(AuthError) as exc:
            adapter.query_records(dataset, Query())

        assert "Malformed response envelope" not in str(exc.value)
