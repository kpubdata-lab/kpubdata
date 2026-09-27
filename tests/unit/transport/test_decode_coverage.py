"""Test module.

This file ``tests/unit/transport/test_decode_coverage.py`` defines test scenarios and helper objects.
For regression prevention and public contract validation verify core flows, exceptions, and edge conditions.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kpubdata.exceptions import ParseError
from kpubdata.transport.decode import decode_json, decode_xml


# Explains scenario for: test decode json raises for non utf8 bytes.
def test_decode_json_raises_for_non_utf8_bytes() -> None:
    """
    Verify: test decode json raises for non utf8 bytes scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    with pytest.raises(ParseError, match="UTF-8"):
        decode_json(b"\xff\xfe")


# test decode xml raises when parser returns non dict Explains scenario validated by test.
def test_decode_xml_raises_when_parser_returns_non_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    test decode xml raises when parser returns non dict Verify scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    fake_module = MagicMock()
    fake_module.parse.return_value = ["not", "a", "dict"]
    monkeypatch.setattr("kpubdata.transport.decode.import_module", lambda _name: fake_module)

    with pytest.raises(ParseError, match="did not decode into a dictionary"):
        _ = decode_xml("<root />")
