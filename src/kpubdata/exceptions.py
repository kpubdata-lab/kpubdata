"""KPubData exception hierarchy with structured error context."""

from __future__ import annotations

from typing import Any, ClassVar


class PublicDataError(Exception):
    """Base class for all KPubData errors carrying structured context attributes.

    ``code`` names the kind of failure and does not change with the message, so a
    consumer maps it without comparing strings (#786). A subclass that adds none
    inherits its parent's.
    """

    code: ClassVar[str] = "public_data_error"

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

    def to_dict(self) -> dict[str, object]:
        """Return the error as a JSON-serialisable dict with a stable ``code``.

        ``detail`` is left out: it holds whatever the raising site attached and is
        not guaranteed to serialise.
        """
        return {
            "code": self.code,
            "type": type(self).__name__,
            "message": str(self.args[0]) if self.args else "",
            "provider": self.provider,
            "dataset_id": self.dataset_id,
            "operation": self.operation,
            "status_code": self.status_code,
            "provider_code": self.provider_code,
            "retryable": self.retryable,
        }

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

    code: ClassVar[str] = "config_error"


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

    code: ClassVar[str] = "auth_error"


class TransportError(PublicDataError):
    """Raised on network and transport-layer failure."""

    code: ClassVar[str] = "transport_error"

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

    code: ClassVar[str] = "transport_timeout"


class RateLimitError(TransportError):
    """Raised when a provider refuses a request (throttling and the like)."""

    code: ClassVar[str] = "rate_limited"


class ServiceUnavailableError(TransportError):
    """Raised when the upstream provider service is temporarily unavailable."""

    code: ClassVar[str] = "service_unavailable"


class ParseError(PublicDataError):
    """Raised when a provider payload cannot be parsed safely."""

    code: ClassVar[str] = "parse_error"


class InvalidRequestError(PublicDataError):
    """Raised when a query or operation input is semantically invalid."""

    code: ClassVar[str] = "invalid_request"


class ProviderResponseError(PublicDataError):
    """Raised when a provider response violates contract expectations."""

    code: ClassVar[str] = "provider_response_error"


class UnsupportedCapabilityError(PublicDataError):
    """Raised when the requested operation is not supported by the dataset."""

    code: ClassVar[str] = "unsupported_capability"


class DatasetNotFoundError(PublicDataError):
    """Raised when the requested dataset identifier cannot be resolved."""

    code: ClassVar[str] = "dataset_not_found"


class ProviderNotRegisteredError(PublicDataError):
    """Raised when a provider key is absent from the registry."""

    code: ClassVar[str] = "provider_not_registered"


class CapabilityContractError(PublicDataError):
    """Raised when a provider adapter's declared capabilities and actual behavior disagree.

    For example: a catalogue dataset declares ``LIST`` but the ``list_datasets``
    call fails, or a dataset declared with an empty ``operations`` set is
    exposed.
    """

    code: ClassVar[str] = "capability_contract_error"


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
