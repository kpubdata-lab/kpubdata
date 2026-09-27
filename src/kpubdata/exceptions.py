"""KPubData exception hierarchy with structured error context."""

from __future__ import annotations

from typing import Any


class PublicDataError(Exception):
    """Base class for all KPubData errors carrying structured context attributes."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        dataset_id: str | None = None,
        operation: str | None = None,
        status_code: int | None = None,
        provider_code: str | None = None,
        retryable: bool = False,
        detail: object = None,
    ) -> None:
        """Initialize the error with optional provider/transport metadata."""

        super().__init__(message)
        self.provider = provider
        self.dataset_id = dataset_id
        self.operation = operation
        self.status_code = status_code
        self.provider_code = provider_code
        self.retryable = retryable
        self.detail = detail

    def __repr__(self) -> str:
        """Return a structured repr that includes provider and transport metadata."""
        parts = [f"{type(self).__name__}({self.args[0]!r}"]
        if self.provider:
            parts.append(f"provider={self.provider!r}")
        if self.dataset_id:
            parts.append(f"dataset={self.dataset_id!r}")
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.retryable:
            parts.append("retryable=True")
        return ", ".join(parts) + ")"


class ConfigError(PublicDataError):
    """Raised when the KPubData configuration is invalid or incomplete."""


#: 4xx statuses worth sending again. The rest of the 4xx range answers the same.
_RETRYABLE_CLIENT_STATUSES = frozenset({408, 425, 429})


def _status_is_retryable(status_code: object) -> bool:
    """Whether a failure with this status code is worth retrying.

    The verdict matches the retry policy of ``transport.http._is_retryable_status``
    in spirit, but also includes 408 and 425 — the transport does not retry
    those two itself, yet telling the caller "you may try again" is still
    the right answer.
    """
    if not isinstance(status_code, int) or isinstance(status_code, bool):
        # A failure with no status code is the transport itself failing
        # (connection/timeout).
        return True
    if status_code in _RETRYABLE_CLIENT_STATUSES:
        return True
    return status_code >= 500


class AuthError(PublicDataError):
    """Raised on authentication or authorization failure."""


class TransportError(PublicDataError):
    """Raised on network and transport-layer failure."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        """Initialize the transport error. The ``retryable`` default comes from the status code.

        It used to be unconditionally ``True``. Failures that answer the same
        no matter how often you resend — 400, 401, 403, 404 — were therefore
        marked "retryable", and callers trusting that flag (the kpubdata-builder
        Bronze fetch) burned their retry budget repeating a bad key or a bad
        request.

        When the status code is unknown (connection failure, timeout — the
        transport itself failing) it stays retryable as before: those really
        are worth another attempt.
        """
        status_code = kwargs.get("status_code")
        kwargs.setdefault("retryable", _status_is_retryable(status_code))
        super().__init__(message, **kwargs)


class TransportTimeoutError(TransportError):
    """Raised when a provider request exceeds the timeout limit."""


class RateLimitError(TransportError):
    """Raised when a provider refuses a request (throttling and the like)."""


class ServiceUnavailableError(TransportError):
    """Raised when the upstream provider service is temporarily unavailable."""


class ParseError(PublicDataError):
    """Raised when a provider payload cannot be parsed safely."""


class InvalidRequestError(PublicDataError):
    """Raised when a query or operation input is semantically invalid."""


class ProviderResponseError(PublicDataError):
    """Raised when a provider response violates contract expectations."""


class UnsupportedCapabilityError(PublicDataError):
    """Raised when the requested operation is not supported by the dataset."""


class DatasetNotFoundError(PublicDataError):
    """Raised when the requested dataset identifier cannot be resolved."""


class ProviderNotRegisteredError(PublicDataError):
    """Raised when a provider key is absent from the registry."""


class CapabilityContractError(PublicDataError):
    """Raised when a provider adapter's declared capabilities and actual behavior disagree.

    For example: a catalogue dataset declares ``LIST`` but the ``list_datasets``
    call fails, or a dataset declared with an empty ``operations`` set is
    exposed.
    """


__all__ = [
    "AuthError",
    "CapabilityContractError",
    "ConfigError",
    "DatasetNotFoundError",
    "InvalidRequestError",
    "ParseError",
    "ProviderNotRegisteredError",
    "ProviderResponseError",
    "PublicDataError",
    "RateLimitError",
    "ServiceUnavailableError",
    "TransportError",
    "TransportTimeoutError",
    "UnsupportedCapabilityError",
]
