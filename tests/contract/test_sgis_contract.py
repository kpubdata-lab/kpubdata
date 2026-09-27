"""Test module.

This file defines test scenarios and helper objects in the
``tests/contract/test_sgis_contract.py`` path. It verifies core flows,
exceptions, and edge conditions for regression prevention and public contract
validation.
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
    return Path(__file__).resolve().parents[1] / "fixtures" / "sgis" / name


class _FakeResponse:
    """
    Class that encapsulates roles related to _FakeResponse.

    This class manages state and behavior of _FakeResponse within the
    ``tests/contract/test_sgis_contract.py`` module.
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
    ``tests/contract/test_sgis_contract.py`` module.
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
            _FakeResponse(_fixture_path(name).read_bytes()) for name in fixture_names
        ]

    def request(self, _method: str, _url: str, **_kwargs: object) -> _FakeResponse:
        """
        Perform request operation.

        Args:
            _method (str): The input value provided by the caller.
            _url (str): The input value provided by the caller.
            **_kwargs (object): The input value provided by the caller.

        Returns:
            _FakeResponse: The computed result or the return value from
            downstream calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        if not self._responses:
            raise AssertionError("No fixture responses remaining")
        return self._responses.pop(0)


class _FixtureAuthClient:
    """
    Class that encapsulates roles related to _FixtureAuthClient.

    This class manages state and behavior of _FixtureAuthClient within the
    ``tests/contract/test_sgis_contract.py`` module.
    Key methods: get_access_token, invalidate.

    Attribute description:
        Properties defined in the constructor and class body are reused
        as shared context by downstream methods.
    """

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        """
        Perform get access token operation.

        Args:
            force_refresh (bool): The input value provided by the caller.

        Returns:
            str: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        _ = force_refresh
        return "contract-token"

    def invalidate(self) -> None:
        """
        Perform invalidate operation.

        Returns:
            None: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return None


class _SgisAdapterFactory(Protocol):
    """
    Class that encapsulates roles related to _SgisAdapterFactory.

    This class manages state and behavior of _SgisAdapterFactory within the
    ``tests/contract/test_sgis_contract.py`` module.
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
        auth_client: object = None,
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
    config = KPubDataConfig(provider_keys={"sgis": "consumer-key:consumer-secret"})
    adapter_module = import_module("kpubdata.providers.sgis.adapter")
    adapter_class_obj = cast(object, adapter_module.SgisAdapter)
    if not isinstance(adapter_class_obj, type):
        raise AssertionError("SgisAdapter is not a class")
    adapter_class = cast(_SgisAdapterFactory, adapter_class_obj)
    return adapter_class(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
        auth_client=_FixtureAuthClient(),
    )


class TestSgisAdapterContract(ProviderAdapterContract):
    """
    Class that encapsulates roles related to TestSgisAdapterContract.

    This class manages state and behavior of TestSgisAdapterContract within
    the ``tests/contract/test_sgis_contract.py`` module.
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
        return _build_adapter(["sido_boundary.geojson"] * 5)

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
        return "boundary.sido"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        """
        Perform invalid dataset key operation.

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
        return adapter.get_dataset("boundary.sido")

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
        return Query(filters={"year": "2023", "low_search": 1})

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
        return ("list", {"year": "2023", "low_search": 1})
