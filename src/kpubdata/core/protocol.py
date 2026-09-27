"""Provider adapter protocol — KPubData's extension point."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor


@runtime_checkable
class ProviderAdapter(Protocol):
    """Protocol that all provider adapters must satisfy.

    Adapters are responsible for authentication, discovery, transformation,
    error mapping, raw access, and honest capability declaration.
    """

    requires_api_key: bool

    @property
    def name(self) -> str:
        """Return provider identifier (e.g., ``datago`` or ``seoul``)."""

        ...

    def list_datasets(self) -> list[DatasetRef]:
        """Return discoverable datasets from this provider."""

        ...

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """Return datasets matching free-text search in this provider."""

        ...

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """Interpret provider-local dataset key as canonical dataset reference."""

        ...

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """Execute canonical list/query request against dataset."""

        ...

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """Return canonical schema metadata if supported."""

        ...

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """Execute provider-specific operation and return unnormalized response."""

        ...


__all__ = ["ProviderAdapter"]
