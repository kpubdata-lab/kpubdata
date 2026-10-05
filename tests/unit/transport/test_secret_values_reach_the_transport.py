"""A key sent under a name the sensitive-name list lacks is still masked (#805).

kpubdata masks a credential by parameter name (``SENSITIVE_PARAM_KEYS``) and by value
(``secret_values``). The spec executor and the legacy ``datago`` adapter passed no value,
so a key under an unlisted name — a spec's own ``auth.param_name``, or
``datago.generic``'s ``_service_key_param`` — had nothing to be recognised by.

These run through the real ``HttpTransport``; only the socket is replaced.
"""

from __future__ import annotations

import dataclasses
import logging
import traceback
from typing import cast
from unittest.mock import patch

import httpx
import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.executor import SpecDatasetAdapter, SpecExecutor
from kpubdata.core.models import Query
from kpubdata.exceptions import PublicDataError
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.transport._sensitive import SENSITIVE_PARAM_KEYS
from kpubdata.transport.http import HttpTransport, TransportConfig
from tests.unit.core.test_executor import _golden_spec, _ref

#: A stand-in value. Named and spelt so that a secret scanner does not take it for a key.
_CANARY = "canary-value-for-masking-test"
#: Not a credential name as far as the name list knows.
_UNLISTED = "accessCode"


def _rendered(error: BaseException) -> str:
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


def _send_500(request: httpx.Request, **_kwargs: object) -> httpx.Response:
    # The response carries the request httpx built — final URL, key included.
    return httpx.Response(status_code=500, request=request)


def test_the_name_used_here_is_not_on_the_list() -> None:
    assert _UNLISTED.casefold() not in {name.casefold() for name in SENSITIVE_PARAM_KEYS}


def test_the_spec_executor_masks_a_key_under_an_unlisted_parameter_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = _golden_spec("apt_trade")
    spec = dataclasses.replace(spec, auth=dataclasses.replace(spec.auth, param_name=_UNLISTED))
    transport = HttpTransport(TransportConfig(max_retries=0))
    config = KPubDataConfig(provider_keys={"datago": _CANARY})
    adapter = SpecDatasetAdapter("datago", [spec], SpecExecutor(transport, config))
    sent: list[str] = []

    def send(request: httpx.Request, **kwargs: object) -> httpx.Response:
        sent.append(str(request.url))
        return _send_500(request, **kwargs)

    with (
        patch("kpubdata.transport.http.httpx.Client.send", side_effect=send),
        caplog.at_level(logging.DEBUG),
        pytest.raises(PublicDataError) as excinfo,
    ):
        adapter.query_records(_ref(spec), Query(filters={"LAWD_CD": "11680", "DEAL_YMD": "202401"}))

    # The key did travel under the unlisted name — otherwise the test shows nothing.
    assert sent and f"{_UNLISTED}={_CANARY}" in sent[0]
    assert _CANARY not in str(excinfo.value)
    assert _CANARY not in _rendered(excinfo.value)
    assert _CANARY not in caplog.text
    assert _CANARY not in "".join(str(record.__dict__) for record in caplog.records)


def test_datago_generic_masks_a_key_under_a_caller_named_parameter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport = HttpTransport(TransportConfig(max_retries=0))
    adapter = DataGoAdapter(
        config=KPubDataConfig(provider_keys={"datago": _CANARY}),
        transport=transport,
    )
    generic = next(d for d in adapter.list_datasets() if d.raw_metadata.get("generic"))
    sent: list[str] = []

    def send(request: httpx.Request, **kwargs: object) -> httpx.Response:
        sent.append(str(request.url))
        return _send_500(request, **kwargs)

    with (
        patch("kpubdata.transport.http.httpx.Client.send", side_effect=send),
        caplog.at_level(logging.DEBUG),
        pytest.raises(PublicDataError) as excinfo,
    ):
        adapter.call_raw(
            generic,
            "getList",
            cast(
                "dict[str, object]",
                {
                    "_base_url": "https://apis.data.go.kr/1234567/SomeService",
                    "_service_key_param": _UNLISTED,
                    "pageNo": "1",
                },
            ),
        )

    assert sent and f"{_UNLISTED}={_CANARY}" in sent[0]
    assert _CANARY not in str(excinfo.value)
    assert _CANARY not in _rendered(excinfo.value)
    assert _CANARY not in caplog.text
    assert _CANARY not in "".join(str(record.__dict__) for record in caplog.records)
