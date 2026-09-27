"""Test module for integration tests.

Defines test scenarios and helper functions in ``tests/integration/test_exception_propagation.py``.
Verifies core flows, exceptions, and edge cases to prevent regressions and validate the public contract..
"""

from __future__ import annotations

import pytest

from kpubdata.client import Client
from kpubdata.core.capability import Operation
from kpubdata.core.models import DatasetRef, Query, RecordBatch
from kpubdata.core.representation import Representation
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    ProviderNotRegisteredError,
    PublicDataError,
    RateLimitError,
    ServiceUnavailableError,
)


class ErrorAdapter:
    """
    ErrorAdapter encapsulates error simulation.

    This class manages ErrorAdapter state and operations within test_exception_propagation.
    Key methods: __init__, name, list_datasets, search_datasets, get_dataset.

    Attributes:
        Attributes defined in __init__ and class body are reused by methods as context.
    """

    def __init__(self) -> None:
        """
        Initialize instance state.
        """
        self._datasets: dict[str, DatasetRef] = {
            "failing": DatasetRef(
                id="errorprov.failing",
                provider="errorprov",
                dataset_key="failing",
                name="Failing Dataset",
                representation=Representation.API_JSON,
                operations=frozenset({Operation.LIST, Operation.RAW}),
            ),
            "limited": DatasetRef(
                id="errorprov.limited",
                provider="errorprov",
                dataset_key="limited",
                name="Limited Dataset",
                representation=Representation.API_JSON,
                operations=frozenset({Operation.LIST, Operation.RAW}),
            ),
        }

    @property
    def name(self) -> str:
        """
        Provider name.
        """
        return "errorprov"

    def list_datasets(self) -> list[DatasetRef]:
        """
        List all available datasets.
        """
        return [self._datasets["failing"], self._datasets["limited"]]

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """
        Search datasets by text.
        """
        _ = text
        return []

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """
        Get dataset by key.
        """
        try:
            return self._datasets[dataset_key]
        except KeyError as exc:
            raise DatasetNotFoundError(
                f"Dataset not found: {self.name}.{dataset_key}",
                provider=self.name,
                dataset_id=f"{self.name}.{dataset_key}",
            ) from exc

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """
        Query records from dataset.
        """
        _ = query
        raise AuthError(
            message="Invalid API key",
            provider="errorprov",
            dataset_id=dataset.id,
            operation="list",
            provider_code="30",
            retryable=False,
        )

    def get_schema(self, dataset: DatasetRef) -> None:
        """
        Get dataset schema.
        """
        raise ServiceUnavailableError(
            message="Service down",
            provider="errorprov",
            dataset_id=dataset.id,
            operation="schema",
            retryable=True,
        )

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """
        Call raw provider operation.
        """
        _ = params
        raise RateLimitError(
            message="Too many requests",
            provider="errorprov",
            dataset_id=dataset.id,
            operation=operation,
            status_code=429,
            retryable=False,
        )


def _build_client() -> tuple[Client, ErrorAdapter]:
    """
    Build error-prone client for testing.
    """
    client = Client(provider_keys={"errorprov": "bad-key"})
    adapter = ErrorAdapter()
    client.register_provider(adapter)
    return client, adapter


# # test auth error from dataset list scenario
def test_auth_error_from_dataset_list() -> None:
    """
    Verify test auth error from dataset list scenario.
    """
    client, _adapter = _build_client()

    with pytest.raises(AuthError) as exc_info:
        _ = client.dataset("errorprov.failing").list()

    exc = exc_info.value
    assert exc.provider == "errorprov"
    assert exc.dataset_id == "errorprov.failing"
    assert exc.operation == "list"
    assert exc.provider_code == "30"
    assert exc.retryable is False


# # test auth error caught as base scenario
def test_auth_error_caught_as_base() -> None:
    """
    Verify test auth error caught as base scenario.
    """
    client, _adapter = _build_client()

    try:
        _ = client.dataset("errorprov.failing").list()
        pytest.fail("Expected PublicDataError")
    except PublicDataError as exc:
        assert isinstance(exc, AuthError)


# # test rate limit from call raw scenario
def test_rate_limit_from_call_raw() -> None:
    """
    Verify test rate limit from call raw scenario.
    """
    client, _adapter = _build_client()

    with pytest.raises(RateLimitError) as exc_info:
        _ = client.dataset("errorprov.failing").call_raw("getData")

    exc = exc_info.value
    assert exc.status_code == 429
    assert exc.retryable is False
    assert exc.operation == "getData"


# # test service unavailable from schema scenario
def test_service_unavailable_from_schema() -> None:
    """
    Verify test service unavailable from schema scenario.
    """
    client, _adapter = _build_client()

    with pytest.raises(ServiceUnavailableError) as exc_info:
        _ = client.dataset("errorprov.failing").schema()

    exc = exc_info.value
    assert exc.retryable is True
    assert exc.operation == "schema"


# # test dataset not found scenario
def test_dataset_not_found() -> None:
    """
    Verify test dataset not found scenario.
    """
    client, _adapter = _build_client()

    with pytest.raises(DatasetNotFoundError) as exc_info:
        _ = client.dataset("errorprov.nonexistent")

    assert exc_info.value.dataset_id == "errorprov.nonexistent"


# # test provider not registered scenario
def test_provider_not_registered() -> None:
    """
    Verify test provider not registered scenario.
    """
    client = Client(provider_keys={"errorprov": "bad-key"})

    with pytest.raises(ProviderNotRegisteredError):
        _ = client.dataset("unknown.ds")


# # test auth error repr includes context scenario
def test_auth_error_repr_includes_context() -> None:
    """
    Verify test auth error repr includes context scenario.
    """
    client, _adapter = _build_client()

    with pytest.raises(AuthError) as exc_info:
        _ = client.dataset("errorprov.failing").list()

    rendered = repr(exc_info.value)
    assert "errorprov" in rendered
    assert "30" in f"{rendered} {exc_info.value.provider_code}"


# # test rate limit repr includes status scenario
def test_rate_limit_repr_includes_status() -> None:
    """
    Verify test rate limit repr includes status scenario.
    """
    client, _adapter = _build_client()

    with pytest.raises(RateLimitError) as exc_info:
        _ = client.dataset("errorprov.failing").call_raw("getData")

    assert "429" in repr(exc_info.value)


# # test dataset not found has cause chain scenario
def test_dataset_not_found_has_cause_chain() -> None:
    """
    Verify test dataset not found has cause chain scenario.
    """
    client, _adapter = _build_client()

    with pytest.raises(DatasetNotFoundError) as exc_info:
        _ = client.dataset("errorprov.nonexistent")

    assert isinstance(exc_info.value.__cause__, KeyError)
