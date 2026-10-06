"""A path-segment key with no ``param_name`` goes into the path, and nowhere else (#839).

The executor kept the key in ``params`` under ``__path_key__`` when the spec named no
parameter for it, then looked for it under ``""``: the URL was built with an empty key,
and the real one was sent as a query parameter called ``__path_key__`` with nothing
marking it secret — so it reached provenance, logs and error text as well.

No bundled spec declares ``path_segment`` without a ``param_name`` today; the spec schema
allows it.
"""

from __future__ import annotations

import json
import logging
import traceback
from dataclasses import replace
from typing import Any
from urllib.parse import quote, quote_plus, urlsplit

import httpx
import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.executor import SpecDatasetAdapter, SpecExecutor
from kpubdata.core.models import Query
from kpubdata.core.spec import AuthSpec, SpecDefinition
from kpubdata.exceptions import PublicDataError
from kpubdata.transport.http import HttpTransport, TransportConfig
from tests.unit.core.test_executor import _golden_spec, _ref

#: A stand-in value with the characters a data.go.kr key has.
_CANARY = "canary+value/for=path-key"
_FILTERS = {"LAWD_CD": "11680", "DEAL_YMD": "202401"}


def _forms() -> set[str]:
    return {_CANARY, quote(_CANARY, safe=""), quote_plus(_CANARY, safe="")}


def _spec(param_name: str | None) -> SpecDefinition:
    base = _golden_spec("apt_trade")
    return replace(
        base,
        auth=AuthSpec(type="path_segment", param_name=param_name, provider_key="datago"),
        endpoint=replace(base.endpoint, path_template="{base_url}/{key}/{operation}"),
    )


class _Network:
    def __init__(self, status: int = 200, location: str | None = None) -> None:
        self.status = status
        self.location = location
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status in (301, 302, 307):
            return httpx.Response(self.status, headers={"Location": self.location or "/"})
        if self.status != 200:
            return httpx.Response(self.status, text=f"rejected: {request.url}")
        envelope = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {"items": {"item": [{"aptNm": "a"}]}, "totalCount": 1},
            }
        }
        return httpx.Response(200, json=envelope)


@pytest.fixture()
def network(monkeypatch: pytest.MonkeyPatch) -> _Network:
    monkeypatch.delenv("KPUBDATA_MODE", raising=False)
    seen = _Network()
    real_client = httpx.Client

    def mocked_client(**kwargs: Any) -> httpx.Client:
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(seen.handle), **kwargs)

    monkeypatch.setattr(httpx, "Client", mocked_client)
    return seen


def _query(spec: SpecDefinition) -> Any:
    transport = HttpTransport(TransportConfig(max_retries=0))
    config = KPubDataConfig(provider_keys={"datago": _CANARY})
    adapter = SpecDatasetAdapter("datago", [spec], SpecExecutor(transport, config))
    try:
        return adapter.query_records(_ref(spec), Query(filters=dict(_FILTERS)))
    finally:
        transport.close()


@pytest.mark.parametrize("param_name", [None, "apikey"])
def test_the_key_is_in_the_path_and_not_in_the_query(
    network: _Network, param_name: str | None
) -> None:
    batch = _query(_spec(param_name))

    assert len(batch.items) == 1
    (request,) = network.requests
    parts = urlsplit(str(request.url))
    # In the path — as sent, or as httpx encodes it there.
    assert any(form in parts.path for form in _forms())
    # And in no query parameter, under any name.
    assert all(form not in parts.query for form in _forms())
    assert "__path_key__" not in parts.query
    assert "apikey" not in parts.query


@pytest.mark.parametrize("param_name", [None, "apikey"])
def test_the_key_is_not_in_what_the_batch_records(
    network: _Network, param_name: str | None
) -> None:
    batch = _query(_spec(param_name))

    dumped = json.dumps(batch.meta, ensure_ascii=False, default=str)
    assert "[REDACTED]" in str(batch.meta["provenance"]["url"])
    for form in _forms():
        assert form not in dumped


@pytest.mark.parametrize("param_name", [None, "apikey"])
def test_an_upstream_that_echoes_the_request_leaks_nothing(
    network: _Network, caplog: pytest.LogCaptureFixture, param_name: str | None
) -> None:
    network.status = 500

    with caplog.at_level(logging.DEBUG), pytest.raises(PublicDataError) as failure:
        _query(_spec(param_name))

    _assert_nothing_leaked(failure.value, caplog)
    assert len(network.requests) == 1


@pytest.mark.parametrize("param_name", [None, "apikey"])
def test_a_redirect_is_not_followed_and_leaks_nothing(
    network: _Network, caplog: pytest.LogCaptureFixture, param_name: str | None
) -> None:
    """A request that carries the key in its path is a credentialed one (#812)."""
    network.status = 302
    network.location = f"https://elsewhere.example/moved/{quote(_CANARY, safe='')}"

    with caplog.at_level(logging.DEBUG), pytest.raises(PublicDataError) as failure:
        _query(_spec(param_name))

    # Only the first request went out: the key was not taken to the new host.
    assert [request.url.host for request in network.requests] == ["apis.data.go.kr"]
    _assert_nothing_leaked(failure.value, caplog)


def _assert_nothing_leaked(error: BaseException, caplog: pytest.LogCaptureFixture) -> None:
    rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    logged = caplog.text + "".join(str(record.__dict__) for record in caplog.records)
    for form in _forms():
        assert form not in str(error)
        assert form not in rendered
        assert form not in logged


# --- The masking that the tests above exposed ---


@pytest.mark.parametrize(
    "query",
    ["", "?page=1", "?page=1&size=100", "?serviceKey=other-secret&page=1"],
)
def test_a_key_in_the_path_is_masked_whatever_the_query_holds(query: str) -> None:
    """With a key in the path and a query that needed no masking, the URL came back as
    it went in: the path had been masked, and then the original was returned (#839).
    No provider that keeps its key in the path sends a query today, so nothing showed."""
    from kpubdata.transport.http import _mask_url

    url = f"https://apis.example.test/svc/{_CANARY}/op{query}"

    masked = _mask_url(url, secret_values=(_CANARY,))

    assert _CANARY not in masked
    assert "/svc/[REDACTED]/op" in masked
    assert "page=1" in masked or not query
    assert "other-secret" not in masked


def test_a_url_with_nothing_to_mask_comes_back_unchanged() -> None:
    """Negative: without secret values a URL with an ordinary query is not rebuilt."""
    from kpubdata.transport.http import _mask_url

    url = "https://apis.example.test/svc/op?b=2&a=1&flag"

    assert _mask_url(url) == url
