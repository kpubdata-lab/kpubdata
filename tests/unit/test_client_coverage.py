"""Unit test module.

tests/unit/test_client_coverage.py`` Defines test scenarios and helper objects.
Verifies core flows, exceptions, and edge conditions for regression prevention and public contract validation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from kpubdata.client import Client
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor


class _Adapter:
    """
    _Adapter Class encapsulating related operations.

    This class in ``tests/unit/test_client_coverage.py`` module manages _Adapterstate and behavior.
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


# test enter delegates to transport and returns self Describes scenario being tested.
def test_enter_delegates_to_transport_and_returns_self() -> None:
    """
    test enter delegates to transport and returns self Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = Client()
    transport = MagicMock()
    client._transport = transport

    entered = client.__enter__()

    transport.__enter__.assert_called_once_with()
    assert entered is client


# test close delegates to transport close Describes scenario being tested.
def test_close_delegates_to_transport_close() -> None:
    """
    test close delegates to transport close Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = Client()
    transport = MagicMock()
    client._transport = transport

    client.close()

    transport.close.assert_called_once_with()


# test exit calls close Describes scenario being tested.
def test_exit_calls_close() -> None:
    """
    test exit calls close Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = Client()
    client.close = MagicMock()

    client.__exit__(None, None, None)

    client.close.assert_called_once_with()


# test repr includes registered provider names Describes scenario being tested.
def test_repr_includes_registered_provider_names() -> None:
    """
    test repr includes registered provider names Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = Client()
    client.register_provider(_Adapter())

    rendered = repr(client)

    assert "alpha" in rendered
    assert "datago" in rendered
    assert "bok" in rendered
    assert "kosis" in rendered


# test builtin providers registered by default Describes scenario being tested.
def test_builtin_providers_registered_by_default() -> None:
    """
    test builtin providers registered by default Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = Client()

    assert "datago" in client._registry
    assert "bok" in client._registry
    assert "kosis" in client._registry


# test builtin providers datasets discoverable Describes scenario being tested.
def test_builtin_providers_datasets_discoverable() -> None:
    """
    test builtin providers datasets discoverable Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = Client()

    datasets = client.datasets.list()

    assert len(datasets) > 0
    provider_names = {ds.provider for ds in datasets}
    assert "datago" in provider_names
    assert "bok" in provider_names
    assert "kosis" in provider_names


# test builtin dataset binding works Describes scenario being tested.
def test_builtin_dataset_binding_works() -> None:
    """
    test builtin dataset binding works Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = Client()

    ds = client.dataset("datago.village_fcst")

    assert ds.id == "datago.village_fcst"
    assert ds.provider == "datago"


# test user adapter overrides builtin Describes scenario being tested.
def test_user_adapter_overrides_builtin() -> None:
    """
    test user adapter overrides builtin Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """

    class _DatagoOverride(_Adapter):
        """
        _DatagoOverride Class encapsulating related operations.

        This class in ``tests/unit/test_client_coverage.py`` module manages _DatagoOverridestate and behavior.
        Key methods: name.

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
            return "datago"

    client = Client()
    client._registry._lazy.pop("datago", None)
    client.register_provider(_DatagoOverride())

    adapter = client._registry.get("datago")
    assert isinstance(adapter, _DatagoOverride)
