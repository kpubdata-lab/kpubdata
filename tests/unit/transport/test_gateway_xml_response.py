"""Ensure mislabeled upstream XML errors reach the normal provider error mapper (#970)."""

from __future__ import annotations

import pytest

from kpubdata.core.models import Query
from kpubdata.exceptions import AuthError
from tests.unit.core.test_executor import (
    FakeResponse,
    FakeTransport,
    _golden_spec,
    _make_executor,
    _ref,
)


def test_text_plain_gateway_auth_xml_preserves_auth_error_category() -> None:
    """An XML body without an XML header is not a generic JSON parse failure."""
    spec = _golden_spec("apt_trade")
    payload = (
        b'<?xml version="1.0" encoding="utf-8"?>'
        b"<OpenAPI_ServiceResponse>"
        b"<cmmMsgHeader>"
        b"<returnReasonCode>30</returnReasonCode>"
        b"<returnAuthMsg>API service not activated</returnAuthMsg>"
        b"</cmmMsgHeader>"
        b"</OpenAPI_ServiceResponse>"
    )
    transport = FakeTransport([FakeResponse(payload, "text/plain")])
    executor = _make_executor(transport)

    with pytest.raises(AuthError, match="not activated"):
        executor.query(
            spec,
            _ref(spec),
            Query(filters={"LAWD_CD": "11110", "DEAL_YMD": "202401"}),
        )

    assert len(transport.calls) == 1
