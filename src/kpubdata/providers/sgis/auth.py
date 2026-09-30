"""KPubData Python module.

This file contains the implementation at
``src/kpubdata/providers/sgis/auth.py``.
Key classes and functions serve as public API, transport layer, or provider
adapter.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NoReturn, cast

from kpubdata.config import KPubDataConfig
from kpubdata.exceptions import AuthError, ConfigError, InvalidRequestError, ProviderResponseError
from kpubdata.transport.decode import decode_json
from kpubdata.transport.http import HttpTransport

_AUTH_ENDPOINT = "https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json"
_SGIS_PROVIDER = "sgis"
_SECRET_ENV = "KPUBDATA_SGIS_CONSUMER_SECRET"


@dataclass(slots=True)
class _TokenState:
    """TokenState to compute or retrieve values."""

    value: str
    expires_at: datetime


class SgisAuthClient:
    """SgisAuthClient to compute or retrieve values."""

    def __init__(self, *, config: KPubDataConfig, transport: HttpTransport) -> None:
        """Initialize internal state for this auth client instance."""
        self._config: KPubDataConfig = config
        self._transport: HttpTransport = transport
        self._cached_token: _TokenState | None = None

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        """Return access token."""
        if (
            not force_refresh
            and self._cached_token is not None
            and not self._is_expired(self._cached_token)
        ):
            return self._cached_token.value

        token_state = self._request_access_token()
        self._cached_token = token_state
        return token_state.value

    def invalidate(self) -> None:
        """Invalidate cached token state."""
        self._cached_token = None

    def _request_access_token(self) -> _TokenState:
        """Request access token.

        Response body is the access token itself. Caching in transport cache
        would leave token plaintext in ~/.cache; force_refresh would re-read
        that stale cache without refreshing. Token caching is done by this
        class in-memory with expiration time.
        """
        consumer_key, consumer_secret = self._resolve_credentials()
        response = self._transport.request(
            "GET",
            _AUTH_ENDPOINT,
            params={"consumer_key": consumer_key, "consumer_secret": consumer_secret},
            no_store=True,
        )

        decoded = decode_json(response.content)
        if not isinstance(decoded, dict):
            raise ProviderResponseError(
                "SGIS auth response must be a JSON object",
                provider=_SGIS_PROVIDER,
            )
        payload = cast(dict[str, object], decoded)

        self._raise_for_err_code(payload)

        result_obj = payload.get("result")
        if not isinstance(result_obj, dict):
            raise ProviderResponseError(
                "SGIS auth response missing result object",
                provider=_SGIS_PROVIDER,
            )
        result = cast(dict[str, object], result_obj)

        token_obj = result.get("accessToken")
        timeout_obj = result.get("accessTimeout")
        if not isinstance(token_obj, str) or not token_obj:
            raise ProviderResponseError(
                "SGIS auth response missing accessToken",
                provider=_SGIS_PROVIDER,
            )

        expires_epoch = _coerce_epoch(timeout_obj)
        if expires_epoch is None:
            raise ProviderResponseError(
                "SGIS auth response has invalid accessTimeout",
                provider=_SGIS_PROVIDER,
            )

        expires_at = datetime.fromtimestamp(expires_epoch, tz=timezone.utc)
        return _TokenState(value=token_obj, expires_at=expires_at)

    def _resolve_credentials(self) -> tuple[str, str]:
        """Resolve credentials from configuration and defaults."""
        consumer_key_raw = self._config.require_provider_key(_SGIS_PROVIDER)
        # The explicit-keys-only mode (#694) reads no credential from the
        # environment, and the consumer secret is a credential.
        consumer_secret_env = (
            os.environ.get(_SECRET_ENV) if getattr(self._config, "env_fallback", True) else None
        )

        if consumer_secret_env:
            return consumer_key_raw, consumer_secret_env

        if ":" in consumer_key_raw:
            key_part, secret_part = consumer_key_raw.split(":", 1)
            if key_part and secret_part:
                return key_part, secret_part

        raise ConfigError(
            "Missing SGIS consumer secret. "
            + "Set KPUBDATA_SGIS_CONSUMER_SECRET or pass provider key "
            + "as 'consumer_key:consumer_secret'."
        )

    def _is_expired(self, state: _TokenState) -> bool:
        """Return whether token is expired."""
        now = datetime.now(tz=timezone.utc)
        return now >= state.expires_at

    def _raise_for_err_code(self, payload: dict[str, object]) -> None:
        """Raise exception for error code."""
        err_code = _extract_err_code(payload)
        if err_code is None or err_code == 0:
            return

        message_obj = payload.get("errMsg")
        message = (
            message_obj if isinstance(message_obj, str) and message_obj else "SGIS auth failed"
        )
        self._raise_for_code(err_code, message)

    def _raise_for_code(self, err_code: int, message: str) -> NoReturn:
        """Raise exception for specific error code."""
        provider_code = str(err_code)
        if err_code in {-401, -402, -403}:
            raise AuthError(message, provider=_SGIS_PROVIDER, provider_code=provider_code)
        if err_code in {-413, -414}:
            raise InvalidRequestError(message, provider=_SGIS_PROVIDER, provider_code=provider_code)
        raise ProviderResponseError(message, provider=_SGIS_PROVIDER, provider_code=provider_code)


def _extract_err_code(payload: Mapping[str, object]) -> int | None:
    """Extract needed value from error code."""
    err_obj = payload.get("errCd")
    if isinstance(err_obj, int):
        return err_obj
    if isinstance(err_obj, str):
        try:
            return int(err_obj)
        except ValueError:
            return None
    return None


def _coerce_epoch(value: object) -> int | None:
    """Coerce value to epoch representation."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


__all__ = ["SgisAuthClient", "_extract_err_code"]
