"""Validate and serialize scalar user filters before HTTP requests.

Public-data provider APIs have different parameter names and date formats.
Python reprs for missing values, booleans or collections are not a portable
wire format. Provider-specific formatting stays outside this shared policy.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import TypeVar

from kpubdata.exceptions import InvalidRequestError

_V = TypeVar("_V")


def scalar_filter_value(
    name: str,
    value: object,
    *,
    allow_bool: bool = False,
    provider: str | None = None,
    dataset_id: str | None = None,
) -> str | None:
    """Return a safe scalar query value, or None for a missing optional filter.

    A spec may explicitly declare a boolean parameter. Only those boolean
    parameters use lowercase JSON-style true/false values. Other API filters
    accept strings and numeric scalars without changing their spelling.
    Dates, lists, mappings and custom objects need provider-specific handling.
    A refusal names ``provider`` and ``dataset_id`` so the caller can tell which
    dataset refused the filter.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        if allow_bool:
            return "true" if value else "false"
        raise InvalidRequestError(
            f"Filter {name!r} does not accept a boolean value",
            provider=provider,
            dataset_id=dataset_id,
        )
    if isinstance(value, str | int):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value):
            return str(value)
        raise InvalidRequestError(
            f"Filter {name!r} requires a finite number", provider=provider, dataset_id=dataset_id
        )
    if isinstance(value, Decimal):
        if value.is_finite():
            return str(value)
        raise InvalidRequestError(
            f"Filter {name!r} requires a finite number", provider=provider, dataset_id=dataset_id
        )
    raise InvalidRequestError(
        f"Filter {name!r} requires a string or numeric scalar, not {type(value).__name__}",
        provider=provider,
        dataset_id=dataset_id,
    )


def scalar_filters(
    filters: Mapping[str, object], *, provider: str | None = None, dataset_id: str | None = None
) -> dict[str, str]:
    """Encode user filters with ``scalar_filter_value``, omitting ``None`` values.

    For adapters without a spec: no parameter is declared boolean, so a boolean
    value is refused like any other unsupported object.
    """
    encoded: dict[str, str] = {}
    for key, value in filters.items():
        text = scalar_filter_value(key, value, provider=provider, dataset_id=dataset_id)
        if text is not None:
            encoded[key] = text
    return encoded


def drop_or_refuse_sdk_params(
    filters: Mapping[str, _V],
    *,
    credential: Iterable[str] = (),
    paging: Iterable[str] = (),
    response_format: Iterable[str] = (),
    provider: str,
    dataset_id: str,
) -> dict[str, _V]:
    """Apply the SDK-set parameter rule to ``list()`` filters, matching names case-insensitively.

    A filter named like the credential parameter is dropped: the credential always
    comes from the configured key and is never sent or echoed from a filter. A
    filter named like a paging or response-format parameter the adapter sets raises
    ``InvalidRequestError`` naming the filter (never its value) before any request.
    """
    credential_names = {name.lower() for name in credential}
    paging_names = {name.lower() for name in paging}
    format_names = {name.lower() for name in response_format}
    kept: dict[str, _V] = {}
    for key, value in filters.items():
        folded = key.lower()
        if folded in credential_names:
            continue
        if folded in paging_names:
            raise sdk_param_error(key, paging=True, provider=provider, dataset_id=dataset_id)
        if folded in format_names:
            raise sdk_param_error(key, paging=False, provider=provider, dataset_id=dataset_id)
        kept[key] = value
    return kept


def sdk_param_error(
    name: str, *, paging: bool, provider: str, dataset_id: str
) -> InvalidRequestError:
    """The refusal for a filter named like a paging or response-format parameter."""
    if paging:
        message = (
            f"Filter {name!r} is a paging parameter the SDK sets; "
            "use list(page=..., page_size=...) instead of passing it as a filter"
        )
    else:
        message = (
            f"Filter {name!r} is a response-format parameter the SDK sets; "
            "the response format is fixed by the adapter and cannot be changed through a filter"
        )
    return InvalidRequestError(message, provider=provider, dataset_id=dataset_id)
