"""Test module.

This module defines tests and helpers for the surrounding test suite.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.representation import Representation
from kpubdata.exceptions import ConfigError, ParseError, ProviderResponseError
from kpubdata.providers._common import build_dataset_ref, coerce_int, require_string_field
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.providers.datago.envelope import DataGoEnvelopeParser
from kpubdata.transport.http import HttpTransport


class FakeResponse:
    """Tests for FakeResponse.

This class groups related test cases and helpers for FakeResponse.
"""

    def __init__(self, data: bytes, content_type: str = "application/json") -> None:
        """
        Initialize with payload.

        Args:
            data (bytes): Input parameter.
            content_type (str): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        self.headers: dict[str, str] = {"content-type": content_type}
        self.content: bytes = data
        self.text: str = data.decode("utf-8")


class FakeTransport:
    """Tests for FakeTransport.

This class groups related test cases and helpers for FakeTransport.
"""

    def __init__(self, responses: list[FakeResponse]) -> None:
        """
        Initialize with payload.

        Args:
            responses (list[FakeResponse]): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        """
        Execute a mock HTTP request.

        Args:
            method (str): Input parameter.
            url (str): Input parameter.
            **kwargs (object): Input parameter.

        Returns:
            FakeResponse: Result.

        Raises:
            Exceptions propagated."""
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No responses queued")
        return self._responses.pop(0)


def _dataset(raw_metadata: dict[str, object]) -> DatasetRef:
    """_dataset

Validates the scenario described by the test name.
"""
    return DatasetRef(
        id="datago.test",
        provider="datago",
        dataset_key="test",
        name="Test Dataset",
        representation=Representation.API_JSON,
        operations=frozenset(),
        raw_metadata=MappingProxyType(raw_metadata),
    )


def _adapter(
    transport: FakeTransport,
    dataset: DatasetRef,
) -> DataGoAdapter:
    """Validates the scenario described by the test name.
"""
    return DataGoAdapter(
        config=KPubDataConfig(provider_keys={"datago": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
        catalogue=[dataset],
    )


def _ok_payload(*, items: object, total_count: object, num_of_rows: object) -> dict[str, object]:
    """_ok_payload

Validates the scenario described by the test name.
"""
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "items": {"item": items},
                "totalCount": total_count,
                "numOfRows": num_of_rows,
                "pageNo": 1,
            },
        }
    }


# test name property returns datago Describes the scenario verified by the test.
def test_name_property_returns_datago() -> None:
    """
    test name property returns datago Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    assert DataGoAdapter(catalogue=[]).name == "datago"


# test query records sets next page for full page with remaining total Describes the scenario verified by the test.
def test_query_records_sets_next_page_for_full_page_with_remaining_total(monkeypatch) -> None:
    """
    test query records sets next page for full page with remaining total Validates the scenario described by the test name.

    Args:
        monkeypatch (object): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    import kpubdata.providers.datago.adapter as adapter_module

    payload = _ok_payload(items=[{"id": 1}, {"id": 2}], total_count=5, num_of_rows=2)
    transport = FakeTransport([FakeResponse(b"{}")])
    dataset = _dataset({"base_url": "https://example.test", "default_operation": "list"})
    adapter = _adapter(transport, dataset)

    monkeypatch.setattr(adapter_module, "detect_content_type", lambda _resp: "json")
    monkeypatch.setattr(adapter_module, "decode_json", lambda _content: payload)

    batch = adapter.query_records(dataset, Query(page_size=2))

    assert len(transport.calls) == 1
    assert batch.next_page == 2


# test query records stops when page size times page reaches total Describes the scenario verified by the test.
def test_query_records_stops_when_page_size_times_page_reaches_total(monkeypatch) -> None:
    """
    test query records stops when page size times page reaches total Validates the scenario described by the test name.

    Args:
        monkeypatch (object): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    import kpubdata.providers.datago.adapter as adapter_module

    payload = _ok_payload(items=[{"id": 1}, {"id": 2}], total_count=2, num_of_rows=2)
    transport = FakeTransport([FakeResponse(b"{}")])
    dataset = _dataset({"base_url": "https://example.test", "default_operation": "list"})
    adapter = _adapter(transport, dataset)

    monkeypatch.setattr(adapter_module, "detect_content_type", lambda _resp: "json")
    monkeypatch.setattr(adapter_module, "decode_json", lambda _content: payload)

    batch = adapter.query_records(dataset, Query(page_size=2))

    assert len(transport.calls) == 1
    assert batch.next_page is None


# test get schema returns none when all fields are filtered out Describes the scenario verified by the test.
def test_get_schema_returns_none_when_all_fields_are_filtered_out() -> None:
    """
    test get schema returns none when all fields are filtered out Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    dataset = _dataset(
        {
            "base_url": "https://example.test",
            "fields": [{"title": "no-name"}, {"name": ""}, {"name": None}],
        }
    )
    adapter = DataGoAdapter(catalogue=[dataset])

    assert adapter.get_schema(dataset) is None


# test build request url raises when base url missing Describes the scenario verified by the test.
def test_build_request_url_raises_when_base_url_missing() -> None:
    """
    test build request url raises when base url missing Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = DataGoAdapter(catalogue=[])
    with pytest.raises(ProviderResponseError, match="missing base_url"):
        _ = adapter._build_request_url(_dataset({}))


# test build request url returns base url when operation missing Describes the scenario verified by the test.
def test_build_request_url_returns_base_url_when_operation_missing() -> None:
    """
    test build request url returns base url when operation missing Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = DataGoAdapter(catalogue=[])
    dataset = _dataset({"base_url": "https://example.test/api"})

    assert adapter._build_request_url(dataset) == "https://example.test/api"


# test request and decode falls back to json for unknown content type Describes the scenario verified by the test.
def test_request_and_decode_falls_back_to_json_for_unknown_content_type(monkeypatch) -> None:
    """
    test request and decode falls back to json for unknown content type Validates the scenario described by the test name.

    Args:
        monkeypatch (object): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    import kpubdata.providers.datago.adapter as adapter_module

    transport = FakeTransport([FakeResponse(b"ignored")])
    adapter = DataGoAdapter(
        config=KPubDataConfig(provider_keys={"datago": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
        catalogue=[],
    )

    called = {"decode_json": False}

    monkeypatch.setattr(adapter_module, "detect_content_type", lambda _resp: "unknown")

    def _decode_json(_content: bytes) -> dict[str, object]:
        """_decode_json

Validates the scenario described by the test name.
"""
        called["decode_json"] = True
        return {"response": {}}

    monkeypatch.setattr(adapter_module, "decode_json", _decode_json)

    decoded = adapter._request_and_decode("https://example.test", {"a": "1"})
    assert called["decode_json"] is True
    assert decoded == {"response": {}}


# test request and decode raises parse error when decoded payload not object Describes the scenario verified by the test.
def test_request_and_decode_raises_parse_error_when_decoded_payload_not_object(monkeypatch) -> None:
    """
    test request and decode raises parse error when decoded payload not object Validates the scenario described by the test name.

    Args:
        monkeypatch (object): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    import kpubdata.providers.datago.adapter as adapter_module

    transport = FakeTransport([FakeResponse(b"[]")])
    adapter = DataGoAdapter(
        config=KPubDataConfig(provider_keys={"datago": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
        catalogue=[],
    )

    monkeypatch.setattr(adapter_module, "detect_content_type", lambda _resp: "json")
    monkeypatch.setattr(adapter_module, "decode_json", lambda _content: [{"x": 1}])

    with pytest.raises(ParseError, match="not an object"):
        _ = adapter._request_and_decode("https://example.test", {})


# test request and decode raises parse error when decode fails Describes the scenario verified by the test.
def test_request_and_decode_raises_parse_error_when_decode_fails(monkeypatch) -> None:
    """
    test request and decode raises parse error when decode fails Validates the scenario described by the test name.

    Args:
        monkeypatch (object): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    import kpubdata.providers.datago.adapter as adapter_module

    transport = FakeTransport([FakeResponse(b"invalid")])
    adapter = DataGoAdapter(
        config=KPubDataConfig(provider_keys={"datago": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
        catalogue=[],
    )

    monkeypatch.setattr(adapter_module, "detect_content_type", lambda _resp: "unknown")

    def _raises_parse_error(_content: bytes) -> dict[str, object]:
        """_raises_parse_error

Validates the scenario described by the test name.
"""
        raise ParseError("bad payload")

    monkeypatch.setattr(adapter_module, "decode_json", _raises_parse_error)

    with pytest.raises(ParseError, match="bad payload"):
        _ = adapter._request_and_decode("https://example.test", {})


# test validate envelope raises when response missing Describes the scenario verified by the test.
def test_validate_envelope_raises_when_response_missing() -> None:
    """
    test validate envelope raises when response missing Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    parser = DataGoEnvelopeParser()

    with pytest.raises(ProviderResponseError, match="missing response"):
        _ = parser.parse({})


# test validate envelope raises when header missing Describes the scenario verified by the test.
def test_validate_envelope_raises_when_header_missing() -> None:
    """
    test validate envelope raises when header missing Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    parser = DataGoEnvelopeParser()

    with pytest.raises(ProviderResponseError, match="missing header"):
        _ = parser.parse({"response": {"body": {}}})


# test validate envelope raises when result code not string Describes the scenario verified by the test.
def test_validate_envelope_raises_when_result_code_not_string() -> None:
    """
    test validate envelope raises when result code not string Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    parser = DataGoEnvelopeParser()

    with pytest.raises(ProviderResponseError, match="missing resultCode"):
        _ = parser.parse({"response": {"header": {"resultCode": 0}, "body": {}}})


# test raise for result code unknown code raises provider response error Describes the scenario verified by the test.
def test_raise_for_result_code_unknown_code_raises_provider_response_error() -> None:
    """
    test raise for result code unknown code raises provider response error Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    parser = DataGoEnvelopeParser()

    with pytest.raises(ProviderResponseError):
        parser._raise_for_result_code("99", "unknown code", "datago.test")


# test normalize items accepts direct list wrapper Describes the scenario verified by the test.
def test_normalize_items_accepts_direct_list_wrapper() -> None:
    """
    test normalize items accepts direct list wrapper Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    parser = DataGoEnvelopeParser()

    normalized = parser.normalize_items([{"id": 1}, "x", {"id": 2}])

    assert normalized == [{"id": 1}, {"id": 2}]


# test normalize items returns empty for unsupported wrapper Describes the scenario verified by the test.
def test_normalize_items_returns_empty_for_unsupported_wrapper() -> None:
    """
    test normalize items returns empty for unsupported wrapper Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    parser = DataGoEnvelopeParser()
    assert parser.normalize_items("not-a-list-or-dict") == []


# test coerce int returns default for non numeric string Describes the scenario verified by the test.
def test_coerce_int_returns_default_for_non_numeric_string() -> None:
    """
    test coerce int returns default for non numeric string Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    assert coerce_int("not-a-number", 7) == 7


# test coerce int returns default for non string non int Describes the scenario verified by the test.
def test_coerce_int_returns_default_for_non_string_non_int() -> None:
    """
    test coerce int returns default for non string non int Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    assert coerce_int(3.14, 11) == 11


class _FakeCatalogueFile:
    """Tests for _FakeCatalogueFile.

This class groups related test cases and helpers for _FakeCatalogueFile.
"""

    def __init__(self, text: str) -> None:
        """
        Initialize with payload.

        Args:
            text (str): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        self._text = text

    def read_text(self, encoding: str = "utf-8") -> str:
        """
        Perform read text operation.

        Args:
            encoding (str): Input parameter.

        Returns:
            str: Result.

        Raises:
            Exceptions propagated."""
        del encoding
        return self._text


class _FakePackageFiles:
    """Tests for _FakePackageFiles.

This class groups related test cases and helpers for _FakePackageFiles.
"""

    def __init__(self, text: str) -> None:
        """
        Initialize with payload.

        Args:
            text (str): Input parameter.

        Returns:
            None: Result.

        Raises:
            Exceptions propagated."""
        self._text = text

    def joinpath(self, _name: str) -> _FakeCatalogueFile:
        """
        Perform joinpath operation.

        Args:
            _name (str): Input parameter.

        Returns:
            _FakeCatalogueFile: Result.

        Raises:
            Exceptions propagated."""
        return _FakeCatalogueFile(self._text)


# test load default catalogue raises when top level json not list Describes the scenario verified by the test.
def test_load_default_catalogue_raises_when_top_level_json_not_list(monkeypatch) -> None:
    """
    test load default catalogue raises when top level json not list Validates the scenario described by the test name.

    Args:
        monkeypatch (object): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    import kpubdata.providers._common as common_module

    monkeypatch.setattr(common_module, "files", lambda _pkg: _FakePackageFiles("{}"))

    with pytest.raises(ConfigError, match="top-level JSON array"):
        _ = DataGoAdapter._load_default_catalogue()


# test load default catalogue raises when entry not dict Describes the scenario verified by the test.
def test_load_default_catalogue_raises_when_entry_not_dict(monkeypatch) -> None:
    """
    test load default catalogue raises when entry not dict Validates the scenario described by the test name.

    Args:
        monkeypatch (object): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    import kpubdata.providers._common as common_module

    monkeypatch.setattr(common_module, "files", lambda _pkg: _FakePackageFiles("[1]"))

    with pytest.raises(ConfigError, match="entries must be JSON objects"):
        _ = DataGoAdapter._load_default_catalogue()


# test load default catalogue raises when entry key not string Describes the scenario verified by the test.
def test_load_default_catalogue_raises_when_entry_key_not_string(monkeypatch) -> None:
    """
    test load default catalogue raises when entry key not string Validates the scenario described by the test name.

    Args:
        monkeypatch (object): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    import kpubdata.providers._common as common_module

    monkeypatch.setattr(common_module, "files", lambda _pkg: _FakePackageFiles("[]"))
    monkeypatch.setattr(common_module.json, "loads", lambda _text: [{1: "bad-key"}])

    with pytest.raises(ConfigError, match="entry keys must be strings"):
        _ = DataGoAdapter._load_default_catalogue()


# test build dataset ref parses string max page size Describes the scenario verified by the test.
def test_build_dataset_ref_parses_string_max_page_size() -> None:
    """
    test build dataset ref parses string max page size Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    dataset = build_dataset_ref(
        "datago",
        {
            "dataset_key": "test",
            "name": "Test",
            "representation": "api_json",
            "query_support": {"pagination": "offset", "max_page_size": "250"},
            "base_url": "https://example.test",
        },
    )

    assert dataset.query_support is not None
    assert dataset.query_support.max_page_size == 250


# test build dataset ref raises for invalid max page size type Describes the scenario verified by the test.
def test_build_dataset_ref_raises_for_invalid_max_page_size_type() -> None:
    """
    test build dataset ref raises for invalid max page size type Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    with pytest.raises(ConfigError, match="max_page_size must be int-like"):
        _ = build_dataset_ref(
            "datago",
            {
                "dataset_key": "test",
                "name": "Test",
                "representation": "api_json",
                "query_support": {"pagination": "offset", "max_page_size": {}},
            },
        )


# test require string field raises when field missing Describes the scenario verified by the test.
def test_require_string_field_raises_when_field_missing() -> None:
    """
    test require string field raises when field missing Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    with pytest.raises(ConfigError, match="missing non-empty string field"):
        _ = require_string_field({}, "dataset_key", "datago")
