"""Client — KPubData's top-level entry point."""

from __future__ import annotations

import logging
import math
import numbers
import os
from collections.abc import Mapping
from typing import cast

from kpubdata import _probe
from kpubdata._probe import ProbeResult
from kpubdata.bootstrap import register_builtin_providers
from kpubdata.catalog import Catalog
from kpubdata.config import KPubDataConfig
from kpubdata.core.dataset import Dataset
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.exceptions import ConfigError, InvalidRequestError, ProviderNotRegisteredError
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
        env_keys: bool = True,
    ) -> None:
        """Initialize the client with explicit provider/transport settings.

        Credentials are passed directly via ``provider_keys``; transport
        behavior is configured through ``timeout`` and ``max_retries``, and
        response caching through ``cache`` (``False`` off, ``True`` the
        default disk cache, or a ``ResponseCache``) and ``cache_ttl_seconds``.
        Every built-in provider is registered lazily: its adapter is
        imported and built the first time it is used.

        A provider missing from ``provider_keys`` is looked up in the
        environment (``KPUBDATA_<PROVIDER>_API_KEY``, then
        ``<PROVIDER>_API_KEY``). ``env_keys=False`` turns that off: the client
        then uses only the keys passed here, for every call including
        ``probe`` (#694).

        An unknown keyword argument is a ``TypeError`` (#781). It used to be
        accepted and dropped, so a typo, or an option this version does not
        have, passed for a setting that was applied.

        An option of the wrong type or out of range is a ``ConfigError`` here,
        at construction, rather than a raw error at the first call. In
        particular ``env_keys`` must be a real ``bool``: the string ``"no"`` is
        truthy and would have turned the environment fallback on.
        """

        _validate_options(
            provider_keys=provider_keys,
            timeout=timeout,
            max_retries=max_retries,
            cache=cache,
            cache_ttl_seconds=cache_ttl_seconds,
            env_keys=env_keys,
        )
        self._config: KPubDataConfig = KPubDataConfig(
            provider_keys=provider_keys or {},
            timeout=timeout,
            max_retries=max_retries,
            env_fallback=env_keys,
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
                "env_keys": self._config.env_fallback,
            },
        )

    @classmethod
    def from_env(
        cls,
        provider_keys: dict[str, str] | None = None,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
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
        )
        cache_ttl_seconds = _resolve_cache_ttl(ttl_override)
        return cls(
            provider_keys=config.provider_keys,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cache=_resolve_cache_from_env(cache_override),
            cache_ttl_seconds=cache_ttl_seconds,
        )

    def __enter__(self) -> Client:
        """Enter the context manager and initialize the transport client."""

        _ = self._transport.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        """Exit the context manager and close transport resources."""

        self.close()

    def close(self) -> None:
        """Close the transport resources this client uses.

        Closing is idempotent. A client used again after ``close()`` rebuilds
        its connection pools lazily, and a later ``close()`` closes them too:
        the dedicated provider transports stay tracked for the client's
        lifetime (#973).
        """

        logger.debug(
            "Client closing",
            extra={"owned_provider_transports": len(self._provider_transports)},
        )
        self._transport.close()
        for provider_transport in self._provider_transports:
            provider_transport.close()

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

    def probe(self, dataset_id: str) -> ProbeResult | None:
        """Classify whether one dataset is reachable with this client's keys.

        Makes at most one call, with the probe's fast-fail transport
        (``PROBE_TIMEOUT_SECONDS``, ``PROBE_RETRIES``, no cache) rather than
        this client's own, and never raises for a failed call: the failure is
        the verdict. ``status`` is one of ``PROBE_STATUSES`` (ADR 0005).

        When the dataset needs a key this client does not have, no call is
        made and the status is ``auth_unknown``. A spec-defined dataset is
        called through its spec; a catalogue dataset of the data.go.kr adapters
        (``datago``, ``semas``, ``localdata``) through the adapter, with one
        one-record ``list`` call. Returns ``None`` for any other dataset — an
        unknown id, a raw-only dataset such as ``datago.generic``, or another
        provider's catalogue dataset, whose error codes are not data.go.kr's.

        The provider part of the id is matched case-insensitively, as
        ``dataset`` matches it.

        Raises:
            InvalidRequestError: ``dataset_id`` is not a str.
        """
        if not isinstance(dataset_id, str):
            raise InvalidRequestError(f"dataset_id must be a str, got {type(dataset_id).__name__}")
        logger.debug("Probing dataset", extra={"dataset_id": dataset_id})
        return _probe.probe_dataset(dataset_id, config=self._config)

    def probe_all(self, *, provider: str | None = None) -> list[ProbeResult]:
        """Probe every spec-defined dataset, or those of one ``provider``.

        One call per dataset, as in ``probe``; the run shares a single
        fast-fail transport that is closed before returning. ``provider`` is
        matched case-insensitively, as ``datasets.list`` matches it.

        Raises:
            InvalidRequestError: ``provider`` is not a str.
            ProviderNotRegisteredError: ``provider`` was given but is unknown.
        """
        if provider is not None:
            if not isinstance(provider, str):
                raise InvalidRequestError(f"provider must be a str, got {type(provider).__name__}")
            if provider not in self._registry:
                raise ProviderNotRegisteredError(f"Provider '{provider}' is not registered")
        logger.debug("Probing datasets", extra={"provider": provider})
        return _probe.probe_all(provider=provider, config=self._config)

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


def _validate_options(
    *,
    provider_keys: object,
    timeout: object,
    max_retries: object,
    cache: object,
    cache_ttl_seconds: object,
    env_keys: object,
) -> None:
    """Refuse a constructor option of the wrong type or out of range with ConfigError."""
    if provider_keys is not None:
        if not isinstance(provider_keys, Mapping):
            raise ConfigError(
                f"provider_keys must be a dict of str to str, got {type(provider_keys).__name__}"
            )
        for name, value in cast(Mapping[object, object], provider_keys).items():
            # A None value counts as absent, as it always has: the key is then
            # looked up from the environment (when allowed) at call time.
            if not isinstance(name, str) or not isinstance(value, str | None):
                raise ConfigError(
                    "provider_keys must be a dict of str to str, got an entry of "
                    f"{type(name).__name__} to {type(value).__name__}"
                )
    # None and an infinite timeout both mean "no timeout" to httpx, and worked before.
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, numbers.Real)
        or math.isnan(timeout)
        or timeout <= 0
    ):
        raise ConfigError(
            f"timeout must be a positive number or None, got {type(timeout).__name__}"
        )
    if (
        isinstance(max_retries, bool)
        or not isinstance(max_retries, numbers.Integral)
        or max_retries < 0
    ):
        raise ConfigError(
            f"max_retries must be an integer >= 0, got {type(max_retries).__name__}"
            + (f" {max_retries}" if isinstance(max_retries, numbers.Integral) else "")
        )
    if not isinstance(cache, bool | ResponseCache):
        raise ConfigError(f"cache must be a bool or a ResponseCache, got {type(cache).__name__}")
    if (
        isinstance(cache_ttl_seconds, bool)
        or not isinstance(cache_ttl_seconds, numbers.Integral)
        or cache_ttl_seconds < 0
    ):
        raise ConfigError(
            f"cache_ttl_seconds must be an integer >= 0, got {type(cache_ttl_seconds).__name__}"
            + (f" {cache_ttl_seconds}" if isinstance(cache_ttl_seconds, numbers.Integral) else "")
        )
    if not isinstance(env_keys, bool):
        raise ConfigError(f"env_keys must be True or False, got {type(env_keys).__name__}")


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
        ttl = int(raw_ttl)
    except ValueError as exc:
        raise ConfigError(f"KPUBDATA_CACHE_TTL must be an integer, got {raw_ttl!r}") from exc
    if ttl < 0:
        raise ConfigError(f"KPUBDATA_CACHE_TTL must be an integer >= 0, got {raw_ttl!r}")
    return ttl
