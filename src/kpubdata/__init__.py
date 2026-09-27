"""KPubData — a Python 3.10+ framework for accessing Korean public data."""

from __future__ import annotations

from kpubdata.client import Client
from kpubdata.core.capability import Operation, PaginationMode, QuerySupport
from kpubdata.core.models import (
    DatasetRef,
    FieldConstraints,
    FieldDescriptor,
    Query,
    RecordBatch,
    SchemaDescriptor,
)
from kpubdata.core.representation import Representation
from kpubdata.exceptions import (
    AuthError,
    ConfigError,
    DatasetNotFoundError,
    InvalidRequestError,
    ParseError,
    ProviderNotRegisteredError,
    ProviderResponseError,
    PublicDataError,
    RateLimitError,
    ServiceUnavailableError,
    TransportError,
    TransportTimeoutError,
    UnsupportedCapabilityError,
)

__all__ = [
    "__version__",
    "Client",
    "DatasetRef",
    "Query",
    "RecordBatch",
    "SchemaDescriptor",
    "FieldConstraints",
    "FieldDescriptor",
    "Operation",
    "PaginationMode",
    "QuerySupport",
    "Representation",
    "PublicDataError",
    "ConfigError",
    "AuthError",
    "TransportError",
    "TransportTimeoutError",
    "RateLimitError",
    "ServiceUnavailableError",
    "ParseError",
    "InvalidRequestError",
    "ProviderResponseError",
    "UnsupportedCapabilityError",
    "DatasetNotFoundError",
    "ProviderNotRegisteredError",
]

from importlib.metadata import version as _pkg_version

__version__: str = _pkg_version("kpubdata")
