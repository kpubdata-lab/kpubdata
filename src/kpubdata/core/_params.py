"""Validate and serialize scalar user filters before HTTP requests.

Public-data provider APIs have different parameter names and date formats.
Python reprs for missing values, booleans or collections are not a portable
wire format. Provider-specific formatting stays outside this shared policy.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import Decimal

from kpubdata.exceptions import InvalidRequestError


def scalar_filter_value(name: str, value: object, *, allow_bool: bool = False) -> str | None:
    """Return a safe scalar query value, or None for a missing optional filter.

    A spec may explicitly declare a boolean parameter. Only those boolean
    parameters use lowercase JSON-style true/false values. Other API filters
    accept strings and numeric scalars without changing their spelling.
    Dates, lists, mappings and custom objects need provider-specific handling.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        if allow_bool:
            return "true" if value else "false"
        raise InvalidRequestError(f"Filter {name!r} does not accept a boolean value")
    if isinstance(value, str | int):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value):
            return str(value)
        raise InvalidRequestError(f"Filter {name!r} requires a finite number")
    if isinstance(value, Decimal):
        if value.is_finite():
            return str(value)
        raise InvalidRequestError(f"Filter {name!r} requires a finite number")
    raise InvalidRequestError(
        f"Filter {name!r} requires a string or numeric scalar, not {type(value).__name__}"
    )


def scalar_filters(filters: Mapping[str, object]) -> dict[str, str]:
    """Encode user filters with ``scalar_filter_value``, omitting ``None`` values.

    For adapters without a spec: no parameter is declared boolean, so a boolean
    value is refused like any other unsupported object.
    """
    encoded: dict[str, str] = {}
    for key, value in filters.items():
        text = scalar_filter_value(key, value)
        if text is not None:
            encoded[key] = text
    return encoded
