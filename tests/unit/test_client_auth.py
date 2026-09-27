"""Unit test module.

tests/unit/test_client_auth.py`` Defines test scenarios and helper objects.
Verifies core flows, exceptions, and edge conditions for regression prevention and public contract validation.
"""

from __future__ import annotations

from kpubdata.client import Client
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor


class _AdapterWithoutFlag:
    """
    _AdapterWithoutFlag Class encapsulating related operations.

    This class in ``tests/unit/test_client_auth.py`` module manages _AdapterWithoutFlagstate and behavior.
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
        return "beta"

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
        raise LookupError(dataset_key)

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
        _ = query
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
        _ = dataset
        _ = operation
        _ = params
        return None


# test iter authenticated providers defaults missing flag to true Describes scenario being tested.
def test_iter_authenticated_providers_defaults_missing_flag_to_true() -> None:
    """
    test iter authenticated providers defaults missing flag to true Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = Client()
    client.register_provider(_AdapterWithoutFlag())

    provider_names = {adapter.name for adapter in client.iter_authenticated_providers()}

    assert "beta" in provider_names
    assert "krx" not in provider_names
