"""Provider adapter registry with registration-time validation.

Verifies at registration time — not call time — that a registered adapter
satisfies the ProviderAdapter protocol.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from threading import RLock

from kpubdata.core.models import DatasetRef
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.exceptions import CapabilityContractError, ProviderNotRegisteredError

logger = logging.getLogger("kpubdata.registry")

_REQUIRED_METHODS = (
    "list_datasets",
    "search_datasets",
    "get_dataset",
    "query_records",
    "get_schema",
    "call_raw",
)


class ProviderRegistry:
    """Thread-safe registry of provider adapters."""

    def __init__(self) -> None:
        """Initialize an empty eager/lazy adapter registry."""
        self._adapters: dict[str, ProviderAdapter] = {}
        self._lazy: dict[str, Callable[[], ProviderAdapter]] = {}
        self._lock = RLock()

    def __repr__(self) -> str:
        """Return a concise debug representation."""
        with self._lock:
            eager_names = sorted(self._adapters.keys())
            lazy_names = sorted(self._lazy.keys())
        return f"ProviderRegistry(eager={eager_names}, lazy={lazy_names})"

    def register(self, adapter: ProviderAdapter, *, validate_capabilities: bool = True) -> None:
        """Register an adapter instance. Validates protocol compliance.

        With ``validate_capabilities=True`` (the default), ``list_datasets()``
        is called once at registration to fail-fast on an adapter whose
        catalogue does not actually load, or whose datasets carry an empty
        ``operations`` set (i.e. a catalogue that mislabels things as
        "supported"). Violations raise ``CapabilityContractError``.

        The name-collision check runs before capability validation —
        capability validation calls ``list_datasets()``, which can cost real
        catalogue-loading work (file I/O and such), and a registration that
        will be rejected anyway should not pay that cost.
        """
        self._validate_adapter(adapter)
        provider_name = str(adapter.name).strip().lower()

        with self._lock:
            if provider_name in self._adapters or provider_name in self._lazy:
                raise ValueError(f"Provider '{provider_name}' is already registered")

        if validate_capabilities:
            self._validate_capability_contract(adapter)

        with self._lock:
            # Re-check: another thread may have registered the same name
            # while capability validation was running.
            if provider_name in self._adapters or provider_name in self._lazy:
                raise ValueError(f"Provider '{provider_name}' is already registered")
            self._adapters[provider_name] = adapter
        logger.debug(
            "Registered eager provider adapter",
            extra={"provider": provider_name, "adapter_type": type(adapter).__name__},
        )

    def register_lazy(
        self, name: str, factory: Callable[[], ProviderAdapter], *, skip_if_exists: bool = False
    ) -> None:
        """Register a lazily loaded adapter through a callable factory.

        When ``skip_if_exists`` is True and the provider name is already
        registered (eager or lazy), the registration is silently skipped.
        This is how ``Client`` registers built-in providers without
        clashing with adapters the user registered.
        """
        normalized_name = name.strip().lower()
        if not normalized_name:
            msg = "Provider name cannot be empty"
            raise ValueError(msg)
        if not callable(factory):
            msg = "Lazy adapter factory must be callable"
            raise TypeError(msg)

        with self._lock:
            if normalized_name in self._adapters or normalized_name in self._lazy:
                if skip_if_exists:
                    logger.debug(
                        "Skipped lazy registration; provider already present",
                        extra={"provider": normalized_name},
                    )
                    return
                raise ValueError(f"Provider '{normalized_name}' is already registered")
            self._lazy[normalized_name] = factory
        logger.debug(
            "Registered lazy provider adapter",
            extra={"provider": normalized_name},
        )

    def get(self, name: str) -> ProviderAdapter:
        """Fetch an adapter by provider name.

        Lazy entries are only peeked at with ``get`` inside the lock, never
        ``pop``-ed (#262) — this simultaneously prevents the race where
        another thread looks the name up during materialization outside the
        lock and misses it in ``_adapters`` yet, and the failure mode where
        a factory error permanently loses the entry. Concurrent
        materialization is idempotent (the first winner is canonical).
        """
        normalized_name = name.strip().lower()
        with self._lock:
            adapter = self._adapters.get(normalized_name)
            if adapter is not None:
                return adapter

            factory = self._lazy.get(normalized_name)

        if factory is None:
            logger.debug("Provider lookup failed", extra={"provider": normalized_name})
            raise ProviderNotRegisteredError(f"Provider '{name}' is not registered")

        logger.debug(
            "Materializing lazy provider adapter",
            extra={"provider": normalized_name},
        )
        lazy_adapter = factory()
        self._validate_adapter(lazy_adapter)
        self._validate_capability_contract(lazy_adapter)
        adapter_name = str(lazy_adapter.name).strip().lower()
        if adapter_name != normalized_name:
            raise TypeError(
                f"Lazy adapter name mismatch: expected '{normalized_name}', got '{adapter_name}'"
            )

        with self._lock:
            winner = self._adapters.setdefault(normalized_name, lazy_adapter)
            if winner is lazy_adapter:
                self._lazy.pop(normalized_name, None)
        logger.debug(
            "Materialized lazy provider adapter",
            extra={
                "provider": normalized_name,
                "adapter_type": type(winner).__name__,
            },
        )
        # Under concurrent materialization every thread shares the first
        # winner's instance (#262).
        return winner

    def __contains__(self, name: str) -> bool:
        """Return True if an adapter is registered, eager or lazy."""
        normalized_name = name.strip().lower()
        with self._lock:
            return normalized_name in self._adapters or normalized_name in self._lazy

    def __iter__(self) -> Iterator[str]:
        """Iterate the provider names the registry currently knows about."""
        with self._lock:
            names = set(self._adapters.keys()) | set(self._lazy.keys())
        return iter(sorted(names))

    @staticmethod
    def _validate_adapter(adapter: ProviderAdapter) -> None:
        """Check that the adapter carries the required protocol methods."""
        name = getattr(adapter, "name", None)
        if not isinstance(name, str) or not name.strip():
            msg = "Adapter must define a non-empty string attribute 'name'"
            raise TypeError(msg)

        missing = [
            method_name for method_name in _REQUIRED_METHODS if not hasattr(adapter, method_name)
        ]
        if missing:
            raise TypeError(f"Adapter '{name}' is missing required methods: {missing}")

        non_callable = [
            method_name
            for method_name in _REQUIRED_METHODS
            if not callable(getattr(adapter, method_name, None))
        ]
        if non_callable:
            raise TypeError(f"Adapter '{name}' has non-callable required methods: {non_callable}")

    @staticmethod
    def _validate_capability_contract(adapter: ProviderAdapter) -> None:
        """Fail-fast validation that the adapter's catalogue declares capabilities honestly.

        If calling ``list_datasets()`` itself fails, catalogue loading is
        broken and the registration is blocked outright. Each exposed
        ``DatasetRef`` is then checked for a non-empty ``operations`` set —
        empty operations amount to claiming "this dataset can do nothing",
        a dishonest declaration.
        """
        provider_name = str(getattr(adapter, "name", "<unknown>"))

        try:
            datasets = adapter.list_datasets()
        except Exception as exc:
            raise CapabilityContractError(
                f"Adapter '{provider_name}' failed to enumerate datasets at registration: {exc}",
                provider=provider_name,
            ) from exc

        if not isinstance(datasets, list):
            raise CapabilityContractError(
                f"Adapter '{provider_name}' list_datasets() must return a list, "
                f"got {type(datasets).__name__}",
                provider=provider_name,
            )

        empty_ops: list[str] = []
        non_ref: list[str] = []
        for entry in datasets:
            if not isinstance(entry, DatasetRef):
                non_ref.append(repr(entry))
                continue
            if not entry.operations:
                empty_ops.append(entry.id)

        if non_ref:
            raise CapabilityContractError(
                f"Adapter '{provider_name}' list_datasets() returned non-DatasetRef entries: "
                f"{non_ref[:3]}",
                provider=provider_name,
            )
        if empty_ops:
            raise CapabilityContractError(
                f"Adapter '{provider_name}' has datasets declaring empty operations: "
                f"{empty_ops[:5]}. An empty operations set is a dishonest capability "
                "declaration — the dataset claims to be supported but exposes no callable "
                "operation.",
                provider=provider_name,
            )


__all__ = ["ProviderRegistry"]
