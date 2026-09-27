"""Test module.

This file defines test scenarios and helper objects in the
``tests/contract/test_law.py`` path. It verifies core flows, exceptions, and
edge conditions for regression prevention and public contract validation.
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
    return Path(__file__).resolve().parents[1] / "fixtures" / "law" / name


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
    ``tests/contract/test_law.py`` module.
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
    ``tests/contract/test_law.py`` module.
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
        self.calls: list[dict[str, object]] = []

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
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No fixture responses remaining")
        return self._responses.pop(0)


class _AdapterFactory(Protocol):
    """
    Class that encapsulates roles related to _AdapterFactory.

    This class manages state and behavior of _AdapterFactory within the
    ``tests/contract/test_law.py`` module.
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


def _build_adapter(fixture_names: list[str]) -> tuple[ProviderAdapter, _FixtureTransport]:
    """
    Internal helper that handles adapter building.

    Args:
        fixture_names (list[str]): The input value provided by the caller.

    Returns:
        tuple[ProviderAdapter, _FixtureTransport]: The computed result or
        the return value from downstream calls.

    Raises:
        Exception from internal implementation or downstream dependencies
        can be raised as-is.
    """
    transport = _FixtureTransport(fixture_names)
    config = KPubDataConfig(provider_keys={"law": "test-law-key"})
    adapter_module = import_module("kpubdata.providers.law.adapter")
    adapter_class_obj = cast(object, adapter_module.LawAdapter)
    adapter_class = cast(_AdapterFactory, adapter_class_obj)
    adapter = adapter_class(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter, transport


class TestLawAdapterContract(ProviderAdapterContract):
    """
    Class that encapsulates roles related to TestLawAdapterContract.

    This class manages state and behavior of TestLawAdapterContract within
    the ``tests/contract/test_law.py`` module.
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
        adapter, _ = _build_adapter(["success_law_search.json"] * 5)
        return adapter

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
        return "law_search"

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
        return adapter.get_dataset("law_search")

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
        return Query(filters={"query": "임대차", "search": "1"})

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
        return ("lawSearch", {"query": "임대차", "search": "1"})

    # test query records uses law search url and oc param - Verifies the scenario tested by this method.
    def test_query_records_uses_law_search_url_and_oc_param(self) -> None:
        """
        Verify test query records uses law search url and oc param scenario.

        Returns:
            None: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.

        Example:
            Ensures the expected behavior described by the test name is
            maintained without regression.
        """
        adapter, transport = _build_adapter(["success_law_search.json"])

        dataset = adapter.get_dataset("law_search")
        _ = adapter.query_records(dataset, Query())

        request_url = cast(str, transport.calls[0]["url"])
        assert request_url.startswith("http://www.law.go.kr/DRF/lawSearch.do?")
        assert "OC=test-law-key" in request_url
        assert "target=law" in request_url
        assert "type=JSON" in request_url
        assert "display=100" in request_url
        assert "page=1" in request_url

    # test call raw supports law detail endpoint - Verifies the scenario tested by this method.
    def test_call_raw_supports_law_detail_endpoint(self) -> None:
        """
        Verify test call raw supports law detail endpoint scenario.

        Returns:
            None: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.

        Example:
            Ensures the expected behavior described by the test name is
            maintained without regression.
        """
        adapter, transport = _build_adapter(["success_law_detail.json"])

        dataset = adapter.get_dataset("law_detail")
        raw = adapter.call_raw(dataset, "lawService", {"MST": "17523"})

        request_url = cast(str, transport.calls[0]["url"])
        assert isinstance(raw, dict)
        assert "법령정보" in raw
        assert request_url.startswith("http://www.law.go.kr/DRF/lawService.do?")
        assert "MST=17523" in request_url
