"""Test module.

This file defines test scenarios and helper objects at ``tests/contract/test_kosis.py````.
It verifies core flows, exceptions, and edge cases for regression prevention and
public contract validation.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.exceptions import AuthError
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
    return Path(__file__).resolve().parents[1] / "fixtures" / "kosis" / name


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

    This class manages state and behavior within ``tests/contract/test_kosis.py`` module. _FakeResponseKey methods: __init__..

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

    This class manages state and behavior within ``tests/contract/test_kosis.py`` module. _FixtureTransportKey methods: __init__, request..

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
    transport = _FixtureTransport(fixture_names)
    config = KPubDataConfig(provider_keys={"kosis": "test-key"})
    module = import_module("kpubdata.providers.kosis.adapter")
    adapter_class = cast(Callable[..., ProviderAdapter], module.KosisAdapter)
    return adapter_class(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )


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
    config = KPubDataConfig(provider_keys={"kosis": "test-key"})
    module = import_module("kpubdata.providers.kosis.adapter")
    adapter_class = cast(Callable[..., ProviderAdapter], module.KosisAdapter)
    adapter = adapter_class(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter, transport


class TestKosisAdapterContract(ProviderAdapterContract):
    """
    TestKosisAdapterContract class that encapsulates its role.

    This class manages state and behavior within ``tests/contract/test_kosis.py`` module. TestKosisAdapterContractKey methods: adapter, valid_dataset_key, invalid_dataset_key, sample_dataset, sample_query..

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
        return "population_migration"

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
        return adapter.get_dataset("population_migration")

    @pytest.fixture()
    def sample_query(self) -> Query:
        """
        Returns sample query.

        Returns:
            Query: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return Query(start_date="202401", end_date="202401")

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        """
        Returns raw operation parameters.

        Returns:
            tuple[str, dict[str, object]]: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return ("statisticsParameterData", {})

    # test query records empty array returns empty batch test scenario.
    def test_query_records_empty_array_returns_empty_batch(self) -> None:
        """
        Verifies empty array result returns empty batch.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.

        Examples:
            Verifies expected behavior described by test name is maintained without regression.
        """
        adapter = _build_adapter(["success_empty.json"])
        dataset = adapter.get_dataset("population_migration")

        batch = adapter.query_records(dataset, Query(start_date="202401", end_date="202401"))

        assert batch.items == []
        assert batch.total_count == 0

    # test query records auth error maps to auth error test scenario.
    def test_query_records_auth_error_maps_to_auth_error(self) -> None:
        """
        Verifies auth error is mapped correctly.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.

        Examples:
            Verifies expected behavior described by test name is maintained without regression.
        """
        adapter = _build_adapter(["error_auth.json"])
        dataset = adapter.get_dataset("population_migration")

        with pytest.raises(AuthError):
            _ = adapter.query_records(dataset, Query(start_date="202401", end_date="202401"))


# test industrial production query records builds default param url and parses fixture test scenario.
def test_industrial_production_query_records_builds_default_param_url_and_parses_fixture() -> None:
    """
    Verifies industrial production query builds default parameter URL and parses fixture.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter, transport = _build_adapter_with_transport(["industrial_production_success.json"])
    dataset = adapter.get_dataset("industrial_production")

    batch = adapter.query_records(dataset, Query(start_date="202401", end_date="202401"))

    request_url = cast(str, transport.calls[0]["url"])
    assert "tblId=DT_1J22003" in request_url
    assert "objL1=T10" in request_url
    assert "itmId=T" in request_url
    assert "prdSe=M" in request_url
    assert "objL2=ALL" not in request_url
    assert len(batch.items) == 1
    assert batch.items[0]["TBL_ID"] == "DT_1J22003"
    assert batch.items[0]["C1"] == "T10"
