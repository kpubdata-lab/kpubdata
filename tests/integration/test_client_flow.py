"""Test module for integration tests.

Defines test scenarios and helper functions in ``tests/integration/test_client_flow.py``.
Verifies core flows, exceptions, and edge cases to prevent regressions and validate the public contract..
"""

from __future__ import annotations

import pytest

from kpubdata.client import Client
from kpubdata.core.capability import Operation
from kpubdata.core.dataset import Dataset
from kpubdata.core.models import DatasetRef, Query, RecordBatch
from kpubdata.core.representation import Representation
from kpubdata.exceptions import (
    DatasetNotFoundError,
    ProviderNotRegisteredError,
)


class FakeAdapter:
    """
    FakeAdapter encapsulates the class definition and state.

    This class manages FakeAdapter state and operations within the test_client_flow module.
    Key methods: __init__, name, list_datasets, search_datasets, get_dataset.

    Property descriptions:
        Attributes defined in __init__ and class body are reused by methods as shared context.
    """

    def __init__(self) -> None:
        """
        Initialize instance state.

        Returns:
            None.

        Raises:
            Exceptions from implementation or dependencies propagate.
        """
        self._datasets: dict[str, DatasetRef] = {
            "weather": DatasetRef(
                id="fake.weather",
                provider="fake",
                dataset_key="weather",
                name="Weather Data",
                representation=Representation.API_JSON,
                operations=frozenset({Operation.LIST, Operation.RAW}),
            ),
            "stations": DatasetRef(
                id="fake.stations",
                provider="fake",
                dataset_key="stations",
                name="Station List",
                representation=Representation.API_JSON,
                operations=frozenset({Operation.LIST, Operation.RAW}),
            ),
        }
        self.last_query: tuple[DatasetRef, Query] | None = None
        self.last_raw_call: tuple[DatasetRef, str, dict[str, object]] | None = None

    @property
    def name(self) -> str:
        """
        Provider name.

        Returns:
            str: provider name.

        Raises:
            Exceptions from implementation or dependencies propagate.
        """
        return "fake"

    def list_datasets(self) -> list[DatasetRef]:
        """
        List all available datasets.

        Returns:
            list[DatasetRef]: dataset list.

        Raises:
            Exceptions from implementation or dependencies propagate.
        """
        return [self._datasets["weather"], self._datasets["stations"]]

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """
        Search datasets by text.

        Args:
            text (str): search text.

        Returns:
            list[DatasetRef]: dataset list.

        Raises:
            Exceptions from implementation or dependencies propagate.
        """
        needle = text.casefold()
        return [
            dataset_ref
            for dataset_ref in self._datasets.values()
            if needle in dataset_ref.name.casefold()
        ]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """
        Get dataset by key.

        Args:
            dataset_key (str): dataset key.

        Returns:
            DatasetRef: the dataset reference.

        Raises:
            Exceptions from implementation or dependencies propagate.
        """
        try:
            return self._datasets[dataset_key]
        except KeyError as exc:
            raise DatasetNotFoundError(f"Dataset not found: {dataset_key}") from exc

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """
        Query records from dataset.

        Args:
            dataset (DatasetRef): target dataset.
            query (Query): query parameters.

        Returns:
            RecordBatch: result records.

        Raises:
            Exceptions from implementation or dependencies propagate.
        """
        self.last_query = (dataset, query)
        return RecordBatch(
            items=[
                {"id": "w-001", "value": "sunny"},
                {"id": "w-002", "value": "rain"},
            ],
            dataset=dataset,
            total_count=2,
        )

    def get_schema(self, _dataset: DatasetRef) -> None:
        """
        Get dataset schema.

        Args:
            _dataset (DatasetRef): target dataset.

        Returns:
            None.

        Raises:
            Exceptions from implementation or dependencies propagate.
        """
        return None

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """
        Call raw provider operation.

        Args:
            dataset (DatasetRef): target dataset.
            operation (str): operation name.
            params (dict[str, object]): operation parameters.

        Returns:
            object: raw operation result.

        Raises:
            Exceptions from implementation or dependencies propagate.
        """
        self.last_raw_call = (dataset, operation, params)
        return {"ok": True, "dataset": dataset.id, "operation": operation, "params": params}


def _build_client() -> tuple[Client, FakeAdapter]:
    """
    Build client and FakeAdapter for testing.

    Returns:
        tuple[Client, FakeAdapter]: initialized client and adapter.

    Raises:
        Exceptions from implementation or dependencies propagate.
    """
    client = Client(provider_keys={"fake": "test-key"})
    fake = FakeAdapter()
    client.register_provider(fake)
    return client, fake


# # test register and list datasets scenario
def test_register_and_list_datasets() -> None:
    """
    Verify test register and list datasets scenario.

    Returns:
        None.

    Raises:
        Exceptions from implementation or dependencies propagate.
    """
    client, _fake = _build_client()

    refs = client.datasets.list()

    fake_refs = [ref for ref in refs if ref.provider == "fake"]
    assert len(fake_refs) == 2
    assert {ref.id for ref in fake_refs} == {"fake.weather", "fake.stations"}


# # test register and search datasets scenario
def test_register_and_search_datasets() -> None:
    """
    Verify test register and search datasets scenario.

    Returns:
        None.

    Raises:
        Exceptions from implementation or dependencies propagate.
    """
    client, _fake = _build_client()

    refs = client.datasets.search("weather")

    matched_ids = {ref.id for ref in refs}
    assert "fake.weather" in matched_ids


# # test dataset resolves to bound dataset scenario
def test_dataset_resolves_to_bound_dataset() -> None:
    """
    Verify test dataset resolves to bound dataset scenario.

    Returns:
        None.

    Raises:
        Exceptions from implementation or dependencies propagate.
    """
    client, _fake = _build_client()

    dataset = client.dataset("fake.weather")

    assert isinstance(dataset, Dataset)
    assert dataset.id == "fake.weather"
    assert dataset.name == "Weather Data"
    assert dataset.provider == "fake"
    assert dataset.operations == frozenset({Operation.LIST, Operation.RAW})


# # test dataset list delegates to query records scenario
def test_dataset_list_delegates_to_query_records() -> None:
    """
    Verify test dataset list delegates to query records scenario.

    Returns:
        None.

    Raises:
        Exceptions from implementation or dependencies propagate.
    """
    client, fake = _build_client()

    result = client.dataset("fake.weather").list(stationName="종로구")

    assert isinstance(result, RecordBatch)
    assert len(result.items) == 2
    assert fake.last_query is not None
    queried_dataset, query = fake.last_query
    assert queried_dataset.id == "fake.weather"
    assert query.filters == {"stationName": "종로구"}


# # test dataset call raw delegates to adapter scenario
def test_dataset_call_raw_delegates_to_adapter() -> None:
    """
    Verify test dataset call raw delegates to adapter scenario.

    Returns:
        None.

    Raises:
        Exceptions from implementation or dependencies propagate.
    """
    client, fake = _build_client()

    result = client.dataset("fake.weather").call_raw("getWeather", param1="value1")

    assert result == {
        "ok": True,
        "dataset": "fake.weather",
        "operation": "getWeather",
        "params": {"param1": "value1"},
    }
    assert fake.last_raw_call is not None
    raw_dataset, raw_operation, raw_params = fake.last_raw_call
    assert raw_dataset.id == "fake.weather"
    assert raw_operation == "getWeather"
    assert raw_params == {"param1": "value1"}


# # test dataset schema returns none scenario
def test_dataset_schema_returns_none() -> None:
    """
    Verify test dataset schema returns none scenario.

    Returns:
        None.

    Raises:
        Exceptions from implementation or dependencies propagate.
    """
    client, _fake = _build_client()

    result = client.dataset("fake.weather").schema()

    assert result is None


# # test unknown provider raises scenario
def test_unknown_provider_raises() -> None:
    """
    Verify test unknown provider raises scenario.

    Returns:
        None.

    Raises:
        Exceptions from implementation or dependencies propagate.
    """
    client = Client(provider_keys={"fake": "test-key"})

    with pytest.raises(ProviderNotRegisteredError):
        _ = client.dataset("unknown.ds")


# # test unknown dataset raises scenario
def test_unknown_dataset_raises() -> None:
    """
    Verify test unknown dataset raises scenario.

    Returns:
        None.

    Raises:
        Exceptions from implementation or dependencies propagate.
    """
    client, _fake = _build_client()

    with pytest.raises(DatasetNotFoundError):
        _ = client.dataset("fake.nonexistent")


# # test from env creates client scenario
def test_from_env_creates_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify test from env creates client scenario."""
    monkeypatch.setenv("KPUBDATA_TIMEOUT", "15")
    client = Client.from_env()
    fake = FakeAdapter()

    client.register_provider(fake)

    assert client.dataset("fake.weather").id == "fake.weather"
