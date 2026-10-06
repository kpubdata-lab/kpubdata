"""Concise HTTP transport layer—session management, retry, timeout, decoding.

This layer does not handle:
- Authentication injection (adapter responsibility)
- Parameter naming convention (adapter responsibility)
- Response envelope parsing (adapter responsibility)
- Provider-specific error mapping (adapter responsibility)
"""

from __future__ import annotations

import logging
import os
import re
import ssl
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from kpubdata.exceptions import (
    AuthError,
    PublicDataError,
    RateLimitError,
    ServiceUnavailableError,
    TransportError,
    TransportTimeoutError,
)
from kpubdata.transport._envelope import is_upstream_error_envelope
from kpubdata.transport._sensitive import SENSITIVE_PARAM_KEYS, _secret_forms
from kpubdata.transport.cache import (
    CACHE_HIT_EXTENSION,
    CACHED_AT_EXTENSION,
    ResponseCache,
    make_cache_key,
)

from .._typing import override

logger = logging.getLogger("kpubdata.transport")


class _HttpxUrlRedactingFilter(logging.Filter):
    """Mask credential query parameters in the URLs httpx itself logs (#694).

    httpx logs every request at INFO on the ``httpx`` logger as
    ``HTTP Request: GET <full url> ...``. kpubdata masks the URLs in its own logs
    and exceptions, but that line carried the query string -- and so a
    data.go.kr ``serviceKey`` -- verbatim to any application that logs at INFO.
    For a multi-user service holding its users' keys, that is a leak.

    Masking is by parameter name (``SENSITIVE_PARAM_KEYS``) and by value (#821). A
    name-based filter sees neither a key in a path segment (seoul, fds, bok) nor one
    under a name nobody listed (DART's ``crtfc_key``), so the transport makes the
    values it is sending known for the length of the call (``_sending``), and the
    line httpx logs during that call is masked by them too.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and args:
            secret_values = _in_flight_secrets.get()
            record.args = tuple(
                _mask_url(str(arg), secret_values=secret_values) if _is_url(arg) else arg
                for arg in args
            )
        return True


def _is_url(arg: object) -> bool:
    """A URL as httpx passes it, or one an earlier filter on the logger already rendered."""
    return isinstance(arg, httpx.URL) or (isinstance(arg, str) and "://" in arg)


#: The secret values of the request this thread is sending, for the httpx log filter.
#: A context variable, so two transports sending at once do not see each other's.
_in_flight_secrets: ContextVar[tuple[str, ...]] = ContextVar(
    "kpubdata_in_flight_secrets", default=()
)


@contextmanager
def _sending(secret_values: tuple[str, ...]) -> Iterator[None]:
    """Make ``secret_values`` known to the httpx log filter until the block ends."""
    token = _in_flight_secrets.set(secret_values)
    try:
        yield
    finally:
        _in_flight_secrets.reset(token)


def _install_httpx_redaction() -> None:
    """Attach the redacting filter to the ``httpx`` logger once."""
    httpx_logger = logging.getLogger("httpx")
    if not any(isinstance(f, _HttpxUrlRedactingFilter) for f in httpx_logger.filters):
        httpx_logger.addFilter(_HttpxUrlRedactingFilter())


_DEFAULT_MAX_RESPONSE_BYTES = 50 * 1024 * 1024


@dataclass
class TransportConfig:
    """Transport layer configuration."""

    timeout: float = 30.0
    max_retries: int = 3
    retry_backoff_factor: float = 0.5
    headers: dict[str, str] | None = None
    verify_ssl: bool = True
    ssl_context: ssl.SSLContext | None = None
    cache: ResponseCache | None = None
    cache_ttl_seconds: int = 86400
    max_response_bytes: int | None = _DEFAULT_MAX_RESPONSE_BYTES
    #: Maximum seconds to honor a ``Retry-After`` hint. If the server asks
    #: for a longer wait, do not sleep; instead raise RateLimitError
    #: immediately, letting the caller decide when to retry. Without an upper
    #: bound, the library would block the thread for hours when a server
    #: returned 3600.
    max_retry_delay: float = 60.0
    #: Follow a redirect on a request that carries a credential. Off by default
    #: (#812): the client re-sends the request to wherever the answer points, and with
    #: the key in the query string that hands the key to that host — an ``http://``
    #: answer can be forged by anyone on the path. A request without a credential is
    #: redirected as before. Turn this on only for a provider known to redirect.
    follow_credentialed_redirects: bool = False


@dataclass(frozen=True)
class TransportRequirements:
    """Declarative transport customization for provider adapters."""

    verify_ssl: bool | None = None
    headers: Mapping[str, str] | None = None
    ssl_context_factory: Callable[[], ssl.SSLContext] | None = None


class HttpTransport:
    """Managed httpx client with retry, timeout, and structured logging."""

    def __init__(
        self,
        config: TransportConfig | None = None,
        requirements: TransportRequirements | None = None,
        cache: ResponseCache | None = None,
        cache_ttl_seconds: int = 86400,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        """Initialize the transport layer with optional explicit configuration."""
        self._config: TransportConfig = config or TransportConfig()
        self._requirements: TransportRequirements | None = requirements
        self._cache: ResponseCache | None = self._config.cache if cache is None else cache
        self._cache_ttl_seconds: int = (
            self._config.cache_ttl_seconds if cache_ttl_seconds == 86400 else cache_ttl_seconds
        )
        # Retry sleep function (#270): default is time.sleep at call time (module-patchable);
        # tests and async embedding inject explicitly.
        self._sleep: Callable[[float], None] = sleep or (lambda delay: time.sleep(delay))
        self._client: httpx.Client | None = None

    @classmethod
    def with_requirements(
        cls,
        config: TransportConfig,
        requirements: TransportRequirements,
    ) -> HttpTransport:
        """Build a new HttpTransport merging base config with provider requirements."""
        return cls(
            config=TransportConfig(
                timeout=config.timeout,
                max_retries=config.max_retries,
                retry_backoff_factor=config.retry_backoff_factor,
                headers=_merge_headers(config.headers, requirements.headers),
                cache=config.cache,
                cache_ttl_seconds=config.cache_ttl_seconds,
                max_response_bytes=config.max_response_bytes,
            ),
            requirements=requirements,
        )

    def __enter__(self) -> HttpTransport:
        """Enter context manager and initialize client immediately."""
        self._client = self._build_client()
        return self

    def __exit__(self, *exc: object) -> None:
        """Exit context manager and close the managed client."""
        self.close()

    @override
    def __repr__(self) -> str:
        """Return a concise debug representation."""
        return (
            "HttpTransport("
            f"timeout={self._config.timeout}, "
            f"max_retries={self._config.max_retries}, "
            f"retry_backoff_factor={self._config.retry_backoff_factor}, "
            f"client_initialized={self._client is not None}"
            ")"
        )

    def _build_client(self, requirements: TransportRequirements | None = None) -> httpx.Client:
        """Create an httpx.Client reflecting current config and requirements."""
        effective_requirements = requirements or self._requirements
        return httpx.Client(
            timeout=self._config.timeout,
            headers=_merge_headers(
                self._config.headers,
                # Provider-specific headers override common headers.
                None if effective_requirements is None else effective_requirements.headers,
            )
            or {},
            follow_redirects=True,
            verify=self._resolve_verify(effective_requirements),
        )

    def _resolve_verify(self, requirements: TransportRequirements | None) -> bool | ssl.SSLContext:
        """Determine final SSL verification setting and SSLContext."""
        # Explicit SSLContext is more specific than verify_ssl boolean, so take precedence.
        if self._config.ssl_context is not None:
            return self._config.ssl_context
        if requirements is None:
            return self._config.verify_ssl
        # If provider supplies an SSLContext factory, create a dedicated context
        # just before the request.
        if requirements.ssl_context_factory is not None:
            return requirements.ssl_context_factory()
        # Finally, apply provider-specific verify_ssl override if present.
        if requirements.verify_ssl is not None:
            return requirements.verify_ssl
        return self._config.verify_ssl

    def close(self) -> None:
        """Close the client if initialized."""
        if self._client is not None:
            self._client.close()
            self._client = None

    @property
    def client(self) -> httpx.Client:
        """Return the lazily-initialized shared ``httpx.Client`` instance."""
        if self._client is None:
            self._client = self._build_client()
        return self._client

    @property
    def cache(self) -> ResponseCache | None:
        """Return the response cache attached to this transport instance."""
        return self._cache

    @property
    def cache_ttl_seconds(self) -> int:
        """Return the default TTL seconds applied to cached responses."""
        return self._cache_ttl_seconds

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        json_body: object = None,
        dataset_id: str | None = None,
        provider: str | None = None,
        secret_values: tuple[str, ...] = (),
        no_store: bool = False,
    ) -> httpx.Response:
        """Execute an HTTP request, breaking the exception chain for requests
        with credentials.

        ``raise ... from None`` sets only ``__suppress_context__`` to True and
        leaves the original httpx exception in ``__context__``. Standard traceback
        output and Sentry honor that flag, so it is usually hidden, but loggers
        that read ``exc.__context__.request.url`` directly still see the key.

        ``__context__`` is refilled at raise time, so clearing it before raise
        is pointless. We strip it once as the exception leaves this boundary.
        Bare ``raise`` re-raises the current exception without overwriting
        ``__context__``.
        """
        try:
            return self._request(
                method,
                url,
                params=params,
                headers=headers,
                content=content,
                json_body=json_body,
                dataset_id=dataset_id,
                provider=provider,
                secret_values=secret_values,
                no_store=no_store,
            )
        except PublicDataError as exc:
            # Not only TransportError: a 401 leaves as AuthError, which is not one (#786).
            if getattr(exc, "_credential_in_request", False):
                exc.__context__ = None
                exc.__suppress_context__ = True
            raise

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        json_body: object = None,
        dataset_id: str | None = None,
        provider: str | None = None,
        secret_values: tuple[str, ...] = (),
        no_store: bool = False,
    ) -> httpx.Response:
        """Execute HTTP request with retry logic.

        Returns:
            Raw ``httpx.Response``.

        Raises:
            TransportError: Non-timeout transport failure.
            TransportTimeoutError: Timeout failure.
        """
        if self._config.max_retries < 0:
            msg = "max_retries must be >= 0"
            raise ValueError(msg)
        if self._config.retry_backoff_factor < 0:
            msg = "retry_backoff_factor must be >= 0"
            raise ValueError(msg)
        if self._config.max_response_bytes is not None and self._config.max_response_bytes < 1:
            msg = "max_response_bytes must be >= 1 or None"
            raise ValueError(msg)

        # Replay mode (#379): if env var is set, replace response with recorded
        # fixture. Check before actual call, cache, or retry to ensure
        # validation pipeline determinism.
        if os.environ.get("KPUBDATA_MODE") == "replay":
            from kpubdata.transport.replay import replay_response

            replayed = replay_response(
                method,
                url,
                params=params,
                dataset_id=dataset_id,
                provider=provider,
            )
            if replayed is not None:
                return replayed

        total_attempts = self._config.max_retries + 1
        # Build cache key only for safe method/URL/header combinations; reuse
        # GET responses. ``no_store`` is for requests where the response body
        # itself is a credential (sgis token). Caching it stores the token in
        # plaintext in ~/.cache, and worse: force_refresh then reads that stale
        # cache and returns the **old token** — a no-op called "refresh".
        cache_key = (
            None
            if no_store
            else self._make_cache_key(method=method, url=url, params=params, headers=headers)
        )
        request_context = _request_context(dataset_id=dataset_id, provider=provider)
        # Log/exceptions use a masked URL with sensitive params hidden instead of
        # the original URL that may carry API keys as query parameters.
        # Adapters can pass secret values for providers that embed keys in path
        # segments (seoul, etc.) (#354) — value-based substitution without heuristics.
        log_url = _mask_url(url, secret_values=secret_values)
        # Original httpx exceptions left in __cause__ leak credential URLs through
        # exception chains (traceback/error trackers). httpx puts the **final** URL
        # in exception messages, and that URL is built by merging params.
        #
        # Previously we only checked ``log_url != url``, catching URL-string
        # embedding but not params= passing. Most key-carrying paths pass via
        # params= (datago, localdata, semas, sgis, spec executor), so masking did
        # not apply. Work in #475/#484 and tests also only looked at URL strings.
        credential_in_request = (
            log_url != url
            or bool(secret_values)
            or _contains_sensitive_params(params)
            or _contains_sensitive_headers(headers)
        )
        if cache_key is not None and self._cache is not None:
            cached = self._cache.get_entry(cache_key)
            if cached is not None:
                logger.debug(
                    "transport cache hit",
                    extra={
                        "url": log_url,
                        "cache_key": cache_key,
                        **request_context,
                    },
                )
                # Restore Content-Type from when it was stored. Without it, cache
                # hits would re-infer the type and JSON-decode XML responses, so
                # the same request could yield different results depending on
                # cache state. Old entries (no stored type) return empty string,
                # preserving the old behavior without headers.
                # Mark the response as a cache hit and carry the original fetch
                # time, so provenance reports ``cached=True`` and does not date a
                # replayed body as freshly fetched (#616).
                return httpx.Response(
                    status_code=200,
                    content=cached.body,
                    headers={"content-type": cached.content_type} if cached.content_type else None,
                    request=httpx.Request(method.upper(), url, params=params, headers=headers),
                    extensions={
                        CACHE_HIT_EXTENSION: True,
                        CACHED_AT_EXTENSION: cached.created_at,
                    },
                )

        # Some Korean public APIs (e.g., Korea Tourism Org's KorService2) declare
        # Content-Encoding: gzip but send non-gzip body. On decode failure, retry
        # once with Accept-Encoding: identity (#414).
        effective_headers = headers
        identity_retry_used = False

        attempt = 0
        while attempt < total_attempts:
            attempt += 1
            retry_delay: float | None = None
            try:
                logger.debug(
                    "HTTP request start",
                    extra={
                        "method": method,
                        "url": log_url,
                        "attempt": attempt,
                        "max_retries": self._config.max_retries,
                        **request_context,
                    },
                )

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "HTTP request params",
                        extra={
                            "method": method,
                            "url": log_url,
                            "params": _sanitize_params(params, secret_values=secret_values),
                            **request_context,
                        },
                    )

                request = self.client.build_request(
                    method=method,
                    url=url,
                    params=params,
                    headers=effective_headers,
                    content=content,
                    json=json_body,
                )
                follow_redirects = (
                    not credential_in_request or self._config.follow_credentialed_redirects
                )
                # httpx logs the request line inside this call; the filter on its logger
                # masks by these values as well as by name (#821).
                with _sending(secret_values):
                    response = self.client.send(
                        request, stream=True, follow_redirects=follow_redirects
                    )
                if response.is_redirect and not follow_redirects:
                    # Not followed: the key would go to wherever the answer points (#812).
                    # Only the host is named; the location may itself carry the key.
                    target = urlsplit(response.headers.get("location", "")).hostname
                    status_code = response.status_code
                    response.close()
                    redirect_error = TransportError(
                        f"{method} {log_url} was answered with a redirect ({status_code}) to "
                        f"{target or 'another location'}, and a request that carries a "
                        "credential is not redirected",
                        provider=provider,
                        dataset_id=dataset_id,
                        status_code=status_code,
                    )
                    _mark_credential_bearing(redirect_error, credential_in_request)
                    raise redirect_error
                try:
                    _ = response.raise_for_status()
                    response = _read_limited_response(
                        response,
                        max_response_bytes=self._config.max_response_bytes,
                        method=method,
                        url=log_url,
                    )
                except Exception:
                    response.close()
                    raise

                logger.debug(
                    "HTTP request success",
                    extra={
                        "method": method,
                        "url": log_url,
                        "status_code": response.status_code,
                        "attempt": attempt,
                        **request_context,
                    },
                )

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "HTTP response preview",
                        extra={
                            "status_code": response.status_code,
                            "content_type": response.headers.get("content-type", ""),
                            "content_length": len(response.content),
                            "preview": _response_preview(response),
                            **request_context,
                        },
                    )

                # Do not cache every 200. Many Korean public APIs report failure
                # in the body envelope, not HTTP status — quota exceeded (22),
                # unregistered key (30), gateway denial all arrive as 200. Checking
                # status alone froze a momentary quota overrun into a 24-hour outage,
                # and that cache reached builder's Bronze fetch, so scheduled builds
                # could publish empty data as "success".
                cacheable = (
                    cache_key is not None
                    and self._cache is not None
                    and 200 <= response.status_code < 300
                )
                if cacheable and is_upstream_error_envelope(
                    response.content,
                    cast(str, response.headers.get("content-type", "")),
                ):
                    logger.debug(
                        "not caching an upstream error envelope",
                        extra={"url": log_url, **request_context},
                    )
                    cacheable = False
                # Both conditions are guaranteed by cacheable, but the type checker
                # cannot narrow through boolean, so we re-assert here.
                if cacheable and self._cache is not None and cache_key is not None:
                    self._cache.set(
                        cache_key,
                        response.content,
                        self._cache_ttl_seconds,
                        cast(str, response.headers.get("content-type", "")),
                    )
                    logger.debug(
                        "transport cache miss; stored",
                        extra={
                            "url": log_url,
                            "cache_key": cache_key,
                            **request_context,
                        },
                    )
                return response

            except httpx.TimeoutException as exc:
                logger.debug(
                    "HTTP request timeout",
                    extra={
                        "method": method,
                        "url": log_url,
                        "attempt": attempt,
                        "exception_type": type(exc).__name__,
                        **request_context,
                    },
                )
                if attempt >= total_attempts:
                    timeout_error = TransportTimeoutError(
                        f"Request timed out after {attempt} attempts: {method} {log_url}"
                    )
                    _mark_credential_bearing(timeout_error, credential_in_request)
                    raise timeout_error from (None if credential_in_request else exc)

            except httpx.DecodingError as exc:
                if not identity_retry_used:
                    # Identity retry is an immediate 1-shot, not consuming a retry count.
                    identity_retry_used = True
                    merged = dict(effective_headers or {})
                    merged["Accept-Encoding"] = "identity"
                    effective_headers = merged
                    attempt -= 1
                    logger.info(
                        "Response decoding failed; retrying with Accept-Encoding identity",
                        extra={"method": method, "url": log_url, **request_context},
                    )
                    continue
                decoding_error = TransportError(
                    f"Response decoding failed after identity retry: {method} {log_url}"
                )
                _mark_credential_bearing(decoding_error, credential_in_request)
                raise decoding_error from (None if credential_in_request else exc)

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                logger.debug(
                    "HTTP status error",
                    extra={
                        "method": method,
                        "url": log_url,
                        "attempt": attempt,
                        "status_code": status_code,
                        **request_context,
                    },
                )
                if not _is_retryable_status(status_code) or attempt >= total_attempts:
                    # Include status_code in the error. Masking breaks the
                    # exception chain (from None), losing the original response,
                    # so the status and the type are all the caller has.
                    error_type = _STATUS_ERROR_TYPES.get(status_code, TransportError)
                    status_error = error_type(
                        f"HTTP status error {status_code} for {method} {log_url}",
                        provider=provider,
                        dataset_id=dataset_id,
                        status_code=status_code,
                    )
                    _mark_credential_bearing(status_error, credential_in_request)
                    raise status_error from (None if credential_in_request else exc)

                retry_after = cast(str | None, exc.response.headers.get("Retry-After"))
                if retry_after is not None:
                    retry_delay = _parse_retry_after(retry_after)

            except httpx.RequestError as exc:
                logger.debug(
                    "HTTP request error",
                    extra={
                        "method": method,
                        "url": log_url,
                        "attempt": attempt,
                        "exception_type": type(exc).__name__,
                        **request_context,
                    },
                )
                if attempt >= total_attempts:
                    request_error = TransportError(
                        f"Request failed after {attempt} attempts: {method} {log_url}"
                    )
                    _mark_credential_bearing(request_error, credential_in_request)
                    raise request_error from (None if credential_in_request else exc)

            delay: float
            if retry_delay is not None:
                # Prefer server Retry-After over exponential backoff, but do not
                # follow indefinitely. A delay exceeding the cap signals "not
                # available now", not "sleep here". Return RateLimitError
                # immediately instead, letting the caller choose when to retry.
                max_delay = self._config.max_retry_delay
                if max_delay is not None and retry_delay > max_delay:
                    raise RateLimitError(
                        f"server asked to retry after {retry_delay:.0f}s, "
                        f"beyond the {max_delay:.0f}s cap: {method} {log_url}",
                        provider=provider,
                        dataset_id=dataset_id,
                        status_code=status_code,
                        retryable=True,
                        detail={"retry_after": retry_delay, "max_retry_delay": max_delay},
                    )
                delay = retry_delay
            else:
                delay = cast(float, self._config.retry_backoff_factor * (2 ** (attempt - 1)))
            logger.debug(
                "Retrying HTTP request",
                extra={
                    "method": method,
                    "url": log_url,
                    "attempt": attempt,
                    "delay_seconds": delay,
                    **request_context,
                },
            )
            self._sleep(delay)

        msg = "unreachable transport retry state"
        raise RuntimeError(msg)

    def _make_cache_key(
        self,
        *,
        method: str,
        url: str,
        params: dict[str, str] | None,
        headers: dict[str, str] | None,
    ) -> str | None:
        """Compute cache key only for cacheable GET requests."""
        if self._cache is None:
            return None
        if method.upper() != "GET":
            return None
        if _contains_sensitive_headers(headers):
            return None
        return make_cache_key(method, url, params, _cache_headers_subset(headers))


def _is_retryable_status(status_code: int) -> bool:
    """Check if HTTP status code should trigger a retry."""
    return status_code == 429 or 500 <= status_code <= 599


def _read_limited_response(
    response: httpx.Response,
    *,
    max_response_bytes: int | None,
    method: str,
    url: str,
) -> httpx.Response:
    """Read response body within size limit; return as content-loaded Response."""
    if max_response_bytes is not None:
        content_length = response.headers.get("Content-Length")
        if content_length is not None and _content_length_exceeds(
            content_length, max_response_bytes
        ):
            raise TransportError(
                f"Response body exceeded max_response_bytes={max_response_bytes}: {method} {url}"
            )

    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if max_response_bytes is not None and len(body) > max_response_bytes:
            raise TransportError(
                f"Response body exceeded max_response_bytes={max_response_bytes}: {method} {url}"
            )

    return httpx.Response(
        status_code=response.status_code,
        headers=response.headers,
        content=bytes(body),
        request=response.request,
        extensions=response.extensions,
        history=response.history,
    )


def _content_length_exceeds(content_length: str, max_response_bytes: int) -> bool:
    """Check if valid Content-Length header exceeds the limit."""
    try:
        return int(content_length) > max_response_bytes
    except ValueError:
        return False


def _request_context(*, dataset_id: str | None, provider: str | None) -> dict[str, str]:
    """Build dataset/provider context dict for log extra."""
    context: dict[str, str] = {}
    if dataset_id is not None:
        context["dataset_id"] = dataset_id
    if provider is not None:
        context["provider"] = provider
    return context


def _merge_headers(
    base_headers: Mapping[str, str] | None,
    override_headers: Mapping[str, str] | None,
) -> dict[str, str] | None:
    """Return merged dict of base and override headers."""
    if base_headers is None and override_headers is None:
        return None

    merged_headers: dict[str, str] = {}
    if base_headers is not None:
        merged_headers.update(base_headers)
    if override_headers is not None:
        merged_headers.update(override_headers)
    return merged_headers


def _sanitize_params(
    params: dict[str, str] | None, *, secret_values: tuple[str, ...] = ()
) -> dict[str, str]:
    """Build a copy of params with sensitive values masked for logging.

    Two masks, because either alone leaks (#737): by name
    (``SENSITIVE_PARAM_KEYS``) and by value — a provider can send its key under
    a name nobody listed (DART's ``crtfc_key``), and then only the value,
    matched in every percent-encoded form, still catches it.
    """
    if params is None:
        return {}

    forms = set(_secret_forms(secret_values))
    sanitized: dict[str, str] = {}
    for key, value in params.items():
        if key.casefold() in SENSITIVE_PARAM_KEYS or str(value) in forms:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = str(value)
    return sanitized


def _mask_url(url: str, *, secret_values: tuple[str, ...] = ()) -> str:
    """Build a log/exception URL string with sensitive values masked.

    For providers passing API keys as query parameters (e.g., datago), including
    the URL as-is in logs or exceptions exposes the key. If no sensitive keys
    are present, return the URL unchanged; otherwise reconstruct with masking.
    URLs that cannot be parsed are replaced with ``"[invalid url]"`` to prevent
    key exposure.

    ``secret_values`` holds the plaintext key for providers embedding keys in
    path segments (seoul, etc.) (#354) — only exact matches in path segments
    are replaced with ``[REDACTED]`` (value-based, so no false positives on
    service names or page indices). A query value that equals one is masked
    whatever its parameter is called (#821). The caller must know the value.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "[invalid url]"
    if secret_values and parts.path:
        # A segment holds the key as sent or percent-encoded (httpx encodes ``+``, ``/``
        # and ``=`` in a path), so every form is matched.
        # A key may itself contain ``/`` and so span segments; it is matched whole, from
        # one segment boundary to another, never as part of a longer segment.
        path = parts.path
        for form in _secret_forms(secret_values):
            path = re.sub(rf"(?<=/){re.escape(form)}(?=/|$)", "[REDACTED]", path)
        parts = parts._replace(path=path)
    if not parts.query:
        return urlunsplit(parts) if secret_values else url

    query_items = parse_qsl(parts.query, keep_blank_values=True)
    # By name, and by value: a key under a name nobody listed is still a key (#821).
    masked_items = [
        (
            key,
            "[REDACTED]"
            if key.casefold() in SENSITIVE_PARAM_KEYS or (value and value in secret_values)
            else value,
        )
        for key, value in query_items
    ]
    if masked_items == query_items:
        return url
    return urlunsplit(parts._replace(query=urlencode(masked_items, safe="[]")))


def _cache_headers_subset(headers: dict[str, str] | None) -> dict[str, str]:
    """Return headers to use for cache key calculation.

    Include sensitive headers (Authorization, etc.) (#263) — ``make_cache_key``
    normalizes values to sha256 fingerprints, so no plaintext appears in cache
    keys and caches are isolated per credential. Excluding them causes
    pollution: different Bearer tokens share the same cache entry.
    """
    if headers is None:
        return {}
    return dict(headers)


def _contains_sensitive_headers(headers: dict[str, str] | None) -> bool:
    """Check if headers contain any sensitive keys."""
    if headers is None:
        return False
    return any(key.casefold() in SENSITIVE_PARAM_KEYS for key in headers)


#: The typed error a terminal HTTP status raises; any other status is a plain
#: TransportError (#786). 403 is not here: what it means depends on the provider, and
#: the callers that know turn it into AuthError with their own hint.
_STATUS_ERROR_TYPES: Mapping[int, type[PublicDataError]] = {
    401: AuthError,
    429: RateLimitError,
    503: ServiceUnavailableError,
}


def _mark_credential_bearing(error: Exception, credential_in_request: bool) -> None:
    """Mark that this exception came from a request carrying credentials.

    ``HttpTransport.request`` checks this flag at the boundary and strips
    ``__context__``. We cannot delete it at raise time (it is refilled), so we
    mark it for deletion once the exception exits this boundary.
    """
    if credential_in_request:
        error._credential_in_request = True  # type: ignore[attr-defined]


def _contains_sensitive_params(params: dict[str, str] | None) -> bool:
    """Check if query parameters contain any sensitive keys.

    httpx merges params into the final URL in exception messages, so checking
    the URL string alone is insufficient; params must be checked separately.
    """
    if params is None:
        return False
    return any(key.casefold() in SENSITIVE_PARAM_KEYS for key in params)


def _response_preview(response: httpx.Response, max_chars: int = 500) -> str:
    """Build a short preview of response body for debug logs."""
    content_type = cast(str, response.headers.get("content-type", "")).casefold()
    is_text = (
        content_type.startswith("text/")
        or "json" in content_type
        or "xml" in content_type
        or "javascript" in content_type
    )

    if not is_text:
        return f"[binary content, {len(response.content)} bytes]"

    try:
        return response.text[:max_chars]
    except (LookupError, UnicodeDecodeError, ValueError):
        return "[decode error]"


def _parse_retry_after(header_value: str) -> float | None:
    """Parse Retry-After header value to delay seconds.

    Follow RFC 7231 §7.1.3, supporting both delta-seconds and HTTP-date formats.
    Return None if the value cannot be parsed.
    """

    normalized = header_value.strip()

    try:
        return max(float(int(normalized)), 0.0)
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(normalized)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    return max((retry_at - now).total_seconds(), 0.0)


__all__ = ["HttpTransport", "TransportConfig", "TransportRequirements"]


_install_httpx_redaction()
