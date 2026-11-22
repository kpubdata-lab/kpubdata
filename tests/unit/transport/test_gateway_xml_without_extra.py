"""A gateway key refusal maps the same way with or without the ``xml`` extra (#1101).

The data.go.kr gateway answers a rejected request with
``OpenAPI_ServiceResponse/cmmMsgHeader`` XML even on JSON endpoints. On a base
install ``decode_xml`` raises ImportError, and the refusal used to surface as
"install the xml extra" (or a bare ParseError) instead of AuthError. Every test
here runs the same body twice, once through xmltodict (installed in dev) and once
with xmltodict blocked, and requires the same outcome.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import Query
from kpubdata.exceptions import InvalidRequestError, ParseError, PublicDataError
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.providers.localdata.adapter import LocaldataAdapter
from kpubdata.providers.semas.adapter import SemasAdapter
from kpubdata.transport.decode import decode_gateway_envelope, decode_xml
from kpubdata.transport.http import HttpTransport
from tests.unit.core.test_executor import (
    FakeResponse,
    FakeTransport,
    _golden_spec,
    _make_executor,
    _ref,
)
from tests.unit.providers.test_error_envelopes import _Resp, _Transport

Outcome = tuple[type[BaseException], str | None, bool, str]


def _gateway_body(code: str, auth_msg: str = "SERVICE_KEY_IS_NOT_REGISTERED_ERROR") -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<OpenAPI_ServiceResponse>\n"
        "\t<cmmMsgHeader>\n"
        "\t\t<errMsg>SERVICE ERROR</errMsg>\n"
        f"\t\t<returnAuthMsg>{auth_msg}</returnAuthMsg>\n"
        f"\t\t<returnReasonCode>{code}</returnReasonCode>\n"
        "\t</cmmMsgHeader>\n"
        "</OpenAPI_ServiceResponse>\n"
    ).encode()


def _run_executor(body: bytes, content_type: str) -> None:
    spec = _golden_spec("apt_trade")
    executor = _make_executor(FakeTransport([FakeResponse(body, content_type)]))
    executor.query(spec, _ref(spec), Query(filters={"LAWD_CD": "11110", "DEAL_YMD": "202401"}))


def _run_datago(body: bytes, content_type: str) -> None:
    transport = cast(HttpTransport, cast(object, _Transport(_Resp(body, content_type))))
    adapter = DataGoAdapter(
        config=KPubDataConfig(provider_keys={"datago": "K"}), transport=transport
    )
    adapter.query_records(adapter.get_dataset("subway_passengers"), Query())


def _run_semas(body: bytes, content_type: str) -> None:
    transport = cast(HttpTransport, cast(object, _Transport(_Resp(body, content_type))))
    adapter = SemasAdapter(config=KPubDataConfig(provider_keys={"semas": "K"}), transport=transport)
    adapter.query_records(adapter.list_datasets()[0], Query())


def _run_localdata(body: bytes, content_type: str) -> None:
    transport = cast(HttpTransport, cast(object, _Transport(_Resp(body, content_type))))
    adapter = LocaldataAdapter(
        config=KPubDataConfig(provider_keys={"localdata": "K"}), transport=transport
    )
    adapter.query_records(adapter.list_datasets()[0], Query())


_PATHS: dict[str, Callable[[bytes, str], None]] = {
    "spec_executor": _run_executor,
    "datago_adapter": _run_datago,
    "semas_family": _run_semas,
    "localdata_family": _run_localdata,
}


def _outcome(run: Callable[[bytes, str], None], body: bytes, content_type: str) -> Outcome:
    with pytest.raises(PublicDataError) as caught:
        run(body, content_type)
    exc = caught.value
    return type(exc), exc.provider_code, exc.retryable, str(exc)


def _block_xmltodict(monkeypatch: pytest.MonkeyPatch) -> None:
    # A None entry makes ``import xmltodict`` raise ImportError, as on a base install.
    monkeypatch.setitem(sys.modules, "xmltodict", None)


@pytest.mark.parametrize("path", sorted(_PATHS))
@pytest.mark.parametrize("code", ["30", "31", "20", "32", "22", "10", "99"])
@pytest.mark.parametrize("content_type", ["text/xml", "text/plain"])
def test_gateway_refusal_maps_the_same_without_xmltodict(
    monkeypatch: pytest.MonkeyPatch, path: str, code: str, content_type: str
) -> None:
    run = _PATHS[path]
    body = _gateway_body(code)

    with_extra = _outcome(run, body, content_type)
    _block_xmltodict(monkeypatch)
    without_extra = _outcome(run, body, content_type)

    assert without_extra == with_extra
    assert with_extra[1] == code


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_gateway_refusal_without_messages_maps_the_same(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    run = _PATHS[path]
    body = (
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg/><returnAuthMsg>  </returnAuthMsg>"
        b"<returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"
    )

    with_extra = _outcome(run, body, "text/xml")
    _block_xmltodict(monkeypatch)

    assert _outcome(run, body, "text/xml") == with_extra


_NOT_A_GATEWAY_REFUSAL = {
    "service_envelope": (
        b'<?xml version="1.0"?><response><header><resultCode>30</resultCode>'
        b"<resultMsg>KEY</resultMsg></header><body/></response>"
    ),
    "entity_declaration": (
        b'<?xml version="1.0"?><!DOCTYPE OpenAPI_ServiceResponse [<!ENTITY a "30">]>'
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>&a;</returnReasonCode>"
        b"</cmmMsgHeader></OpenAPI_ServiceResponse>"
    ),
    "billion_laughs": (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
        b'<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>'
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode>"
        b"<errMsg>&lol3;</errMsg></cmmMsgHeader></OpenAPI_ServiceResponse>"
    ),
    "entity_reference_in_text": (
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>3&#48;</returnReasonCode>"
        b"</cmmMsgHeader></OpenAPI_ServiceResponse>"
    ),
    "unclosed_root": (
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode>"
        b"</cmmMsgHeader>"
    ),
    "mismatched_tags": (
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</errMsg>"
        b"</cmmMsgHeader></OpenAPI_ServiceResponse>"
    ),
    "trailing_document": (
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode>"
        b"</cmmMsgHeader></OpenAPI_ServiceResponse><response/>"
    ),
    "nested_element": (
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode><b>30</b>"
        b"</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"
    ),
    "attribute": (
        b'<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode x="1">30'
        b"</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"
    ),
    "repeated_field": (
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode>"
        b"<returnReasonCode>22</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"
    ),
    "oversized": (
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode>"
        b"<errMsg>" + b"A" * 20_000 + b"</errMsg></cmmMsgHeader></OpenAPI_ServiceResponse>"
    ),
    "not_utf8": (
        b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode>"
        b"<errMsg>\xff\xfe</errMsg></cmmMsgHeader></OpenAPI_ServiceResponse>"
    ),
    "whitespace_before_declaration": b"\n" + _gateway_body("30"),
    "control_character_in_text": _gateway_body("30", auth_msg="KEY\x01ERROR"),
    "unicode_separator_between_elements": _gateway_body("30").replace(
        b"<cmmMsgHeader>", "<cmmMsgHeader>\u3000".encode()
    ),
}


@pytest.mark.parametrize("name", sorted(_NOT_A_GATEWAY_REFUSAL))
def test_only_the_strict_gateway_envelope_is_recognised(name: str) -> None:
    assert decode_gateway_envelope(_NOT_A_GATEWAY_REFUSAL[name]) is None


@pytest.mark.parametrize(
    "fixture",
    [
        "error_gateway_key_not_registered.xml",
        "error_gateway_quota_exceeded.xml",
        "error_gateway_unregistered_ip.xml",
    ],
)
def test_recorded_gateway_fixtures_decode_as_xmltodict_does(fixture: str) -> None:
    from tests.unit.providers.test_error_envelopes import FIXTURES

    body = (FIXTURES / "datago" / fixture).read_bytes()

    assert decode_gateway_envelope(body) == decode_xml(body)


@pytest.mark.parametrize(
    ("path", "error"),
    [
        ("spec_executor", InvalidRequestError),
        ("datago_adapter", ParseError),
        ("semas_family", ParseError),
        ("localdata_family", ParseError),
    ],
)
@pytest.mark.parametrize("name", sorted(_NOT_A_GATEWAY_REFUSAL))
def test_other_xml_keeps_the_missing_extra_error(
    monkeypatch: pytest.MonkeyPatch, path: str, error: type[PublicDataError], name: str
) -> None:
    _block_xmltodict(monkeypatch)

    with pytest.raises(error) as caught:
        _PATHS[path](_NOT_A_GATEWAY_REFUSAL[name], "text/xml")

    assert type(caught.value) is error
    assert isinstance(caught.value.__cause__, ImportError)
    if path == "spec_executor":
        assert "kpubdata[xml]" in str(caught.value)


def test_hostile_input_returns_promptly() -> None:
    # Many unterminated candidate fields would make a backtracking pattern explode.
    bodies = [
        b"<OpenAPI_ServiceResponse><cmmMsgHeader>" + b"<a>x</a> " * 900,
        b"<OpenAPI_ServiceResponse><cmmMsgHeader>" + b"<a>" * 2700,
        b"<OpenAPI_ServiceResponse><cmmMsgHeader>" + b" " * 8000 + b"<",
        b"<?xml" + b" " * 8000,
        b"<" * 10_000_000,
    ]
    for body in bodies:
        started = time.perf_counter()
        assert decode_gateway_envelope(body) is None
        assert time.perf_counter() - started < 0.5


@pytest.mark.parametrize(
    "body",
    [
        "\ufeff".encode() + _gateway_body("30"),
        _gateway_body("30", auth_msg="LINE ONE\r\nLINE TWO\rLINE THREE"),
    ],
    ids=["byte_order_mark", "carriage_returns"],
)
def test_bom_and_line_endings_decode_as_xmltodict_does(body: bytes) -> None:
    assert decode_gateway_envelope(body) == decode_xml(body)
