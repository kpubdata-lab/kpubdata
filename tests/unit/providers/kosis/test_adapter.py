"""Test module.

This file defines test scenarios and helper objects for the tests/unit/providers/kosis/test_adapter.py path.
It validates core flows, exceptions, and edge conditions to prevent regressions and verify the public contract."""

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
    """Tests for FakeResponse.

This class groups related test cases and helpers for FakeResponse.
"""

    def __init__(self, payload: object) -> None:
        """
        Initialize with payload.

        Args:
            payload (object): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        self.headers: dict[str, str] = {"content-type": "application/json"}
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


def _build_adapter_with_transport(
    responses: list[FakeResponse],
    *,
    dataset_key: str = "population_migration",
) -> tuple[KosisAdapter, DatasetRef, FakeTransport]:
    """
    Build adapter with transport.

    Args:
        responses (list[FakeResponse]): Input parameter.
        dataset_key (str): Input parameter.

    Returns:
        tuple[KosisAdapter, DatasetRef, FakeTransport]: Result.

    Raises:
        Exceptions propagated."""
    transport = FakeTransport(responses)
    adapter = KosisAdapter(
        config=KPubDataConfig(provider_keys={"kosis": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset(dataset_key)
    return adapter, dataset, transport


# test catalogue parses industrial production default query params Describes the scenario verified by the test.
def test_catalogue_parses_industrial_production_default_query_params() -> None:
    """
    test catalogue parses industrial production default query params Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
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


# test adapter docstring documents default query params merge rule Describes the scenario verified by the test.
def test_adapter_docstring_documents_default_query_params_merge_rule() -> None:
    """
    Verify docstring docs.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    assert KosisAdapter.__doc__ is not None
    assert "dataset default_query_params < query.filters (호출자 우선)" in KosisAdapter.__doc__


# test query records missing start date logs debug Describes the scenario verified by the test.
def test_query_records_missing_start_date_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """
    test query records missing start date logs debug Validates the scenario described by the test name.

    Args:
        caplog (pytest.LogCaptureFixture): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
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


# test query records zero items logs debug Describes the scenario verified by the test.
def test_query_records_zero_items_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """
    test query records zero items logs debug Validates the scenario described by the test name.

    Args:
        caplog (pytest.LogCaptureFixture): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
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


# test population migration keeps hardcoded default query params Describes the scenario verified by the test.
def test_population_migration_keeps_hardcoded_default_query_params() -> None:
    """
    test population migration keeps hardcoded default query params Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter, dataset, transport = _build_adapter_with_transport([FakeResponse([])])

    batch = adapter.query_records(dataset, Query(start_date="202401", end_date="202401"))

    assert batch.items == []
    request_url = cast(str, transport.calls[0]["url"])
    assert "objL1=ALL" in request_url
    assert "objL2=ALL" in request_url
    assert "itmId=ALL" in request_url
    assert "prdSe=M" in request_url


# test query records applies dataset default query params when filters absent Describes the scenario verified by the test.
def test_query_records_applies_dataset_default_query_params_when_filters_absent() -> None:
    """
    test query records applies dataset default query params when filters absent Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
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


# test query records merges default query params but query filters win Describes the scenario verified by the test.
def test_query_records_merges_default_query_params_but_query_filters_win() -> None:
    """
    test query records merges default query params but query filters win Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
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


# test query records ignores non kosis default query param keys Describes the scenario verified by the test.
def test_query_records_ignores_non_kosis_default_query_param_keys() -> None:
    """
    test query records ignores non kosis default query param keys Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
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


# test raise for error payload returns none when err field absent Describes the scenario verified by the test.
def test_raise_for_error_payload_returns_none_when_err_field_absent() -> None:
    """test_raise_for_error_payload_returns_none_when_err_field_absent

Validates the scenario described by the test name.
"""
    adapter, dataset, _ = _build_adapter_with_transport([])
# Verifies test behavior (see test name for details).
    result = adapter._raise_for_error_payload({"some_field": "some_value"}, dataset.id)
    assert result is None


# test raise for error payload raises auth error on code 30 Describes the scenario verified by the test.
def test_raise_for_error_payload_raises_auth_error_on_code_30() -> None:
    """test_raise_for_error_payload_raises_auth_error_on_code_30

Validates the scenario described by the test name.
"""
    adapter, dataset, _ = _build_adapter_with_transport([])
    with pytest.raises(AuthError):
        adapter._raise_for_error_payload({"err": "30", "errMsg": "인증키 오류"}, dataset.id)


# test raise for error payload raises invalid request error on code 10 Describes the scenario verified by the test.
def test_raise_for_error_payload_raises_invalid_request_error_on_code_10() -> None:
    """test_raise_for_error_payload_raises_invalid_request_error_on_code_10

Validates the scenario described by the test name.
"""
    adapter, dataset, _ = _build_adapter_with_transport([])
    with pytest.raises(InvalidRequestError):
        adapter._raise_for_error_payload({"err": "10", "errMsg": "잘못된 요청"}, dataset.id)


# test raise for error payload raises provider response error on unknown code Describes the scenario verified by the test.
def test_raise_for_error_payload_raises_provider_response_error_on_unknown_code() -> None:
    """test_raise_for_error_payload_raises_provider_response_error_on_unknown_code

Validates the scenario described by the test name.
"""
    adapter, dataset, _ = _build_adapter_with_transport([])
    with pytest.raises(ProviderResponseError):
        adapter._raise_for_error_payload({"err": "99", "errMsg": "기타 오류"}, dataset.id)
