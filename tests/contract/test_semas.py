"""Test module.

This file defines test scenarios and helper objects in the
``tests/contract/test_semas.py`` path. It verifies core flows, exceptions,
and edge conditions for regression prevention and public contract validation.
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
    Internal helper that handles fixture path resolution.

    Args:
        name (str): The input value provided by the caller.

    Returns:
        Path: The computed result or the return value from downstream calls.

    Raises:
        Exception from internal implementation or downstream dependencies
        can be raised as-is.
    """
    return Path(__file__).resolve().parents[1] / "fixtures" / "semas" / name


def _load_fixture_bytes(name: str) -> bytes:
    """
    Internal helper that handles loading fixture bytes.

    Args:
        name (str): The input value provided by the caller.

    Returns:
        bytes: The computed result or the return value from downstream calls.

    Raises:
        Exception from internal implementation or downstream dependencies
        can be raised as-is.
    """
    return _fixture_path(name).read_bytes()


class _FakeResponse:
    """
    Class that encapsulates roles related to _FakeResponse.

    This class manages state and behavior of _FakeResponse within the
    ``tests/contract/test_semas.py`` module.
    Key method: __init__.

    Attribute description:
        Properties defined in the constructor and class body are reused
        as shared context by downstream methods.
    """

    def __init__(self, data: bytes, content_type: str = "application/json") -> None:
        """
        Initialize instance state for internal use.

        Args:
            data (bytes): The input value provided by the caller.
            content_type (str): The input value provided by the caller.

        Returns:
            None: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        self.headers: dict[str, str] = {"content-type": content_type}
        self.content: bytes = data
        self.text: str = data.decode("utf-8")


class _FixtureTransport:
    """
    Class that encapsulates roles related to _FixtureTransport.

    This class manages state and behavior of _FixtureTransport within the
    ``tests/contract/test_semas.py`` module.
    Key methods: __init__, request.

    Attribute description:
        Properties defined in the constructor and class body are reused
        as shared context by downstream methods.
    """

    def __init__(self, fixture_names: list[str]) -> None:
        """
        Initialize instance state for internal use.

        Args:
            fixture_names (list[str]): The input value provided by the caller.

        Returns:
            None: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        self._responses: list[_FakeResponse] = [
            _FakeResponse(_load_fixture_bytes(name)) for name in fixture_names
        ]

    def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        """
        Perform request operation.

        Args:
            method (str): The input value provided by the caller.
            url (str): The input value provided by the caller.
            **kwargs (object): The input value provided by the caller.

        Returns:
            _FakeResponse: The computed result or the return value from
            downstream calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        _ = method, url, kwargs
        if not self._responses:
            raise AssertionError("No fixture responses remaining")
        return self._responses.pop(0)


class _AdapterFactory(Protocol):
    """
    Class that encapsulates roles related to _AdapterFactory.

    This class manages state and behavior of _AdapterFactory within the
    ``tests/contract/test_semas.py`` module.
    Key method: __call__.

    Attribute description:
        Properties defined in the constructor and class body are reused
        as shared context by downstream methods.
    """

    def __call__(
        self,
        *,
        config: KPubDataConfig | None = None,
        transport: HttpTransport | None = None,
    ) -> ProviderAdapter: ...


def _build_adapter(fixture_names: list[str]) -> ProviderAdapter:
    """
    Internal helper that handles adapter building.

    Args:
        fixture_names (list[str]): The input value provided by the caller.

    Returns:
        ProviderAdapter: The computed result or the return value from
        downstream calls.

    Raises:
        Exception from internal implementation or downstream dependencies
        can be raised as-is.
    """
    transport = _FixtureTransport(fixture_names)
    config = KPubDataConfig(provider_keys={"datago": "test-key"})
    adapter_module = import_module("kpubdata.providers.semas.adapter")
    adapter_class_obj = cast(object, adapter_module.SemasAdapter)
    if not isinstance(adapter_class_obj, type):
        raise AssertionError("SemasAdapter is not a class")
    adapter_class = cast(_AdapterFactory, adapter_class_obj)
    return adapter_class(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )


class TestSemasAdapterContract(ProviderAdapterContract):
    """
    Class that encapsulates roles related to TestSemasAdapterContract.

    This class manages state and behavior of TestSemasAdapterContract within
    the ``tests/contract/test_semas.py`` module.
    Key methods: adapter, valid_dataset_key, invalid_dataset_key,
    sample_dataset, sample_query.

    Attribute description:
        Properties defined in the constructor and class body are reused
        as shared context by downstream methods.
    """

    @pytest.fixture()
    def adapter(self) -> ProviderAdapter:
        """
        Perform adapter operation.

        Returns:
            ProviderAdapter: The computed result or the return value from
            downstream calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return _build_adapter(["store_one_success.json", "store_one_success.json"])

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        """
        Perform valid dataset key operation.

        Returns:
            str: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return "store_one"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        """
        inPerform valid dataset key operation.

        Returns:
            str: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: ProviderAdapter) -> DatasetRef:
        """
        Perform sample dataset operation.

        Args:
            adapter (ProviderAdapter): The input value provided by the caller.

        Returns:
            DatasetRef: The computed result or the return value from
            downstream calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return adapter.get_dataset("store_one")

    @pytest.fixture()
    def sample_query(self) -> Query:
        """
        Perform sample query operation.

        Returns:
            Query: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return Query(filters={"bizesId": "S001"})

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        """
        Perform raw operation operation.

        Returns:
            tuple[str, dict[str, object]]: The computed result or the return
            value from downstream calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return ("storeOne", {"bizesId": "S001"})
