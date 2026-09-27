"""Unit test module.

tests/unit/test_catalog_coverage.py`` Defines test scenarios and helper objects.
Verifies core flows, exceptions, and edge conditions for regression prevention and public contract validation.
"""

from __future__ import annotations

import pytest

from kpubdata.catalog import Catalog
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.exceptions import DatasetNotFoundError
from kpubdata.registry import ProviderRegistry


class _ExplodingAdapter:
    """
    _ExplodingAdapter Class encapsulating related operations.

    This class in ``tests/unit/test_catalog_coverage.py`` module manages _ExplodingAdapterstate and behavior.
    Key methods: name, list_datasets, search_datasets, get_dataset, query_records.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    @property
    def name(self) -> str:
        """
        name Performs the operation.

        Returns:
            str: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return "alpha"

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
        raise RuntimeError("unexpected adapter failure")

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
        return RecordBatch(items=[], dataset=dataset)

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
        return None


# test resolve wraps unexpected adapter errors as dataset not found Describes scenario being tested.
def test_resolve_wraps_unexpected_adapter_errors_as_dataset_not_found() -> None:
    """
    test resolve wraps unexpected adapter errors as dataset not found Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    registry = ProviderRegistry()
    registry.register(_ExplodingAdapter())
    catalog = Catalog(registry)

    with pytest.raises(DatasetNotFoundError) as exc_info:
        _ = catalog.resolve("alpha.some_dataset")

    error = exc_info.value
    assert error.provider == "alpha"
    assert error.dataset_id == "alpha.some_dataset"
    assert "Dataset not found" in str(error)
