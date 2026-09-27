"""Test module.

This file defines test scenarios and helper objects in the
``tests/contract/test_lofin.py`` path. It verifies core flows, exceptions,
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
from kpubdata.exceptions import AuthError
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
    return Path(__file__).resolve().parents[1] / "fixtures" / "lofin" / name


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
    ``tests/contract/test_lofin.py`` module.
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
    ``tests/contract/test_lofin.py`` module.
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
    ``tests/contract/test_lofin.py`` module.
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
    adapter_module = import_module("kpubdata.providers.lofin.adapter")
    adapter_class_obj = cast(object, adapter_module.LofinAdapter)
    if not isinstance(adapter_class_obj, type):
        raise AssertionError("LofinAdapter is not a class")
    adapter_class = cast(_AdapterFactory, adapter_class_obj)
    adapter_obj = adapter_class(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter_obj


class TestLofinAdapterContract(ProviderAdapterContract):
    """
    Class that encapsulates roles related to TestLofinAdapterContract.

    This class manages state and behavior of TestLofinAdapterContract within
    the ``tests/contract/test_lofin.py`` module.
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
        return _build_adapter(["success_single_page.json"] * 5)

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
        return "expenditure_budget"

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
        return adapter.get_dataset("expenditure_budget")

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
        return Query()

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
        return ("list", {"pIndex": "1", "pSize": "10"})

    # test query records uses lofin365 url and key param - Verifies the scenario tested by this method.
    def test_query_records_uses_lofin365_url_and_key_param(self) -> None:
        """
        Verify test query records uses lofin365 url and key param scenario.

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
        transport = _FixtureTransport(["success_single_page.json"])
        config = KPubDataConfig(provider_keys={"datago": "test-key"})
        adapter_module = import_module("kpubdata.providers.lofin.adapter")
        adapter_class_obj = cast(object, adapter_module.LofinAdapter)
        if not isinstance(adapter_class_obj, type):
            raise AssertionError("LofinAdapter is not a class")
        adapter_class = cast(_AdapterFactory, adapter_class_obj)
        adapter = adapter_class(
            config=config,
            transport=cast(HttpTransport, cast(object, transport)),
        )

        dataset = adapter.get_dataset("expenditure_budget")
        _ = adapter.query_records(dataset, Query())

        request_url = cast(str, transport.calls[0]["url"])
        assert request_url.startswith("https://www.lofin365.go.kr/lf/hub/AJGCF")
        assert "?Key=test-key&Type=json&pIndex=1&pSize=100" in request_url

    # test query records handles top level auth error - Verifies the scenario tested by this method.
    def test_query_records_handles_top_level_auth_error(self) -> None:
        """
        Verify test query records handles top level auth error scenario.

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
        transport = _FixtureTransport(["error_auth.json"])
        config = KPubDataConfig(provider_keys={"datago": "invalid-key"})
        adapter_module = import_module("kpubdata.providers.lofin.adapter")
        adapter_class_obj = cast(object, adapter_module.LofinAdapter)
        if not isinstance(adapter_class_obj, type):
            raise AssertionError("LofinAdapter is not a class")
        adapter_class = cast(_AdapterFactory, adapter_class_obj)
        adapter = adapter_class(
            config=config,
            transport=cast(HttpTransport, cast(object, transport)),
        )

        dataset = adapter.get_dataset("expenditure_budget")
        with pytest.raises(AuthError) as exc_info:
            _ = adapter.query_records(dataset, Query())

        assert exc_info.value.provider_code == "ERROR-290"

    # test query records fiacrv dataset - Verifies the scenario tested by this method.
    def test_query_records_fiacrv_dataset(self) -> None:
        """
        Verify test query records fiacrv dataset scenario.

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
        transport = _FixtureTransport(["success_fiacrv.json"])
        config = KPubDataConfig(provider_keys={"datago": "test-key"})
        adapter_module = import_module("kpubdata.providers.lofin.adapter")
        adapter_class_obj = cast(object, adapter_module.LofinAdapter)
        if not isinstance(adapter_class_obj, type):
            raise AssertionError("LofinAdapter is not a class")
        adapter_class = cast(_AdapterFactory, adapter_class_obj)
        adapter = adapter_class(
            config=config,
            transport=cast(HttpTransport, cast(object, transport)),
        )

        dataset = adapter.get_dataset("revenue_by_source")
        result = adapter.query_records(dataset, Query())

        assert result.total_count == 2
        assert len(result.items) == 2
        assert result.items[0]["armk_nm"] == "총괄"
        assert result.items[1]["armk_nm"] == "지방세수입"

        request_url = cast(str, transport.calls[0]["url"])
        assert "FIACRV" in request_url
