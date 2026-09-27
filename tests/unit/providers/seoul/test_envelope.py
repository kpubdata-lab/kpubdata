"""Seoul API envelope parser regression tests for errors and edge cases (#454).

This parser determines response shape — when broken, downstream receives
**empty results** rather than exceptions. Thus this suite fixes "which
responses map to which exceptions" and "how to distinguish empty from failed"
rather than success round-trips.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from kpubdata.core.models import DatasetRef
from kpubdata.core.representation import Representation
from kpubdata.exceptions import AuthError, InvalidRequestError, ProviderResponseError
from kpubdata.providers.seoul.envelope import validate_envelope

_SERVICE = "TestService"


def _ref(**raw: object) -> DatasetRef:
    return DatasetRef(
        id="seoul:test",
        provider="seoul",
        dataset_key="test",
        name="Test",
        representation=Representation.API_JSON,
        raw_metadata=MappingProxyType(dict(raw)),
    )


def _envelope(code: str, *, rows: object = None, message: str = "msg") -> dict[str, object]:
    body: dict[str, object] = {"RESULT": {"CODE": code, "MESSAGE": message}}
    if rows is not None:
        body["row"] = rows
    return {_SERVICE: body}


# --- Success / Empty ---


def test_success_returns_body_and_rows() -> None:
    body, rows = validate_envelope(
        _envelope("INFO-000", rows=[{"a": 1}, {"a": 2}]), _SERVICE, _ref()
    )
    assert rows == [{"a": 1}, {"a": 2}]
    assert body["RESULT"] == {"CODE": "INFO-000", "MESSAGE": "msg"}


def test_empty_result_code_is_not_an_error() -> None:
    """INFO-200 (no data) is empty list, not exception."""
    _, rows = validate_envelope(_envelope("INFO-200"), _SERVICE, _ref())
    assert rows == []


def test_success_with_no_row_key_yields_no_rows() -> None:
    _, rows = validate_envelope(_envelope("INFO-000"), _SERVICE, _ref())
    assert rows == []


def test_single_row_object_is_wrapped_in_a_list() -> None:
    """Single row: Seoul API returns dict as-is — must normalize to list."""
    _, rows = validate_envelope(_envelope("INFO-000", rows={"a": 1}), _SERVICE, _ref())
    assert rows == [{"a": 1}]


@pytest.mark.parametrize("rows", ["not-a-list", 42, True])
def test_unusable_row_payload_yields_no_rows(rows: object) -> None:
    _, parsed = validate_envelope(_envelope("INFO-000", rows=rows), _SERVICE, _ref())
    assert parsed == []


def test_non_mapping_row_entries_are_dropped() -> None:
    """Drop mixed non-object items, keep rest."""
    _, rows = validate_envelope(
        _envelope("INFO-000", rows=[{"a": 1}, "junk", None, {"b": 2}]), _SERVICE, _ref()
    )
    assert rows == [{"a": 1}, {"b": 2}]


# --- Result Code -> Exception Mapping ---


@pytest.mark.parametrize("code", ["INFO-100", "INFO-300"])
def test_auth_codes_raise_auth_error(code: str) -> None:
    with pytest.raises(AuthError) as exc:
        validate_envelope(_envelope(code, message="인증키 오류"), _SERVICE, _ref())
    assert exc.value.provider_code == code


@pytest.mark.parametrize("code", ["INFO-400", "ERROR-300", "ERROR-301", "ERROR-310", "ERROR-336"])
def test_request_codes_raise_invalid_request_error(code: str) -> None:
    with pytest.raises(InvalidRequestError) as exc:
        validate_envelope(_envelope(code), _SERVICE, _ref())
    assert exc.value.provider_code == code


@pytest.mark.parametrize("code", ["INFO-500", "ERROR-500", "ERROR-600", "ERROR-601"])
def test_server_codes_raise_provider_response_error(code: str) -> None:
    with pytest.raises(ProviderResponseError) as exc:
        validate_envelope(_envelope(code), _SERVICE, _ref())
    assert exc.value.provider_code == code


def test_unknown_code_still_raises_rather_than_returning_empty() -> None:
    """Unclassified codes as success lead to silent empty results."""
    with pytest.raises(ProviderResponseError) as exc:
        validate_envelope(_envelope("ERROR-999", message="알 수 없음"), _SERVICE, _ref())
    assert exc.value.provider_code == "ERROR-999"


def test_non_string_code_and_message_get_placeholders() -> None:
    payload: dict[str, object] = {_SERVICE: {"RESULT": {"CODE": 500, "MESSAGE": None}}}
    with pytest.raises(ProviderResponseError) as exc:
        validate_envelope(payload, _SERVICE, _ref())
    assert exc.value.provider_code == "ERROR-UNKNOWN"
    assert "Provider returned error" in str(exc.value)


# --- Malformed Envelope ---


def test_missing_service_key_is_reported_by_name() -> None:
    with pytest.raises(ProviderResponseError, match=f"missing {_SERVICE}"):
        payload: dict[str, object] = {"SomethingElse": {}}
        validate_envelope(payload, _SERVICE, _ref())


def test_service_value_that_is_not_a_mapping_is_rejected() -> None:
    with pytest.raises(ProviderResponseError, match=f"missing {_SERVICE}"):
        payload: dict[str, object] = {_SERVICE: ["not", "a", "mapping"]}
        validate_envelope(payload, _SERVICE, _ref())


def test_missing_result_block_is_rejected() -> None:
    with pytest.raises(ProviderResponseError, match="missing RESULT"):
        payload: dict[str, object] = {_SERVICE: {"row": []}}
        validate_envelope(payload, _SERVICE, _ref())


def test_result_that_is_not_a_mapping_is_rejected() -> None:
    with pytest.raises(ProviderResponseError, match="missing RESULT"):
        payload: dict[str, object] = {_SERVICE: {"RESULT": "INFO-000"}}
        validate_envelope(payload, _SERVICE, _ref())


# --- Top-level RESULT Variations ---


def test_top_level_result_success() -> None:
    """Some services put RESULT at top level with key name 'RESULT.CODE'."""
    payload: dict[str, object] = {
        "RESULT": {"RESULT.CODE": "INFO-000", "RESULT.MESSAGE": "정상"},
        _SERVICE: [{"a": 1}],
    }
    _, rows = validate_envelope(payload, _SERVICE, _ref(top_level_result=True))
    assert rows == [{"a": 1}]


def test_top_level_result_empty_code() -> None:
    payload: dict[str, object] = {"RESULT": {"RESULT.CODE": "INFO-200", "RESULT.MESSAGE": "없음"}}
    _, rows = validate_envelope(payload, _SERVICE, _ref(top_level_result=True))
    assert rows == []


def test_top_level_result_error_code_raises() -> None:
    payload: dict[str, object] = {
        "RESULT": {"RESULT.CODE": "INFO-100", "RESULT.MESSAGE": "인증 필요"}
    }
    with pytest.raises(AuthError):
        validate_envelope(payload, _SERVICE, _ref(top_level_result=True))


def test_top_level_result_missing_block_is_rejected() -> None:
    with pytest.raises(ProviderResponseError, match="missing RESULT"):
        payload: dict[str, object] = {_SERVICE: []}
        validate_envelope(payload, _SERVICE, _ref(top_level_result=True))


# --- Top-level code/message Error Response ---


def test_bare_error_object_is_classified_before_envelope_parsing() -> None:
    """Error responses with only code/message (no service key) share same classification."""
    with pytest.raises(AuthError) as exc:
        validate_envelope({"code": "INFO-100", "message": "키 없음"}, _SERVICE, _ref())
    assert exc.value.provider_code == "INFO-100"


def test_bare_error_object_with_non_string_fields() -> None:
    with pytest.raises(ProviderResponseError) as exc:
        validate_envelope({"code": 1, "message": 2}, _SERVICE, _ref())
    assert exc.value.provider_code == "ERROR-UNKNOWN"


def test_code_and_message_alongside_the_service_key_are_not_an_error() -> None:
    """Success responses may include code/message too — must not misclassify as error."""
    payload: dict[str, object] = {
        "code": "INFO-000",
        "message": "정상",
        _SERVICE: {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상"}, "row": [{"a": 1}]},
    }
    _, rows = validate_envelope(payload, _SERVICE, _ref())
    assert rows == [{"a": 1}]


# --- Envelope Key Redefinition ---


def test_envelope_key_override_is_used_when_present() -> None:
    payload: dict[str, object] = {"OtherKey": {"RESULT": {"CODE": "INFO-000"}, "row": [{"a": 1}]}}
    _, rows = validate_envelope(payload, _SERVICE, _ref(envelope_key="OtherKey"))
    assert rows == [{"a": 1}]


def test_envelope_key_override_falls_back_when_absent_from_payload() -> None:
    """Redefined key absent in response falls back to service name — does not fail immediately."""
    payload = _envelope("INFO-000", rows=[{"a": 1}])
    _, rows = validate_envelope(payload, _SERVICE, _ref(envelope_key="Missing"))
    assert rows == [{"a": 1}]


@pytest.mark.parametrize("override", ["", 123, None])
def test_unusable_envelope_key_override_is_ignored(override: object) -> None:
    payload = _envelope("INFO-000", rows=[{"a": 1}])
    _, rows = validate_envelope(payload, _SERVICE, _ref(envelope_key=override))
    assert rows == [{"a": 1}]
