"""Unit test module.

tests/unit/test_client_transport_requirements.py`` Defines test scenarios and helper objects.
Verifies core flows, exceptions, and edge conditions for regression prevention and public contract validation.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from kpubdata.client import Client
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.transport.cache import ResponseCache
from kpubdata.transport.http import HttpTransport, TransportRequirements


class _AdapterWithoutRequirements:
    """
    _AdapterWithoutRequirements Class encapsulating related operations.

    This class in ``tests/unit/test_client_transport_requirements.py`` module manages _AdapterWithoutRequirementsstate and behavior.
    Key methods: __init__, name, list_datasets, search_datasets, get_dataset.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    instances: list[object] = []

    def __init__(self, *, config: object, transport: HttpTransport) -> None:
        """
        Initialize internal state for the instance.

        Args:
            config (object): Input value provided by caller.
            transport (HttpTransport): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self.config: object = config
        self.transport: HttpTransport = transport
        type(self).instances.append(self)

    @property
    def name(self) -> str:
        """
        name Performs the operation.

        Returns:
            str: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return "dummy"

    def list_datasets(self) -> list[DatasetRef]:
        """
        list datasets Performs the operation.

        Returns:
            list[DatasetRef]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return []

    def search_datasets(self, _text: str) -> list[DatasetRef]:
        """
        search datasets Performs the operation.

        Args:
            _text (str): Input value provided by caller.

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

    def query_records(self, dataset: DatasetRef, _query: Query) -> RecordBatch:
        """
        query records Performs the operation.

        Args:
            dataset (DatasetRef): Input value provided by caller.
            _query (Query): Input value provided by caller.

        Returns:
            RecordBatch: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return RecordBatch(items=[], dataset=dataset)

    def get_schema(self, _dataset: DatasetRef) -> SchemaDescriptor | None:
        """
        get schema Performs the operation.

        Args:
            _dataset (DatasetRef): Input value provided by caller.

        Returns:
            SchemaDescriptor | None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return None

    def call_raw(self, _dataset: DatasetRef, _operation: str, _params: dict[str, object]) -> object:
        """
        call raw Performs the operation.

        Args:
            _dataset (DatasetRef): Input value provided by caller.
            _operation (str): Input value provided by caller.
            _params (dict[str, object]): Input value provided by caller.

        Returns:
            object: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return None


class _AdapterWithRequirements:
    """
    _AdapterWithRequirements Class encapsulating related operations.

    This class in ``tests/unit/test_client_transport_requirements.py`` module manages _AdapterWithRequirementsstate and behavior.
    Key methods: __init__, name, transport_requirements, list_datasets, search_datasets.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    instances: list[object] = []

    def __init__(self, *, config: object, transport: HttpTransport) -> None:
        """
        Initialize internal state for the instance.

        Args:
            config (object): Input value provided by caller.
            transport (HttpTransport): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self.config: object = config
        self.transport: HttpTransport = transport
        type(self).instances.append(self)

    @property
    def name(self) -> str:
        """
        name Performs the operation.

        Returns:
            str: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return "dummy"

    @property
    def transport_requirements(self) -> TransportRequirements | None:
        """
        transport requirements Performs the operation.

        Returns:
            TransportRequirements | None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return TransportRequirements(headers={"X-Provider": "dummy"}, verify_ssl=False)

    def list_datasets(self) -> list[DatasetRef]:
        """
        list datasets Performs the operation.

        Returns:
            list[DatasetRef]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return []

    def search_datasets(self, _text: str) -> list[DatasetRef]:
        """
        search datasets Performs the operation.

        Args:
            _text (str): Input value provided by caller.

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

    def query_records(self, dataset: DatasetRef, _query: Query) -> RecordBatch:
        """
        query records Performs the operation.

        Args:
            dataset (DatasetRef): Input value provided by caller.
            _query (Query): Input value provided by caller.

        Returns:
            RecordBatch: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return RecordBatch(items=[], dataset=dataset)

    def get_schema(self, _dataset: DatasetRef) -> SchemaDescriptor | None:
        """
        get schema Performs the operation.

        Args:
            _dataset (DatasetRef): Input value provided by caller.

        Returns:
            SchemaDescriptor | None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return None

    def call_raw(self, _dataset: DatasetRef, _operation: str, _params: dict[str, object]) -> object:
        """
        call raw Performs the operation.

        Args:
            _dataset (DatasetRef): Input value provided by caller.
            _operation (str): Input value provided by caller.
            _params (dict[str, object]): Input value provided by caller.

        Returns:
            object: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return None


# test builtin provider without transport requirements uses shared transport Describes scenario being tested.
def test_builtin_provider_without_transport_requirements_uses_shared_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    test builtin provider without transport requirements uses shared transport Verifies scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    _AdapterWithoutRequirements.instances.clear()
    monkeypatch.setattr(
        "kpubdata.bootstrap.BUILTIN_PROVIDERS", (("dummy", "dummy.module", "DummyAdapter"),)
    )

    with (
        patch(
            "importlib.import_module",
            return_value=SimpleNamespace(DummyAdapter=_AdapterWithoutRequirements),
        ),
        patch.object(HttpTransport, "with_requirements") as with_requirements,
    ):
        client = Client()
        _ = client.datasets.list()

    with_requirements.assert_not_called()
    assert len(_AdapterWithoutRequirements.instances) == 1


# test builtin provider with transport requirements builds custom transport Describes scenario being tested.
def test_builtin_provider_with_transport_requirements_builds_custom_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    test builtin provider with transport requirements builds custom transport Verifies scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    _AdapterWithRequirements.instances.clear()
    monkeypatch.setattr(
        "kpubdata.bootstrap.BUILTIN_PROVIDERS", (("dummy", "dummy.module", "DummyAdapter"),)
    )

    with patch(
        "importlib.import_module",
        return_value=SimpleNamespace(DummyAdapter=_AdapterWithRequirements),
    ):
        client = Client(timeout=12.0, max_retries=7)
        _ = client.datasets.list()

    adapter = _AdapterWithRequirements.instances[-1]
    assert isinstance(adapter, _AdapterWithRequirements)
    assert len(_AdapterWithRequirements.instances) == 2

    with patch("kpubdata.transport.http.httpx.Client") as client_cls:
        _ = adapter.transport.client

    client_cls.assert_called_once_with(
        timeout=12.0,
        headers={"X-Provider": "dummy"},
        follow_redirects=True,
        verify=False,
    )


# test custom transport inherits cache settings Describes scenario being tested.
def test_custom_transport_inherits_cache_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    test custom transport inherits cache settings Verifies scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.
        tmp_path (Path): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    _AdapterWithRequirements.instances.clear()
    monkeypatch.setattr(
        "kpubdata.bootstrap.BUILTIN_PROVIDERS", (("dummy", "dummy.module", "DummyAdapter"),)
    )
    cache = ResponseCache(base_dir=tmp_path)

    with patch(
        "importlib.import_module",
        return_value=SimpleNamespace(DummyAdapter=_AdapterWithRequirements),
    ):
        client = Client(cache=cache, cache_ttl_seconds=123)
        _ = client.datasets.list()

    adapter = _AdapterWithRequirements.instances[-1]
    assert isinstance(adapter, _AdapterWithRequirements)
    assert adapter.transport.cache is cache
    assert adapter.transport.cache_ttl_seconds == 123
