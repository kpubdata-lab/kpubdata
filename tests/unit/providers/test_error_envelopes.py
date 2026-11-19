"""Provider error envelopes map to canonical exceptions; "no data" is an empty batch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import Query, RecordBatch
from kpubdata.exceptions import (
    AuthError,
    InvalidRequestError,
    ProviderResponseError,
    RateLimitError,
)
from kpubdata.providers.bok.adapter import BokAdapter
from kpubdata.providers.kipris.adapter import KiprisAdapter
from kpubdata.providers.kosis.adapter import KosisAdapter
from kpubdata.providers.law.adapter import LawAdapter
from kpubdata.providers.localdata.adapter import LocaldataAdapter
from kpubdata.providers.lofin.adapter import LofinAdapter
from kpubdata.providers.semas.adapter import SemasAdapter
from kpubdata.transport.http import HttpTransport

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
GATEWAY_XML = (FIXTURES / "datago" / "error_gateway_key_not_registered.xml").read_bytes()


class _Resp:
    def __init__(self, body: bytes, content_type: str = "application/json") -> None:
        self.content = body
        self.status_code = 200
        self.headers = {"content-type": content_type}
        self.text = body.decode("utf-8", "replace")


class _Transport:
    def __init__(self, *bodies: object) -> None:
        self._bodies = list(bodies)
        self.urls: list[str] = []

    def request(self, method: str, url: str, **kwargs: object) -> _Resp:
        self.urls.append(url)
        body = self._bodies.pop(0)
        if isinstance(body, _Resp):
            return body
        return _Resp(json.dumps(body, ensure_ascii=False).encode())


def _cfg(name: str) -> KPubDataConfig:
    return KPubDataConfig(provider_keys={name: "K"})


def _tr(*bodies: object) -> tuple[_Transport, HttpTransport]:
    fake = _Transport(*bodies)
    return fake, cast(HttpTransport, fake)


def _gateway(code: str, msg: str = "SERVICE ERROR") -> _Resp:
    xml = (
        "<OpenAPI_ServiceResponse><cmmMsgHeader>"
        f"<errMsg>{msg}</errMsg><returnReasonCode>{code}</returnReasonCode>"
        "</cmmMsgHeader></OpenAPI_ServiceResponse>"
    )
    return _Resp(xml.encode(), "text/xml")


# 1. KIPRIS header.resultCode


def _kipris(body: object) -> tuple[KiprisAdapter, RecordBatch | None]:
    _, transport = _tr(body)
    adapter = KiprisAdapter(config=_cfg("kipris"), transport=transport)
    return adapter, None


def _kipris_query(body: object) -> RecordBatch:
    adapter, _ = _kipris(body)
    dataset = adapter.get_dataset("patent_family")
    return adapter.query_records(dataset, Query(filters={"applicationNumber": "1"}))


def test_kipris_auth_result_code_raises_auth_error() -> None:
    body = {"response": {"header": {"resultCode": "30", "resultMsg": "KEY"}, "body": {}}}
    with pytest.raises(AuthError):
        _kipris_query(body)


def test_kipris_quota_result_code_raises_rate_limit_error() -> None:
    body = {"response": {"header": {"resultCode": "22", "resultMsg": "QUOTA"}, "body": {}}}
    with pytest.raises(RateLimitError):
        _kipris_query(body)


def test_kipris_no_data_result_code_is_empty_batch() -> None:
    body = {"response": {"header": {"resultCode": "03", "resultMsg": "NODATA"}, "body": {}}}
    assert _kipris_query(body).items == []


def test_kipris_success_result_code_is_not_an_error() -> None:
    body = {"response": {"header": {"resultCode": "00", "resultMsg": "OK"}, "body": {}}}
    assert _kipris_query(body).items == []


def test_kipris_call_raw_raises_on_error_code_and_returns_raw_on_success() -> None:
    err = {"response": {"header": {"resultCode": "30", "resultMsg": "KEY"}, "body": {}}}
    adapter, _ = _kipris(err)
    dataset = adapter.get_dataset("patent_family")
    with pytest.raises(AuthError):
        adapter.call_raw(dataset, "", {"applicationNumber": "1"})

    ok = {"response": {"header": {"resultCode": "00"}, "body": {"items": {}}}}
    adapter, _ = _kipris(ok)
    assert adapter.call_raw(dataset, "", {"applicationNumber": "1"}) == ok


# 2. localdata / semas gateway refusal


def test_semas_gateway_key_not_registered_is_auth_error() -> None:
    _, transport = _tr(_Resp(GATEWAY_XML, "text/xml"))
    adapter = SemasAdapter(config=_cfg("semas"), transport=transport)
    with pytest.raises(AuthError):
        adapter.query_records(adapter.list_datasets()[0], Query())


def test_semas_gateway_quota_is_rate_limit_error() -> None:
    _, transport = _tr(_gateway("22", "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"))
    adapter = SemasAdapter(config=_cfg("semas"), transport=transport)
    with pytest.raises(RateLimitError):
        adapter.query_records(adapter.list_datasets()[0], Query())


def test_localdata_gateway_key_not_registered_is_auth_error() -> None:
    _, transport = _tr(_Resp(GATEWAY_XML, "text/xml"))
    adapter = LocaldataAdapter(config=_cfg("localdata"), transport=transport)
    with pytest.raises(AuthError):
        adapter.query_records(adapter.list_datasets()[0], Query())


# 3. law "oc" substring


def test_law_message_with_oc_substring_is_not_auth_error() -> None:
    body = {"resultCode": "99", "resultMsg": "Unknown target: ordinance procedure"}
    _, transport = _tr(body)
    adapter = LawAdapter(config=_cfg("law"), transport=transport)
    with pytest.raises(ProviderResponseError) as info:
        adapter.query_records(adapter.get_dataset("law_search"), Query())
    assert not isinstance(info.value, AuthError)


@pytest.mark.parametrize("msg", ["사용자 인증에 실패했습니다", "invalid OC value", "Bad API key"])
def test_law_genuine_auth_messages_still_raise_auth_error(msg: str) -> None:
    _, transport = _tr({"resultCode": "99", "resultMsg": msg})
    adapter = LawAdapter(config=_cfg("law"), transport=transport)
    with pytest.raises(AuthError):
        adapter.query_records(adapter.get_dataset("law_search"), Query())


# 4. BOK codes


def _bok(code: str, msg: str) -> RecordBatch:
    _, transport = _tr({"RESULT": {"CODE": code, "MESSAGE": msg}})
    adapter = BokAdapter(config=_cfg("bok"), transport=transport)
    return adapter.query_records(
        adapter.list_datasets()[0], Query(start_date="202401", end_date="202402")
    )


def test_bok_info_200_is_empty_batch() -> None:
    assert _bok("INFO-200", "해당하는 데이터가 없습니다.").items == []


def test_bok_error_602_is_rate_limit_error() -> None:
    with pytest.raises(RateLimitError):
        _bok(
            "ERROR-602", "과도한 OpenAPI호출로 이용이 제한되었습니다. 잠시후 이용해주시기 바랍니다."
        )


# 5. LOFIN ERROR-300


def test_lofin_error_300_is_invalid_request_error() -> None:
    body = {"RESULT": [{"CODE": "ERROR-300", "MESSAGE": "필수 값이 누락되어 있습니다."}]}
    _, transport = _tr(body)
    adapter = LofinAdapter(config=_cfg("lofin"), transport=transport)
    with pytest.raises(InvalidRequestError):
        adapter.query_records(adapter.list_datasets()[0], Query())


# 6. KOSIS pagination


def _kosis() -> tuple[KosisAdapter, _Transport]:
    rows = json.loads((FIXTURES / "kosis" / "success_single_page.json").read_text())
    fake, transport = _tr(rows, rows)
    return KosisAdapter(config=_cfg("kosis"), transport=transport), fake


def test_kosis_declares_no_pagination() -> None:
    adapter, _ = _kosis()
    for dataset in adapter.list_datasets():
        assert dataset.query_support.pagination.value == "none"
        assert dataset.query_support.max_page_size is None


@pytest.mark.parametrize("kwargs", [{"page": 2}, {"page_size": 1}, {"page": 1, "page_size": 5}])
def test_kosis_refuses_page_options_it_cannot_honour(kwargs: dict[str, int]) -> None:
    adapter, fake = _kosis()
    dataset = adapter.get_dataset("industrial_production")
    with pytest.raises(InvalidRequestError):
        adapter.query_records(dataset, Query(start_date="202401", end_date="202402", **kwargs))
    assert fake.urls == []
