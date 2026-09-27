"""Tests for transport decode utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from kpubdata.exceptions import ParseError
from kpubdata.transport.decode import decode_json, decode_xml, detect_content_type


class FakeResponse:
    """Mimics minimal httpx.Response interface (headers.content-type)."""

    def __init__(self, content_type: str) -> None:
        """Initialize with response content type."""
        self.headers = {"content-type": content_type}


class TestDetectContentType:
    """Test content type detection."""

    def test_json(self) -> None:
        """JSON content type is detected."""
        assert detect_content_type(FakeResponse("application/json; charset=utf-8")) == "json"

    def test_xml(self) -> None:
        """XML content type is detected."""
        assert detect_content_type(FakeResponse("text/xml")) == "xml"

    def test_other(self) -> None:
        """Other content types are reported."""
        assert detect_content_type(FakeResponse("text/plain")) == "other"


class TestDecodeJson:
    """Test JSON decoding."""

    def test_string(self) -> None:
        """JSON string is decoded."""
        assert decode_json('{"a": 1}') == {"a": 1}

    def test_bytes(self) -> None:
        """JSON bytes are decoded."""
        assert decode_json(b'{"a": 1}') == {"a": 1}

    def test_invalid(self) -> None:
        """Invalid JSON raises ParseError."""
        with pytest.raises(ParseError, match="decode JSON"):
            decode_json("not json")


class TestDecodeXml:
    """Test XML decoding."""

    def test_real_fixture_string(self) -> None:
        """XML string fixture is decoded."""
        xml_path = Path(__file__).resolve().parents[2] / "fixtures" / "datago" / "success_xml.xml"
        xml_text = xml_path.read_text(encoding="utf-8")
        result = decode_xml(xml_text)
        assert isinstance(result, dict)

        body = result["response"]["body"]
        items = body["items"]["item"]
        assert isinstance(items, list)
        assert items[0]["stationName"] == "종로구"
        assert items[1]["stationName"] == "강남구"

    def test_real_fixture_bytes(self) -> None:
        """XML bytes fixture is decoded."""
        xml_path = Path(__file__).resolve().parents[2] / "fixtures" / "datago" / "success_xml.xml"
        xml_bytes = xml_path.read_bytes()
        result = decode_xml(xml_bytes)
        assert isinstance(result, dict)
        assert result["response"]["header"]["resultCode"] == "00"

    def test_single_item_returns_dict_not_list(self) -> None:
        """Single XML item returns dict, not list."""
        xml_path = (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "datago"
            / "success_xml_single_item.xml"
        )
        xml_text = xml_path.read_text(encoding="utf-8")
        result = decode_xml(xml_text)
        item = result["response"]["body"]["items"]["item"]

        assert isinstance(item, dict)
        assert item["stationName"] == "종로구"

    def test_invalid_xml_raises_parse_error(self) -> None:
        """Invalid XML raises ParseError."""
        with pytest.raises(ParseError, match="Failed to decode XML"):
            decode_xml("<<<not xml>>>")

    def test_missing_xmltodict_raises_import_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing xmltodict dependency raises ImportError with hint."""

        def _mock_import(name: str) -> None:
            """Mock import that raises ImportError."""
            raise ImportError("No module named 'xmltodict'")

        monkeypatch.setattr("kpubdata.transport.decode.import_module", _mock_import)
        with pytest.raises(ImportError, match="kpubdata\\[xml\\]"):
            decode_xml("<root/>")

    def test_bytes_utf8_decode_error(self) -> None:
        """Invalid UTF-8 bytes raise ParseError."""
        bad_bytes = b"\xff\xfe<root/>"
        with pytest.raises(ParseError, match="UTF-8"):
            decode_xml(bad_bytes)
