"""Test module.

This file defines test scenarios and helper objects at ``tests/contract/test_bok.py````.
It verifies core flows, exceptions, and edge cases for regression prevention and
public contract validation.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.transport.http import HttpTransport
from tests.contract.provider_adapter import ProviderAdapterContract


def _fixture_path(name: str) -> Path:
    """
    Internal helper for fixture path handling.

    Args:
        name (str): Input value provided by caller.

    Returns:
        Path: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may
        propagate unchanged.
    """
    return Path(__file__).resolve().parents[1] / "fixtures" / "bok" / name


def _load_fixture_bytes(name: str) -> bytes:
    """
    Internal helper for load fixture bytes handling.

    Args:
        name (str): Input value provided by caller.

    Returns:
        bytes: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may
        propagate unchanged.
    """
    return _fixture_path(name).read_bytes()


class _FakeResponse:
    """
    _FakeResponse class that encapsulates its role.

    This class manages state and behavior within ``tests/contract/test_bok.py`` module. _FakeResponseKey methods: __init__..

    Attribute descriptions:
        Properties defined in constructor and class body are reused by
        subordinate methods as common context.
    """

    def __init__(self, data: bytes, content_type: str = "application/json") -> None:
        """
        Initializes internal state for the object.

        Args:
            data (bytes): Input value provided by caller.
            content_type (str): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        self.headers: dict[str, str] = {"content-type": content_type}
        self.content: bytes = data
        self.text: str = data.decode("utf-8")


class _FixtureTransport:
    """
    _FixtureTransport class that encapsulates its role.

    This class manages state and behavior within ``tests/contract/test_bok.py`` module. _FixtureTransportKey methods: __init__, request..

    Attribute descriptions:
        Properties defined in constructor and class body are reused by
        subordinate methods as common context.
    """

    def __init__(self, fixture_names: list[str]) -> None:
        """
        Initializes internal state for the object.

        Args:
            fixture_names (list[str]): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        self._responses: list[_FakeResponse] = [
            _FakeResponse(_load_fixture_bytes(name)) for name in fixture_names
        ]
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        """
        Performs HTTP request operation.

        Args:
            method (str): Input value provided by caller.
            url (str): Input value provided by caller.
            **kwargs (object): Input value provided by caller.

        Returns:
            _FakeResponse: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No fixture responses remaining")
        return self._responses.pop(0)


class _AdapterFactory(Protocol):
    """
    _AdapterFactory class that encapsulates its role.

    This class manages state and behavior within ``tests/contract/test_bok.py`` module. _AdapterFactoryKey methods: __call__..

    Attribute descriptions:
        Properties defined in constructor and class body are reused by
        subordinate methods as common context.
    """

    def __call__(
        self,
        *,
        config: KPubDataConfig | None = None,
        transport: HttpTransport | None = None,
    ) -> ProviderAdapter: ...


def _build_adapter_with_transport(
    fixture_names: list[str],
) -> tuple[ProviderAdapter, _FixtureTransport]:
    """
    Internal helper to build adapter with custom transport.

    Args:
        fixture_names (list[str]): Input value provided by caller.

    Returns:
        tuple[ProviderAdapter, _FixtureTransport]: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may
        propagate unchanged.
    """
    transport = _FixtureTransport(fixture_names)
    config = KPubDataConfig(provider_keys={"bok": "test-key"})
    adapter_module = import_module("kpubdata.providers.bok.adapter")
    adapter_class_obj = cast(object, adapter_module.BokAdapter)
    if not isinstance(adapter_class_obj, type):
        raise AssertionError("BokAdapter is not a class")
    adapter_class = cast(_AdapterFactory, adapter_class_obj)
    adapter_obj = adapter_class(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter_obj, transport


def _build_adapter(fixture_names: list[str]) -> ProviderAdapter:
    """
    Internal helper to build adapter.

    Args:
        fixture_names (list[str]): Input value provided by caller.

    Returns:
        ProviderAdapter: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may
        propagate unchanged.
    """
    adapter, _ = _build_adapter_with_transport(fixture_names)
    return adapter


class TestBokAdapterContract(ProviderAdapterContract):
    """
    TestBokAdapterContract class that encapsulates its role.

    This class manages state and behavior within ``tests/contract/test_bok.py`` module. TestBokAdapterContractKey methods: adapter, valid_dataset_key, invalid_dataset_key, sample_dataset, sample_query..

    Attribute descriptions:
        Properties defined in constructor and class body are reused by
        subordinate methods as common context.
    """

    @pytest.fixture()
    def adapter(self) -> ProviderAdapter:
        """
        Performs adapter fixture operation.

        Returns:
            ProviderAdapter: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return _build_adapter(["success_single_page.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        """
        Returns valid dataset key.

        Returns:
            str: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return "base_rate"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        """
        inReturns valid dataset key.

        Returns:
            str: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: ProviderAdapter) -> DatasetRef:
        """
        Returns sample dataset.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.

        Returns:
            DatasetRef: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return adapter.get_dataset("base_rate")

    @pytest.fixture()
    def sample_query(self) -> Query:
        """
        Returns sample query.

        Returns:
            Query: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return Query(start_date="202401", end_date="202403")

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        """
        Returns raw operation parameters.

        Returns:
            tuple[str, dict[str, object]]: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return (
            "StatisticSearch",
            {"start_date": "202401", "end_date": "202403", "frequency": "M"},
        )


# test usd krw query records builds daily ecos url and parses fixture test scenario.
def test_usd_krw_query_records_builds_daily_ecos_url_and_parses_fixture() -> None:
    """
    Verifies USD/KRW query builds daily ECOS URL and parses fixture.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter, transport = _build_adapter_with_transport(["usd_krw_success.json"])
    dataset = adapter.get_dataset("usd_krw")

    batch = adapter.query_records(
        dataset,
        Query(
            start_date="20240101",
            end_date="20240105",
            extra={"frequency": "D"},
        ),
    )

    request_url = cast(str, transport.calls[0]["url"])
    assert "/StatisticSearch/" in request_url
    assert "731Y003/D/20240101/20240105/0000003" in request_url
    assert len(batch.items) == 4
    assert [item["TIME"] for item in batch.items] == [
        "20240102",
        "20240103",
        "20240104",
        "20240105",
    ]


# test bond yield 3y query records builds daily ecos url and parses fixture test scenario.
def test_bond_yield_3y_query_records_builds_daily_ecos_url_and_parses_fixture() -> None:
    """
    Verifies 3Y bond yield query builds daily ECOS URL and parses fixture.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter, transport = _build_adapter_with_transport(["bond_yield_3y_success.json"])
    dataset = adapter.get_dataset("bond_yield_3y")

    batch = adapter.query_records(
        dataset,
        Query(
            start_date="20240102",
            end_date="20240108",
            extra={"frequency": "D"},
        ),
    )

    request_url = cast(str, transport.calls[0]["url"])
    assert "/StatisticSearch/" in request_url
    assert "817Y002/D/20240102/20240108/010200000" in request_url
    assert len(batch.items) == 5
    assert [item["TIME"] for item in batch.items] == [
        "20240102",
        "20240103",
        "20240104",
        "20240105",
        "20240108",
    ]


# test money supply query records builds monthly ecos url and parses fixture test scenario.
def test_money_supply_query_records_builds_monthly_ecos_url_and_parses_fixture() -> None:
    """
    Verifies money supply query builds monthly ECOS URL and parses fixture.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter, transport = _build_adapter_with_transport(["money_supply_success.json"])
    dataset = adapter.get_dataset("money_supply")

    batch = adapter.query_records(
        dataset,
        Query(
            start_date="200301",
            end_date="200303",
            extra={"frequency": "M"},
        ),
    )

    request_url = cast(str, transport.calls[0]["url"])
    assert "/StatisticSearch/" in request_url
    assert "101Y003/M/200301/200303/BBHS00" in request_url
    assert len(batch.items) == 3
    assert [item["TIME"] for item in batch.items] == ["200301", "200302", "200303"]
    assert {item["STAT_CODE"] for item in batch.items} == {"101Y003"}
    assert {item["ITEM_CODE1"] for item in batch.items} == {"BBHS00"}
