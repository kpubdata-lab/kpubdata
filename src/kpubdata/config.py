"""Configuration management — explicit settings and environment-based loading.

Provider key lookup order:
1. An explicit `provider_keys` dict passed to the constructor
2. Environment variable: KPUBDATA_{PROVIDER}_API_KEY (upper case)
3. Environment variable: {PROVIDER}_API_KEY (upper case, fallback)

Steps 2 and 3 are skipped when ``env_fallback`` is False — the
explicit-keys-only mode (#694). A caller holding someone else's key (a
multi-user service probing with a user's key, for example) must not have a
missing entry silently filled in from the process environment: the call would
run on the operator's key, spend the operator's quota and report a verdict
that is not the user's.

data.go.kr family providers (localdata, lofin, semas) all use the "datago"
key. Setting KPUBDATA_DATAGO_API_KEY once covers every data.go.kr based
provider.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

from kpubdata.exceptions import ConfigError

_ENV_KEY_PATTERN = re.compile(r"^KPUBDATA_([A-Z0-9_]+)_API_KEY$")
logger = logging.getLogger("kpubdata.config")


@dataclass
class KPubDataConfig:
    """Framework configuration."""

    provider_keys: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    max_retries: int = 3
    extra: dict[str, object] = field(default_factory=dict)
    #: When False, only ``provider_keys`` is consulted; environment variables are
    #: never read for credentials (#694).
    env_fallback: bool = True

    def __repr__(self) -> str:
        """Return a concise debug representation that exposes no secrets."""
        providers = sorted(self.provider_keys.keys())
        return (
            "KPubDataConfig("
            f"providers={providers}, "
            f"timeout={self.timeout}, "
            f"max_retries={self.max_retries}, "
            f"extra_keys={sorted(self.extra.keys())}, "
            f"env_fallback={self.env_fallback}"
            ")"
        )

    def get_provider_key(self, provider: str) -> str | None:
        """Look up a provider's API key following the documented precedence."""
        normalized_provider = _normalize_provider_name(provider)

        explicit = _get_explicit_key(self.provider_keys, normalized_provider)
        if explicit:
            return explicit

        if not self.env_fallback:
            return None

        provider_token = _provider_env_token(normalized_provider)
        kpub_var = f"KPUBDATA_{provider_token}_API_KEY"
        value = os.environ.get(kpub_var)
        if value:
            return value

        fallback_var = f"{provider_token}_API_KEY"
        fallback_value = os.environ.get(fallback_var)
        if fallback_value:
            return fallback_value

        return None

    def require_provider_key(self, provider: str, *, fallback_to: str | None = None) -> str:
        """Like get_provider_key, but raises ConfigError when the key is missing.

        ``fallback_to`` exists for providers that **share one key from the
        same issuer** — localdata and semas use the same data.go.kr service
        key as datago. Those two adapters used to call
        ``require_provider_key("datago")`` directly, which **silently
        ignored** what the README recommends (``provider_keys={"localdata":
        ...}`` or ``KPUBDATA_LOCALDATA_API_KEY``). Users who followed the
        documentation hit a ConfigError.

        Now a provider looks under its own name first and falls back to the
        shared key. Both spellings work, so documentation and code no longer
        disagree.
        """
        key = self.get_provider_key(provider)
        if key is not None:
            return key
        if fallback_to is not None:
            shared = self.get_provider_key(fallback_to)
            if shared is not None:
                return shared
            logger.debug(
                "Missing provider API key",
                extra={"provider": provider, "fallback": fallback_to},
            )
            raise ConfigError(
                f"Missing provider API key for {provider!r}. "
                f"{provider} uses the same data.go.kr service key as {fallback_to!r}, "
                f"so either KPUBDATA_{provider.upper()}_API_KEY or "
                f"KPUBDATA_{fallback_to.upper()}_API_KEY works."
            )
        logger.debug("Missing provider API key", extra={"provider": provider})
        raise ConfigError(f"Missing provider API key for '{provider}'")

    @classmethod
    def from_env(
        cls,
        provider_keys: dict[str, str] | None = None,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
        extra: dict[str, object] | None = None,
    ) -> KPubDataConfig:
        """Build the configuration from environment variables.

        Scans for the KPUBDATA_*_API_KEY pattern. Overrides are passed only
        through explicit parameters (#276) — ``**kwargs: Any`` bypassed type
        safety and was dropped.
        """
        scanned_keys: dict[str, str] = {}
        for env_name, env_value in os.environ.items():
            match = _ENV_KEY_PATTERN.match(env_name)
            if match is None:
                continue
            if not env_value:
                continue
            provider_name = match.group(1).lower()
            scanned_keys[provider_name] = env_value

        provider_overrides: dict[str, str] = {}
        for key, value in (provider_keys or {}).items():
            # The type is dict[str, str]; runtime validation stays as defense
            # against untyped callers.
            if isinstance(key, str) and isinstance(value, str) and value:
                provider_overrides[_normalize_provider_name(key)] = value

        merged_provider_keys = scanned_keys.copy()
        merged_provider_keys.update(provider_overrides)

        return cls(
            provider_keys=merged_provider_keys,
            timeout=30.0 if timeout is None else timeout,
            max_retries=3 if max_retries is None else max_retries,
            extra={} if extra is None else extra,
        )


def _normalize_provider_name(provider: str) -> str:
    """Normalize a provider name into a comparable lower-case form."""
    return provider.strip().lower()


def _provider_env_token(provider: str) -> str:
    """Convert a provider name into a token usable in an environment variable prefix."""
    token = re.sub(r"[^A-Za-z0-9]", "_", provider)
    return token.upper()


def _get_explicit_key(provider_keys: dict[str, str], provider: str) -> str | None:
    """Find a provider key in the explicitly passed provider_keys."""
    if provider in provider_keys and provider_keys[provider]:
        return provider_keys[provider]

    for name, value in provider_keys.items():
        if name.lower() == provider and value:
            return value
    return None


__all__ = ["KPubDataConfig"]
