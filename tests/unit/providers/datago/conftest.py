"""Test module.

This file defines test scenarios and helper objects for the
tests/unit/providers/datago/conftest.py path. It validates core flows,
exceptions, and edge conditions to prevent regressions and verify the
public contract.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.transport.http import HttpTransport


def fixture_path(name: str) -> Path:
    """Return the fixture file path.

    Args:
        name (str): Fixture file name.

    Returns:
        Path: Resolved path to the fixture file.

    Raises:
        Any exceptions raised by underlying dependencies are propagated.
    """
    return Path(__file__).resolve().parents[3] / "fixtures" / "datago" / name


def load_json_fixture(name: str) -> dict[str, object]:
    """Load JSON fixture file and return as dict.

    Args:
        name (str): Fixture file name.

    Returns:
        dict[str, object]: Parsed JSON object from fixture.

    Raises:
        ValueError: If fixture does not contain a JSON object.
        Any exceptions raised by underlying dependencies are propagated.
    """
    payload = cast(object, json.loads(fixture_path(name).read_text(encoding="utf-8")))
    if isinstance(payload, dict):
        return cast(dict[str, object], payload)
    raise ValueError(f"Fixture must contain a JSON object: {name}")


def load_fixture_bytes(name: str) -> bytes:
    """Load fixture file as bytes.

    Args:
        name (str): Fixture file name.

    Returns:
        bytes: Raw bytes from fixture file.

    Raises:
        Any exceptions raised by underlying dependencies are propagated.
    """
    return fixture_path(name).read_bytes()


class FakeResponse:
    """Mock HTTP response object for testing.

    This class simulates an HTTP response with headers and content for
    use in unit tests without making actual network requests.
    """

    def __init__(self, data: bytes, content_type: str = "application/json") -> None:
        """Initialize FakeResponse with data and content type.

        Args:
            data (bytes): Response body as bytes.
            content_type (str): Content-Type header value.
        """
        self.headers: dict[str, str] = {"content-type": content_type}
        self.content: bytes = data
        self.text: str = data.decode("utf-8")


class FixtureTransport:
    """Mock HTTP transport for testing with fixture responses.

    Stores a queue of fixture-based responses and records all requests
    for assertion in tests.
    """

    def __init__(self, fixture_names: list[str], content_type: str = "application/json") -> None:
        """Initialize FixtureTransport with fixture names.

        Args:
            fixture_names (list[str]): List of fixture file names.
            content_type (str): Content-Type header for all responses.
        """
        self._responses: list[FakeResponse] = [
            FakeResponse(load_fixture_bytes(name), content_type=content_type)
            for name in fixture_names
        ]
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        """Execute a mocked HTTP request.

        Args:
            method (str): HTTP method name.
            url (str): Request URL.
            **kwargs (object): Additional request parameters.

        Returns:
            FakeResponse: Next fixture response from the queue.

        Raises:
            AssertionError: If no fixture responses remain.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No fixture responses remaining")
        return self._responses.pop(0)


@pytest.fixture
def configured_adapter() -> Callable[
    [list[str], str], tuple[DataGoAdapter, DatasetRef, FixtureTransport]
]:
    """Factory fixture providing a pre-configured DataGoAdapter instance.

    Returns:
        Callable: A callable that builds an adapter with given fixtures.
    """

    def _build(
        fixture_names: list[str],
        content_type: str = "application/json",
    ) -> tuple[DataGoAdapter, DatasetRef, FixtureTransport]:
        """Build adapter with fixture transport.

        Args:
            fixture_names (list[str]): List of fixture file names.
            content_type (str): Content-Type for all responses.

        Returns:
            tuple: (adapter, dataset, transport) triple.
        """
        transport = FixtureTransport(fixture_names=fixture_names, content_type=content_type)
        config = KPubDataConfig(provider_keys={"datago": "test-key"})
        adapter = DataGoAdapter(
            config=config,
            transport=cast(HttpTransport, cast(object, transport)),
        )
        dataset = adapter.get_dataset("metro_fare")
        return adapter, dataset, transport

    return _build
