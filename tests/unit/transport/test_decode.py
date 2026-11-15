"""Tests for transport decode utilities."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
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

    def test_bounded_sniff_recognizes_gateway_xml_without_xml_content_type(self) -> None:
        response = httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            content=b"  <?xml version='1.0'?><OpenAPI_ServiceResponse/>",
        )
        assert detect_content_type(response) == "xml"

    def test_mislabeled_json_is_identified_by_its_prefix(self) -> None:
        response = httpx.Response(
            200, headers={"content-type": "text/plain"}, content=b'{"result": "ok"}'
        )
        assert detect_content_type(response) == "json"

    def test_html_document_is_not_guessed_as_xml(self) -> None:
        response = httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<!doctype html><html><body>service unavailable</body></html>",
        )
        assert detect_content_type(response) == "other"


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

    def test_utf8_bom_bytes_are_accepted(self) -> None:
        """A provider's UTF-8 BOM is not part of the JSON syntax."""
        assert decode_json(b'\xef\xbb\xbf{"response": {"code": 0}}') == {
            "response": {"code": 0}
        }

    def test_parse_errors_never_log_response_payload(self, caplog: pytest.LogCaptureFixture) -> None:
        """Upstream bodies may include echoed credentials; never log previews."""
        secret = "SECRET_SENTINEL_970"
        with (
            caplog.at_level(logging.DEBUG, logger="kpubdata.transport.decode"),
            pytest.raises(ParseError),
        ):
            decode_json('{"serviceKey": "' + secret + '"')
        assert secret not in caplog.text


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

    def test_declared_euc_kr_encoding_is_honored(self) -> None:
        """XML bytes are parsed using the encoding in the XML declaration."""
        xml = '<?xml version="1.0" encoding="euc-kr"?><root><city>서울</city></root>'
        assert decode_xml(xml.encode("euc-kr"))["root"]["city"] == "서울"

    def test_invalid_xml_bytes_are_a_parse_error(self) -> None:
        """Corrupt bytes are rejected without an assumed UTF-8-only policy."""
        bad_bytes = b"\xff\xfe<root/>"
        with pytest.raises(ParseError, match="Failed to decode XML"):
            decode_xml(bad_bytes)

    def test_parse_errors_never_log_xml_payload(self, caplog: pytest.LogCaptureFixture) -> None:
        secret = "SECRET_SENTINEL_970"
        with (
            caplog.at_level(logging.DEBUG, logger="kpubdata.transport.decode"),
            pytest.raises(ParseError),
        ):
            decode_xml("<root><serviceKey>" + secret + "</serviceKey>")
        assert secret not in caplog.text
