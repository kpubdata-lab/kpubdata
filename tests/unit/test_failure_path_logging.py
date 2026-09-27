"""Unit test module.

tests/unit/test_failure_path_logging.py`` Defines test scenarios and helper objects.
Verifies core flows, exceptions, and edge conditions for regression prevention and public contract validation.
"""

from __future__ import annotations

import logging

import pytest

from kpubdata.catalog import Catalog
from kpubdata.config import KPubDataConfig
from kpubdata.core.dataset import Dataset
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.core.representation import Representation
from kpubdata.exceptions import ConfigError, DatasetNotFoundError, UnsupportedCapabilityError
from kpubdata.registry import ProviderRegistry


class _FakeAdapter:
    """
    _FakeAdapter Class encapsulating related operations.

    This class in ``tests/unit/test_failure_path_logging.py`` module manages _FakeAdapterstate and behavior.
    Key methods: list_datasets, search_datasets, get_dataset, query_records, get_schema.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    name = "fake"

    def list_datasets(self) -> list[DatasetRef]:
        """
        list datasets Performs the operation.

        Returns:
            list[DatasetRef]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return []

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """
        search datasets Performs the operation.

        Args:
            text (str): Input value provided by caller.

        Returns:
            list[DatasetRef]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = text
        return []

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """
        get dataset Performs the operation.

        Args:
            dataset_key (str): Input value provided by caller.

        Returns:
            DatasetRef: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        raise DatasetNotFoundError(
            f"Dataset not found: fake.{dataset_key}",
            provider="fake",
            dataset_id=f"fake.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """
        query records Performs the operation.

        Args:
            dataset (DatasetRef): Input value provided by caller.
            query (Query): Input value provided by caller.

        Returns:
            RecordBatch: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = dataset, query
        raise AssertionError("query_records should not be called")

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """
        get schema Performs the operation.

        Args:
            dataset (DatasetRef): Input value provided by caller.

        Returns:
            SchemaDescriptor | None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = dataset
        return None

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """
        call raw Performs the operation.

        Args:
            dataset (DatasetRef): Input value provided by caller.
            operation (str): Input value provided by caller.
            params (dict[str, object]): Input value provided by caller.

        Returns:
            object: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = dataset, operation, params
        return None


# test catalog resolve failure logs debug Describes scenario being tested.
def test_catalog_resolve_failure_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """
    test catalog resolve failure logs debug Verifies scenario.

    Args:
        caplog (pytest.LogCaptureFixture): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    registry = ProviderRegistry()
    registry.register(_FakeAdapter())
    catalog = Catalog(registry)

    caplog.set_level(logging.DEBUG, logger="kpubdata.catalog")
    with pytest.raises(DatasetNotFoundError):
        _ = catalog.resolve("fake.nope")

    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "Catalog resolve failed: dataset not found"
    )
    assert record.__dict__["dataset_id"] == "fake.nope"
    assert record.__dict__["provider"] == "fake"


# test dataset list unsupported logs debug Describes scenario being tested.
def test_dataset_list_unsupported_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """
    test dataset list unsupported logs debug Verifies scenario.

    Args:
        caplog (pytest.LogCaptureFixture): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    dataset = Dataset(
        ref=DatasetRef(
            id="fake.raw_only",
            provider="fake",
            dataset_key="raw_only",
            name="Raw Only",
            operations=frozenset(),
            representation=Representation.API_JSON,
        ),
        adapter=_FakeAdapter(),
    )

    caplog.set_level(logging.DEBUG, logger="kpubdata.dataset")
    with pytest.raises(UnsupportedCapabilityError):
        _ = dataset.list()

    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "Dataset does not support LIST"
    )
    assert record.__dict__["dataset_id"] == "fake.raw_only"
    assert record.__dict__["provider"] == "fake"
    assert record.__dict__["operation"] == "list"


# test missing provider key logs debug Describes scenario being tested.
def test_missing_provider_key_logs_debug(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    test missing provider key logs debug Verifies scenario.

    Args:
        caplog (pytest.LogCaptureFixture): Input value provided by caller.
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    monkeypatch.delenv("KPUBDATA_DATAGO_API_KEY", raising=False)
    monkeypatch.delenv("DATAGO_API_KEY", raising=False)
    cfg = KPubDataConfig()

    caplog.set_level(logging.DEBUG, logger="kpubdata.config")
    with pytest.raises(ConfigError):
        cfg.require_provider_key("datago")

    record = next(
        record for record in caplog.records if record.getMessage() == "Missing provider API key"
    )
    assert record.__dict__["provider"] == "datago"
