"""Client — KPubData's top-level entry point."""

from __future__ import annotations

import logging
import os
from typing import cast

from kpubdata.bootstrap import register_builtin_providers
from kpubdata.catalog import Catalog
from kpubdata.config import KPubDataConfig
from kpubdata.core.dataset import Dataset
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.exceptions import ConfigError
from kpubdata.registry import ProviderRegistry
from kpubdata.transport.cache import ResponseCache
from kpubdata.transport.http import HttpTransport, TransportConfig

from ._typing import override

logger = logging.getLogger("kpubdata.client")


class Client:
    """Top-level entry point for dataset discovery and bound operations."""

    def __init__(
        self,
        *,
        provider_keys: dict[str, str] | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        cache: bool | ResponseCache = False,
        cache_ttl_seconds: int = 86400,
        **extra: object,
    ) -> None:
        """Initialize the client with explicit provider/transport settings.

        Credentials are passed directly via ``provider_keys``; transport
        behavior is configured through ``timeout`` and ``max_retries``.
        Built-in providers (datago, bok, kosis, lofin) are registered
        lazily by default.
        """

        self._config: KPubDataConfig = KPubDataConfig(
            provider_keys=provider_keys or {},
            timeout=timeout,
            max_retries=max_retries,
            extra=dict(extra),
        )
        self._registry: ProviderRegistry = ProviderRegistry()
        resolved_cache = _resolve_cache(cache)
        self._transport_config: TransportConfig = TransportConfig(
            timeout=self._config.timeout,
            max_retries=self._config.max_retries,
            cache=resolved_cache,
            cache_ttl_seconds=cache_ttl_seconds,
        )
        self._transport: HttpTransport = HttpTransport(
            self._transport_config,
            cache=resolved_cache,
            cache_ttl_seconds=cache_ttl_seconds,
        )
        self._provider_transports: list[HttpTransport] = []
        self._register_builtin_providers()
        self._catalog: Catalog = Catalog(self._registry)
        logger.debug(
            "Client initialized",
            extra={
                "providers": sorted(self._registry),
                "timeout": self._config.timeout,
                "max_retries": self._config.max_retries,
                "cache_enabled": resolved_cache is not None,
                "cache_ttl_seconds": cache_ttl_seconds,
                "explicit_provider_keys": sorted(self._config.provider_keys.keys()),
            },
        )

    @classmethod
    def from_env(
        cls,
        provider_keys: dict[str, str] | None = None,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
        extra: dict[str, object] | None = None,
        cache: bool | ResponseCache | None = None,
        cache_ttl_seconds: int | None = None,
    ) -> Client:
        """Build a client from environment variables and explicit overrides (#276).

        Overrides are accepted only through explicit parameters —
        ``**kwargs: object`` bypasses type safety. ``cache=None`` means
        "unspecified" (the environment-variable rules apply) while ``False``
        is an explicit opt-out.
        """
        cache_override: object = _UNSET if cache is None else cache
        ttl_override: object = _UNSET if cache_ttl_seconds is None else cache_ttl_seconds
        config = KPubDataConfig.from_env(
            provider_keys=provider_keys,
            timeout=timeout,
            max_retries=max_retries,
            extra=extra,
        )
        cache_ttl_seconds = _resolve_cache_ttl(ttl_override)
        return cls(
            provider_keys=config.provider_keys,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cache=_resolve_cache_from_env(cache_override),
            cache_ttl_seconds=cache_ttl_seconds,
            **config.extra,
        )

    def __enter__(self) -> Client:
        """Enter the context manager and initialize the transport client."""

        _ = self._transport.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        """Exit the context manager and close transport resources."""

        self.close()

    def close(self) -> None:
        """Close the transport resources this client uses."""

        logger.debug(
            "Client closing",
            extra={"owned_provider_transports": len(self._provider_transports)},
        )
        self._transport.close()
        for provider_transport in self._provider_transports:
            provider_transport.close()
        self._provider_transports.clear()

    @property
    def datasets(self) -> Catalog:
        """Return the catalog interface for discovery, search and resolution."""

        return self._catalog

    def dataset(self, dataset_id: str) -> Dataset:
        """Bind and return a dataset object for a canonical identifier.

        Raises:
            DatasetNotFoundError: The dataset ID is invalid or unknown.
            ProviderNotRegisteredError: The provider is not registered.
        """

        logger.debug("Binding dataset", extra={"dataset_id": dataset_id})
        adapter, ref = self._catalog.resolve(dataset_id)
        logger.debug(
            "Dataset bound",
            extra={
                "dataset_id": ref.id,
                "provider": ref.provider,
                "operations": sorted(op.value for op in ref.operations),
            },
        )
        return Dataset(ref=ref, adapter=adapter)

    def register_provider(self, adapter: object) -> None:
        """Register a provider adapter on this client's registry.

        Raises:
            TypeError: The adapter does not satisfy the required protocol.
            ValueError: The provider is already registered.
        """

        logger.debug(
            "Registering external provider adapter",
            extra={"adapter_type": type(adapter).__name__},
        )
        self._registry.register(cast(ProviderAdapter, adapter))

    def iter_authenticated_providers(self) -> tuple[ProviderAdapter, ...]:
        """Collect and return only the provider adapters that require an API key."""
        providers: list[ProviderAdapter] = []
        for provider_name in self._registry:
            adapter = self._registry.get(provider_name)
            if _requires_api_key(adapter):
                providers.append(adapter)
        return tuple(providers)

    def _register_builtin_providers(self) -> None:
        """Register the built-in providers through the bootstrap layer (#230)."""
        register_builtin_providers(
            self._registry,
            config=self._config,
            transport=self._transport,
            transport_config=self._transport_config,
            owned_transports=self._provider_transports,
        )

    @override
    def __repr__(self) -> str:
        """Return a concise representation including the known providers."""

        return f"Client(providers=[{', '.join(self._registry)}])"


__all__ = ["Client"]


_UNSET = object()


def _requires_api_key(adapter: ProviderAdapter) -> bool:
    """Return whether the adapter requires an API key."""
    return cast(bool, getattr(adapter, "requires_api_key", True))


def _resolve_cache(cache: bool | ResponseCache) -> ResponseCache | None:
    """Normalize the cache argument into a ResponseCache instance or None."""
    if cache is False:
        return None
    if cache is True:
        return ResponseCache()
    return cache


def _resolve_cache_from_env(cache_override: object) -> bool | ResponseCache:
    """Read environment variables to decide cache usage and storage location."""
    if cache_override is not _UNSET:
        return cast(bool | ResponseCache, cache_override)
    if os.environ.get("KPUBDATA_CACHE") != "1":
        return False
    cache_dir = os.environ.get("KPUBDATA_CACHE_DIR")
    if cache_dir:
        return ResponseCache(base_dir=cache_dir)
    return True


def _resolve_cache_ttl(ttl_override: object) -> int:
    """Read the cache TTL in seconds from the environment when not overridden."""
    if ttl_override is not _UNSET:
        return cast(int, ttl_override)
    raw_ttl = os.environ.get("KPUBDATA_CACHE_TTL")
    if raw_ttl is None or raw_ttl == "":
        return 86400
    try:
        return int(raw_ttl)
    except ValueError as exc:
        raise ConfigError(f"KPUBDATA_CACHE_TTL must be an integer, got {raw_ttl!r}") from exc
