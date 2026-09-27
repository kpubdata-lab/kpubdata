"""Client assembly (bootstrap) layer (#230).

A factory layer that separates provider/transport **assembly** concerns from
\`Client\` — the Client itself handles runtime behavior (discovery, querying,
lifecycle), while this module decides which built-in providers to register
and how. The public API is unchanged.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from typing import cast

from kpubdata.config import KPubDataConfig
from kpubdata.core.bridge import CompositeProviderAdapter
from kpubdata.core.executor import SpecDatasetAdapter, SpecExecutor
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.core.spec import SpecDefinition, discover_specs
from kpubdata.providers.manifest import BUILTIN_PROVIDERS
from kpubdata.registry import ProviderRegistry
from kpubdata.transport.http import (
    HttpTransport,
    TransportConfig,
    TransportRequirements,
)


def register_builtin_providers(
    registry: ProviderRegistry,
    *,
    config: KPubDataConfig,
    transport: HttpTransport,
    transport_config: TransportConfig,
    owned_transports: list[HttpTransport],
) -> None:
    """Register the built-in providers on the registry as lazy factories.

    Args:
        registry: The registry to register on.
        config: Framework configuration used to construct providers.
        transport: The default transport shared by providers that declare no
            requirements.
        transport_config: Base settings when building a per-provider
            dedicated transport.
        owned_transports: List that per-provider dedicated transports are
            appended to — the caller (Client) closes them on shutdown.
    """
    for provider_name, module_path, class_name in BUILTIN_PROVIDERS:
        registry.register_lazy(
            provider_name,
            _make_builtin_factory(
                provider_name,
                module_path,
                class_name,
                config,
                transport,
                transport_config,
                owned_transports,
            ),
            skip_if_exists=True,
        )


def _make_builtin_factory(
    provider_name: str,
    mod: str,
    cls: str,
    cfg: KPubDataConfig,
    tpt: HttpTransport,
    base_transport_config: TransportConfig,
    owned_transports: list[HttpTransport],
) -> Callable[[], ProviderAdapter]:
    """Build an adapter factory that imports the provider module lazily."""

    def _factory() -> ProviderAdapter:
        module = importlib.import_module(mod)
        adapter_cls = cast(Callable[..., ProviderAdapter], getattr(module, cls))
        adapter = adapter_cls(config=cfg, transport=tpt)
        final_transport = tpt
        requirements = _get_transport_requirements(adapter)
        # A provider with its own SSL/header requirements gets a separate
        # HttpTransport.
        if requirements is not None:
            final_transport = HttpTransport.with_requirements(
                base_transport_config,
                requirements,
            )
            owned_transports.append(final_transport)
            adapter = adapter_cls(config=cfg, transport=final_transport)
        # Providers with specs are merged with the catalogue adapter and
        # exposed spec-first (#378).
        return _wrap_with_specs(provider_name, adapter, final_transport, cfg)

    return _factory


def _wrap_with_specs(
    provider_name: str,
    adapter: ProviderAdapter,
    transport: HttpTransport,
    config: KPubDataConfig,
) -> ProviderAdapter:
    """Wrap in a composite bridge when the provider has specs; return the original otherwise."""
    specs = _specs_for_provider(provider_name)
    if not specs:
        return adapter
    executor = SpecExecutor(transport, config)
    spec_adapter = SpecDatasetAdapter(provider_name, list(specs), executor)
    logger.info(
        "Wrapping builtin adapter with dataset specs",
        extra={"provider": provider_name, "spec_count": len(specs)},
    )
    return CompositeProviderAdapter(adapter, spec_adapter)


def _specs_for_provider(provider_name: str) -> tuple[SpecDefinition, ...]:
    """Collect the bundled specs belonging to this provider."""
    return tuple(spec for spec in discover_specs() if spec.provider == provider_name)


def _get_transport_requirements(adapter: ProviderAdapter) -> TransportRequirements | None:
    """Read and return the transport requirements an adapter declares."""
    requirements = getattr(adapter, "transport_requirements", None)
    if requirements is None:
        return None
    return cast(TransportRequirements | None, requirements)


logger = logging.getLogger("kpubdata.bootstrap")

__all__ = ["register_builtin_providers"]
