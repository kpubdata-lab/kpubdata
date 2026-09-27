"""Composite Provider bridge — merges legacy adapters and spec executors into one.

Integration layer for the spec system (#378). Unifies two worlds registered under
the same Provider name (catalog-based built-in adapter / declarative spec executor)
under a single ``ProviderAdapter`` surface.

Merge rules:
- If the same ``dataset_key`` exists in both, **spec wins** (during cutover, spec
  becomes the single source of truth for that dataset).
- Spec-only keys are added at the end of the list.
- Catalog-only keys are handled by the legacy adapter (coexist).

After cutover is complete, the Provider's catalog entry is removed and only this
bridge remains.
"""

from __future__ import annotations

import logging

from kpubdata.core.executor import SpecDatasetAdapter
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.core.protocol import ProviderAdapter

logger = logging.getLogger("kpubdata.core.bridge")


class CompositeProviderAdapter:
    """Built-in adapter and spec adapter merged spec-first."""

    def __init__(self, inner: ProviderAdapter, spec_adapter: SpecDatasetAdapter) -> None:
        """Initialize the composite adapter from two adapters.

        Args:
            inner: The built-in (catalog-based) adapter.
            spec_adapter: The spec executor adapter.

        Raises:
            ValueError: If the two adapters have different Provider names.
        """
        if inner.name != spec_adapter.name:
            msg = (
                f"CompositeProviderAdapter는 같은 Provider만 병합할 수 있습니다: "
                f"{inner.name!r} vs {spec_adapter.name!r}"
            )
            raise ValueError(msg)
        self._inner = inner
        self._spec = spec_adapter
        self.requires_api_key: bool = bool(
            getattr(inner, "requires_api_key", False) or spec_adapter.requires_api_key
        )

    @property
    def name(self) -> str:
        """Return the Provider identifier (shared by both adapters)."""
        return self._inner.name

    def _spec_owns(self, dataset_key: str) -> bool:
        """Return whether this key is owned by spec."""
        try:
            self._spec.get_dataset(dataset_key)
        except Exception:
            return False
        return True

    def list_datasets(self) -> list[DatasetRef]:
        """Return catalog + spec datasets without key duplication (spec first)."""
        spec_refs = {ref.dataset_key: ref for ref in self._spec.list_datasets()}
        merged: list[DatasetRef] = []
        seen: set[str] = set()
        for ref in self._inner.list_datasets():
            if ref.dataset_key in spec_refs:
                merged.append(spec_refs[ref.dataset_key])
                seen.add(ref.dataset_key)
            else:
                merged.append(ref)
        for key, ref in spec_refs.items():
            if key not in seen:
                merged.append(ref)
        return merged

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """Merge search results from both without key duplication (spec first)."""
        spec_matches = {ref.dataset_key: ref for ref in self._spec.search_datasets(text)}
        merged: list[DatasetRef] = []
        seen: set[str] = set()
        for ref in self._inner.search_datasets(text):
            if ref.dataset_key in spec_matches:
                merged.append(spec_matches[ref.dataset_key])
                seen.add(ref.dataset_key)
            else:
                merged.append(ref)
        for key, ref in spec_matches.items():
            if key not in seen:
                merged.append(ref)
        return merged

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """Resolve dataset key (spec first, fallback to built-in adapter)."""
        if self._spec_owns(dataset_key):
            return self._spec.get_dataset(dataset_key)
        return self._inner.get_dataset(dataset_key)

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """Delegate query to spec executor or built-in adapter by ownership."""
        if self._spec_owns(dataset.dataset_key):
            logger.debug(
                "Routing dataset query to spec executor",
                extra={"dataset_id": dataset.id, "provider": self.name},
            )
            return self._spec.query_records(dataset, query)
        return self._inner.query_records(dataset, query)

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """Delegate schema metadata query by ownership."""
        if self._spec_owns(dataset.dataset_key):
            return self._spec.get_schema(dataset)
        return self._inner.get_schema(dataset)

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """Delegate raw operation by ownership (escape hatch guaranteed)."""
        if self._spec_owns(dataset.dataset_key):
            return self._spec.call_raw(dataset, operation, params)
        return self._inner.call_raw(dataset, operation, params)

    @property
    def inner(self) -> ProviderAdapter:
        """Return the wrapped built-in adapter (for debugging/testing)."""
        return self._inner

    @property
    def spec_adapter(self) -> SpecDatasetAdapter:
        """Return the wrapped spec adapter (for debugging/testing)."""
        return self._spec


__all__ = ["CompositeProviderAdapter"]
