"""Offline parsing of spec-backed dataset responses."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from kpubdata import Client
from kpubdata.core.dataset import Dataset
from kpubdata.exceptions import AuthError, ParseError, RateLimitError, UnsupportedCapabilityError

_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures/datago/apt_trade/seoul_gangnam_2024_01.raw.json"
)


def _dataset() -> Dataset:
    return Client(provider_keys={"datago": "test-key"}).dataset("datago.apt_trade")


def test_parse_raw_casts_fields_without_transport() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    with patch(
        "kpubdata.transport.http.HttpTransport.request", side_effect=AssertionError("network")
    ):
        batch = _dataset().parse_raw(payload)

    assert batch.items
    assert batch.items[0]["dealAmount"] == 101300
    assert batch.items[0]["bonbun"] == "0766"
    assert batch.total_count == int(payload["response"]["body"]["totalCount"])
    assert batch.raw == payload
    assert batch.next_page is None


def test_parse_raw_maps_provider_auth_error() -> None:
    payload = {"response": {"header": {"resultCode": "30", "resultMsg": "bad key"}}}
    with pytest.raises(AuthError, match="bad key"):
        _dataset().parse_raw(payload)


def test_parse_raw_maps_provider_rate_limit_error() -> None:
    payload = {"response": {"header": {"resultCode": "22", "resultMsg": "quota"}}}
    with pytest.raises(RateLimitError, match="quota"):
        _dataset().parse_raw(payload)


def test_parse_raw_maps_gateway_error_without_service_envelope() -> None:
    payload = {
        "OpenAPI_ServiceResponse": {
            "cmmMsgHeader": {"returnReasonCode": "30", "returnAuthMsg": "gateway denied"}
        }
    }
    with pytest.raises(AuthError, match="gateway denied"):
        _dataset().parse_raw(payload)


@pytest.mark.parametrize(
    "body",
    [{"other": "wrong envelope"}, {"items": {"item": "not rows"}}],
)
def test_parse_raw_rejects_malformed_success_envelope(body: dict[str, object]) -> None:
    payload = {"response": {"header": {"resultCode": "00"}, "body": body}}
    with pytest.raises(ParseError):
        _dataset().parse_raw(payload)


def test_parse_raw_rejects_missing_response_code() -> None:
    with pytest.raises(ParseError):
        _dataset().parse_raw({"response": {"body": {"items": []}}})


def test_parse_raw_accepts_empty_result() -> None:
    payload = {
        "response": {
            "header": {"resultCode": "00"},
            "body": {"items": None, "totalCount": "0"},
        }
    }
    batch = _dataset().parse_raw(payload)
    assert batch.items == []
    assert batch.total_count == 0


def test_parse_raw_is_unsupported_on_catalogue_dataset() -> None:
    dataset = Client().dataset("datago.generic")
    with pytest.raises(UnsupportedCapabilityError):
        dataset.parse_raw({"response": {}})
