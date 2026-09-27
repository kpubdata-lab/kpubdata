"""Tests for uncovered branches in transport/http.py (L277-278, L301)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import PropertyMock, patch

import httpx

import kpubdata.transport.http as http_module


# Explains scenario for: test response preview returns decode error on text decode failure.
def test_response_preview_returns_decode_error_on_text_decode_failure() -> None:
    """
    Verify: test response preview returns decode error on text decode failure scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    response_preview = cast(Callable[[httpx.Response], str], http_module._response_preview)
    request = httpx.Request("GET", "https://example.test/resource")
    response = httpx.Response(
        status_code=200,
        headers={"content-type": "text/plain"},
        content=b"\x80\x81\x82",
        request=request,
    )

    with patch.object(
        type(response),
        "text",
        new_callable=PropertyMock,
        side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "bad"),
    ):
        result = response_preview(response)

    assert result == "[decode error]"


# Explains scenario for: test parse retry after naive datetime treated as utc.
def test_parse_retry_after_naive_datetime_treated_as_utc() -> None:
    """
    Verify: test parse retry after naive datetime treated as utc scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    parse_retry_after = cast(Callable[[str], float | None], http_module._parse_retry_after)

    future = datetime.now(timezone.utc) + timedelta(seconds=10)
    naive_date_str = future.strftime("%a, %d %b %Y %H:%M:%S") + " GMT"

    with patch.object(
        http_module,
        "parsedate_to_datetime",
        return_value=future.replace(tzinfo=None),
    ):
        result = parse_retry_after(naive_date_str)

    assert result is not None
    assert result >= 0.0
