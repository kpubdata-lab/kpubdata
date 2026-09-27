"""Test module.

This file defines test scenarios and helper objects for the
tests/unit/providers/bok/test_bok_adapter.py path. It validates core flows,
exceptions, and edge conditions to prevent regressions and verify the
public contract.
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
from kpubdata.providers.bok.adapter import BokAdapter
from kpubdata.transport.http import HttpTransport


class FakeResponse:
    """Mock HTTP response object for testing."""

    def __init__(self, payload: dict[str, object]) -> None:
        """Initialize FakeResponse with payload.

        Args:
            payload (dict[str, object]): Response body.
        """
        self.headers: dict[str, str] = {"content-type": "application/json"}
        self.text: str = json.dumps(payload)
        self.content: bytes = self.text.encode()


class FakeTransport:
    """Mock HTTP transport for testing."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        """Initialize FakeTransport with responses.

        Args:
            responses (list[FakeResponse]): Queue of responses.
        """
        self._responses: list[FakeResponse] = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        """Execute a mocked HTTP request.

        Args:
            method (str): HTTP method.
            url (str): Request URL.
            **kwargs (object): Additional request parameters.

        Returns:
            FakeResponse: Next response from queue.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._responses.pop(0)


def _success_payload(*, items: object, total_count: object) -> dict[str, object]:
    """Build success response payload.

    Args:
        items (object): Response items.
        total_count (object): Total count value.

    Returns:
        dict[str, object]: Payload dict.
    """
    return {
        "StatisticSearch": {
            "list_total_count": total_count,
            "row": items,
        }
    }


def _build_adapter_with_transport(
    responses: list[FakeResponse], *, dataset_key: str = "base_rate"
) -> tuple[BokAdapter, DatasetRef, FakeTransport]:
    """Build adapter with mock transport.

    Args:
        responses (list[FakeResponse]): Response queue.
        dataset_key (str): Dataset key to load.

    Returns:
        tuple: (adapter, dataset, transport) triple.
    """
    transport = FakeTransport(responses)
    adapter = BokAdapter(
        config=KPubDataConfig(provider_keys={"bok": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset(dataset_key)
    return adapter, dataset, transport


# Verify catalogue includes USD/KRW daily dataset.
def test_catalogue_includes_usd_krw_daily_dataset() -> None:
    """Verify USD/KRW daily dataset is in the catalogue.

    The test name describes the expected behavior verified by the test.
    """
    _, dataset, _ = _build_adapter_with_transport([], dataset_key="usd_krw")
    catalogue = cast(
        list[dict[str, object]],
        json.loads(
            files("kpubdata.providers.bok").joinpath("catalogue.json").read_text(encoding="utf-8")
        ),
    )
    usd_krw_entry = next(entry for entry in catalogue if entry["dataset_key"] == "usd_krw")

    assert dataset.id == "bok.usd_krw"
    assert dataset.name == "원/달러 환율 매매기준율 (USD/KRW Exchange Rate)"
    assert dataset.description == "Bank of Korea ECOS USD/KRW exchange rate historical data"
    assert dataset.raw_metadata["stat_code"] == "731Y003"
    assert dataset.raw_metadata["item_code1"] == "0000003"
    assert dataset.tags == ("finance", "exchange-rate", "fx")
    assert dataset.query_support is not None
    assert dataset.query_support.pagination.value == "offset"
    assert dataset.query_support.max_page_size == 1000
    assert usd_krw_entry["query_support"] == {
        "pagination": "offset",
        "max_page_size": 1000,
        "frequency": ["D"],
    }
    raw_fields = cast(list[dict[str, object]], dataset.raw_metadata["fields"])
    assert [field["name"] for field in raw_fields] == [
        "TIME",
        "DATA_VALUE",
        "UNIT_NAME",
        "STAT_CODE",
        "ITEM_CODE1",
        "ITEM_NAME1",
    ]


# Verify catalogue includes Treasury Bond 3Y daily dataset.
def test_catalogue_includes_bond_yield_3y_daily_dataset() -> None:
    """Verify Treasury Bond 3Y yield dataset is in the catalogue."""
    _, dataset, _ = _build_adapter_with_transport([], dataset_key="bond_yield_3y")
    catalogue = cast(
        list[dict[str, object]],
        json.loads(
            files("kpubdata.providers.bok").joinpath("catalogue.json").read_text(encoding="utf-8")
        ),
    )
    bond_yield_3y_entry = next(
        entry for entry in catalogue if entry["dataset_key"] == "bond_yield_3y"
    )

    assert dataset.id == "bok.bond_yield_3y"
    assert dataset.name == "국고채 3년물 수익률 (Korea Treasury Bond 3Y Yield)"
    assert dataset.description == "Bank of Korea ECOS Korea Treasury Bond 3Y yield historical data"
    assert dataset.raw_metadata["stat_code"] == "817Y002"
    assert dataset.raw_metadata["item_code1"] == "010200000"
    assert dataset.tags == ("finance", "interest-rate", "bond", "treasury")
    assert dataset.query_support is not None
    assert dataset.query_support.pagination.value == "offset"
    assert dataset.query_support.max_page_size == 1000
    assert bond_yield_3y_entry["query_support"] == {
        "pagination": "offset",
        "max_page_size": 1000,
        "frequency": ["D"],
    }
    raw_fields = cast(list[dict[str, object]], dataset.raw_metadata["fields"])
    assert [field["name"] for field in raw_fields] == [
        "TIME",
        "DATA_VALUE",
        "UNIT_NAME",
        "STAT_CODE",
        "ITEM_CODE1",
        "ITEM_NAME1",
    ]


# Verify catalogue includes Money Supply M2 monthly dataset.
def test_catalogue_includes_money_supply_monthly_dataset() -> None:
    """Verify Money Supply M2 dataset is in the catalogue."""
    _, dataset, _ = _build_adapter_with_transport([], dataset_key="money_supply")
    catalogue = cast(
        list[dict[str, object]],
        json.loads(
            files("kpubdata.providers.bok").joinpath("catalogue.json").read_text(encoding="utf-8")
        ),
    )
    money_supply_entry = next(
        entry for entry in catalogue if entry["dataset_key"] == "money_supply"
    )

    assert dataset.id == "bok.money_supply"
    assert dataset.name == "통화량(M2) 구 통계 (Money Supply M2, Legacy Series)"
    assert (
        dataset.description
        == "Bank of Korea ECOS M2 money supply monthly data (legacy series, 198601-200409)"
    )
    assert dataset.raw_metadata["stat_code"] == "101Y003"
    assert dataset.raw_metadata["item_code1"] == "BBHS00"
    assert dataset.tags == ("finance", "money-supply", "monetary-aggregate")
    assert dataset.query_support is not None
    assert dataset.query_support.pagination.value == "offset"
    assert dataset.query_support.max_page_size == 1000
    assert money_supply_entry["query_support"] == {
        "pagination": "offset",
        "max_page_size": 1000,
        "frequency": ["M"],
    }
    raw_fields = cast(list[dict[str, object]], dataset.raw_metadata["fields"])
    assert [field["name"] for field in raw_fields] == [
        "TIME",
        "DATA_VALUE",
        "UNIT_NAME",
        "STAT_CODE",
        "ITEM_CODE1",
        "ITEM_NAME1",
    ]


# Verify query_records returns single page and sets next_page correctly.
def test_query_records_returns_single_page_and_sets_next_page() -> None:
    """Verify query_records returns paginated results and next_page."""
    payload = _success_payload(items=[{"id": 1}, {"id": 2}], total_count=5)
    adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

    batch = adapter.query_records(
        dataset,
        Query(page=1, page_size=2, start_date="202401", end_date="202403"),
    )

    assert batch.items == [{"id": 1}, {"id": 2}]
    assert batch.total_count == 5
    assert batch.next_page == 2
    assert batch.raw == payload
    assert len(transport.calls) == 1


# Verify query_records uses default page size of 100.
def test_query_records_uses_default_page_size_100() -> None:
    """Verify default page size is 100."""
    payload = _success_payload(items=[{"id": 1}], total_count=1)
    adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

    _batch = adapter.query_records(dataset, Query(start_date="202401", end_date="202403"))

    request_url = cast(str, transport.calls[0]["url"])
    assert "/1/100/" in request_url


# Verify heuristic next_page computation works without total_count.
def test_query_records_uses_heuristic_next_page_without_total_count() -> None:
    """Verify next_page calculated heuristically when total_count is None."""
    payload = _success_payload(items=[{"id": 1}, {"id": 2}], total_count=None)
    adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

    batch = adapter.query_records(
        dataset,
        Query(page=1, page_size=2, start_date="202401", end_date="202403"),
    )

    assert batch.total_count is None
    assert batch.next_page == 2


# Verify missing dates are logged at debug level.
def test_query_records_missing_dates_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """Verify InvalidRequestError logged when start/end dates missing."""
    adapter, dataset, _ = _build_adapter_with_transport([])

    caplog.set_level(logging.DEBUG, logger="kpubdata.provider.bok")
    with pytest.raises(InvalidRequestError, match="start_date and end_date"):
        _ = adapter.query_records(dataset, Query())

    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "BOK ECOS invalid query: missing start/end date"
    )
    assert record.__dict__["dataset_id"] == dataset.id


# Verify zero items response is logged at debug level.
def test_query_records_zero_items_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """Verify empty result logged with dataset and pagination info."""
    payload = _success_payload(items=[], total_count=0)
    adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

    caplog.set_level(logging.DEBUG, logger="kpubdata.provider.bok")
    batch = adapter.query_records(
        dataset,
        Query(page=1, page_size=10, start_date="202401", end_date="202403"),
    )

    assert batch.items == []
    record = next(
        record for record in caplog.records if record.getMessage() == "BOK envelope: zero items"
    )
    assert record.__dict__["dataset_id"] == dataset.id
    assert record.__dict__["page"] == 1
    assert record.__dict__["page_size"] == 10
    assert record.__dict__["total_count"] == 0


# Verify _raise_for_result returns None when no RESULT field present.
def test_raise_for_result_returns_none_when_no_result_field() -> None:
    """Verify normal response without RESULT field does not raise."""
    adapter, dataset, _ = _build_adapter_with_transport([])
    result = adapter._raise_for_result({"StatisticSearch": {}}, dataset.id)
    assert result is None


# Verify _raise_for_result raises on non-ERROR codes in RESULT field.
def test_raise_for_result_raises_on_non_error_code_in_result_field() -> None:
    """Verify any code in RESULT field raises error (not just ERROR)."""
    adapter, dataset, _ = _build_adapter_with_transport([])
    # Previous implementation: non-ERROR codes treated as success, no exception.
    # After fix: any RESULT field is treated as error.
    with pytest.raises(ProviderResponseError):
        adapter._raise_for_result({"RESULT": {"CODE": "INFO-100", "MESSAGE": "warning"}}, dataset.id)


# Verify _raise_for_result raises when RESULT CODE field is absent.
def test_raise_for_result_raises_when_result_code_absent() -> None:
    """Verify missing CODE in RESULT field raises ProviderResponseError."""
    adapter, dataset, _ = _build_adapter_with_transport([])
    with pytest.raises(ProviderResponseError):
        adapter._raise_for_result({"RESULT": {"MESSAGE": "missing code"}}, dataset.id)


# Verify _raise_for_result raises AuthError for invalid credentials.
def test_raise_for_result_raises_auth_error_on_auth_message() -> None:
    """Verify AuthError raised when RESULT CODE=ERROR with auth message."""
    adapter, dataset, _ = _build_adapter_with_transport([])
    with pytest.raises(AuthError):
        adapter._raise_for_result(
            {"RESULT": {"CODE": "ERROR", "MESSAGE": "invalid API key"}}, dataset.id
        )


def test_query_records_passes_the_path_key_as_a_secret_value() -> None:
    """BOK embeds API key in URL path segment for all requests (#354).

    Query parameter-based masking cannot hide path-embedded keys.
    The raw key must be passed to transport as secret_values so that
    logs and error messages can sanitize URLs correctly. Otherwise,
    a single transport error exposes the raw API key.
    """
    payload = _success_payload(items=[{"id": 1}], total_count=1)
    adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

    adapter.query_records(dataset, Query(page_size=1, start_date="202401", end_date="202403"))

    call = transport.calls[0]
    assert call.get("secret_values") == ("test-key",)


def test_the_bok_request_url_still_carries_the_key_in_its_path() -> None:
    # Verify the reason secret_values is needed — key is actually in the path.
    payload = _success_payload(items=[{"id": 1}], total_count=1)
    adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

    adapter.query_records(dataset, Query(page_size=1, start_date="202401", end_date="202403"))

    assert "/test-key/" in str(transport.calls[0]["url"])
