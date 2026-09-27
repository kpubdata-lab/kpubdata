"""Test module.

This file ``tests/unit/core/test_dataset_coverage.py`` defines test scenarios and helper objects.
For regression prevention and public contract validation verify core flows, exceptions, and edge conditions.
"""

from __future__ import annotations

from kpubdata.core.capability import Operation
from kpubdata.core.dataset import Dataset
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.core.representation import Representation


class _Adapter:
    """
    Class encapsulating _Adapter role.

    This class ``tests/unit/core/test_dataset_coverage.py`` within module _Adaptermanages its state and behavior together.
    Key methods: name, list_datasets, search_datasets, get_dataset, query_records.

    Property description:
        Properties defined in constructor and class body are reused by sub-methods in shared context.
    """

    @property
    def name(self) -> str:
        """
        name performs operation.

        Returns:
            str: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.
        """
        return "mock"

    def list_datasets(self) -> list[DatasetRef]:
        """
        list datasets performs operation.

        Returns:
            list[DatasetRef]: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.
        """
        return []

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """
        search datasets performs operation.

        Args:
            text (str): input value provided by caller.

        Returns:
            list[DatasetRef]: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.
        """
        return []

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """
        get dataset performs operation.

        Args:
            dataset_key (str): input value provided by caller.

        Returns:
            DatasetRef: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.
        """
        raise LookupError(dataset_key)

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """
        performs query records operation.

        Args:
            dataset (DatasetRef): input value provided by caller.
            query (Query): input value provided by caller.

        Returns:
            RecordBatch: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.
        """
        return RecordBatch(items=[], dataset=dataset)

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """
        get schema performs operation.

        Args:
            dataset (DatasetRef): input value provided by caller.

        Returns:
            SchemaDescriptor | None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.
        """
        return None

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """
        call raw performs operation.

        Args:
            dataset (DatasetRef): input value provided by caller.
            operation (str): input value provided by caller.
            params (dict[str, object]): input value provided by caller.

        Returns:
            object: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.
        """
        return None


# test ref property returns bound reference Explains scenario validated by test.
def test_ref_property_returns_bound_reference() -> None:
    """
    test ref property returns bound reference Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    ref = DatasetRef(
        id="mock.sample",
        provider="mock",
        dataset_key="sample",
        name="Sample",
        representation=Representation.API_JSON,
        operations=frozenset({Operation.LIST}),
    )
    dataset = Dataset(ref=ref, adapter=_Adapter())

    assert dataset.ref is ref


# test list all generator type Explains scenario validated by test.
def test_list_all_generator_type() -> None:
    """
    test list all generator type Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    ref = DatasetRef(
        id="mock.sample",
        provider="mock",
        dataset_key="sample",
        name="Sample",
        representation=Representation.API_JSON,
        operations=frozenset({Operation.LIST}),
    )
    dataset = Dataset(ref=ref, adapter=_Adapter())

    batches = dataset.list_all()

    assert hasattr(batches, "__iter__")
