"""Unit test module.

tests/unit/test_registry_coverage.py`` Defines test scenarios and helper objects.
Verifies core flows, exceptions, and edge conditions for regression prevention and public contract validation.
"""

from __future__ import annotations

from typing import Any

import pytest

from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.registry import ProviderRegistry


class _ValidAdapter:
    """
    _ValidAdapter Class encapsulating related operations.

    This class in ``tests/unit/test_registry_coverage.py`` module manages _ValidAdapterstate and behavior.
    Key methods: __init__, name, list_datasets, search_datasets, get_dataset.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    def __init__(self, provider_name: str) -> None:
        """
        Initialize internal state for the instance.

        Args:
            provider_name (str): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self._name: str = provider_name

    @property
    def name(self) -> str:
        """
        name Performs the operation.

        Returns:
            str: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return self._name

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


class _NameOnlyAdapter:
    """
    _NameOnlyAdapter Class encapsulating related operations.

    This class in ``tests/unit/test_registry_coverage.py`` module manages _NameOnlyAdapterstate and behavior.
    Key methods: none.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    name: str = "broken"


def _build_non_callable_adapter() -> Any:
    """
    Helper for build non callable adapter processing.

    Returns:
        Any: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.
    """
    return type(
        "BrokenAdapter",
        (),
        {
            "name": "ok",
            "list_datasets": None,
            "search_datasets": lambda self, text: [],
            "get_dataset": lambda self, dataset_key: None,
            "query_records": lambda self, dataset, query: None,
            "get_schema": lambda self, dataset: None,
            "call_raw": lambda self, dataset, operation, params: None,
        },
    )()


# test repr lists eager and lazy names Describes scenario being tested.
def test_repr_lists_eager_and_lazy_names() -> None:
    """
    test repr lists eager and lazy names Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    registry = ProviderRegistry()
    registry.register(_ValidAdapter("eager"))
    registry.register_lazy("lazy", lambda: _ValidAdapter("lazy"))

    rendered = repr(registry)

    assert rendered == "ProviderRegistry(eager=['eager'], lazy=['lazy'])"


# test register lazy rejects empty name Describes scenario being tested.
def test_register_lazy_rejects_empty_name() -> None:
    """
    test register lazy rejects empty name Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    registry = ProviderRegistry()

    with pytest.raises(ValueError, match="cannot be empty"):
        registry.register_lazy("   ", lambda: _ValidAdapter("x"))


# test register lazy rejects non callable factory Describes scenario being tested.
def test_register_lazy_rejects_non_callable_factory() -> None:
    """
    test register lazy rejects non callable factory Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    registry = ProviderRegistry()

    with pytest.raises(TypeError, match="must be callable"):
        registry.register_lazy("x", object())


# test register lazy rejects duplicate name Describes scenario being tested.
def test_register_lazy_rejects_duplicate_name() -> None:
    """
    test register lazy rejects duplicate name Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    registry = ProviderRegistry()
    registry.register_lazy("dup", lambda: _ValidAdapter("dup"))

    with pytest.raises(ValueError, match="already registered"):
        registry.register_lazy("dup", lambda: _ValidAdapter("dup"))


# test get rejects lazy adapter name mismatch Describes scenario being tested.
def test_get_rejects_lazy_adapter_name_mismatch() -> None:
    """
    test get rejects lazy adapter name mismatch Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    registry = ProviderRegistry()
    registry.register_lazy("expected", lambda: _ValidAdapter("actual"))

    with pytest.raises(TypeError, match="name mismatch"):
        registry.get("expected")


# test validate adapter rejects missing methods Describes scenario being tested.
def test_validate_adapter_rejects_missing_methods() -> None:
    """
    test validate adapter rejects missing methods Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    with pytest.raises(TypeError, match="missing required methods"):
        ProviderRegistry._validate_adapter(_NameOnlyAdapter())


# test validate adapter rejects non callable methods Describes scenario being tested.
def test_validate_adapter_rejects_non_callable_methods() -> None:
    """
    test validate adapter rejects non callable methods Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    with pytest.raises(TypeError, match="non-callable required methods"):
        ProviderRegistry._validate_adapter(_build_non_callable_adapter())
