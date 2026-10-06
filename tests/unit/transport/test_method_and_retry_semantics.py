"""What a spec's ``method`` means when it is executed, and what is retried (#844).

Two things were found by reading and are pinned here:

- The spec schema allows ``method: POST``, and the spec executor sent every request as a
  ``GET`` whatever the spec said. A POST spec is now refused: where its parameters would
  go — body or query — is not defined, and sending it as something else is not an answer.
- The transport retried every method on a timeout or a retryable status. A method that
  is not idempotent is now sent once.

No bundled spec declares ``POST`` (all 25 are ``GET``), and nothing in the library sends
one, so no shipped behaviour changes.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from kpubdata import discover_specs
from kpubdata.config import KPubDataConfig
from kpubdata.core.executor import SpecDatasetAdapter, SpecExecutor
from kpubdata.core.models import Query
from kpubdata.core.spec import SpecDefinition, from_mapping
from kpubdata.exceptions import InvalidRequestError, PublicDataError
from kpubdata.transport.http import HttpTransport, TransportConfig
from tests.unit.core.test_executor import _golden_spec, _ref

_SCHEMA = Path(__file__).resolve().parents[3] / "src" / "kpubdata" / "specs" / "schema.json"
#: A stand-in value. Named and spelt so that a secret scanner does not take it for a key.
_CANARY = "canary-value-for-retry-test"


class _Network:
    """Answers every request the same way and counts them by method."""

    def __init__(self, *, status: int = 200, timeout: bool = False) -> None:
        self.status = status
        self.timeout = timeout
        self.methods: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.methods.append(request.method)
        if self.timeout:
            raise httpx.ReadTimeout("read timed out", request=request)
        return httpx.Response(self.status, json={"ok": self.status == 200})


@pytest.fixture()
def network(monkeypatch: pytest.MonkeyPatch) -> _Network:
    monkeypatch.delenv("KPUBDATA_MODE", raising=False)
    seen = _Network()
    real_client = httpx.Client

    def mocked_client(**kwargs: Any) -> httpx.Client:
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(seen.handle), **kwargs)

    monkeypatch.setattr(httpx, "Client", mocked_client)
    # Retries run for real; only their waiting is skipped.
    monkeypatch.setattr("kpubdata.transport.http.time.sleep", lambda _seconds: None)
    return seen


def _request(method: str, **kwargs: Any) -> None:
    transport = HttpTransport(TransportConfig(max_retries=3, retry_backoff_factor=0))
    try:
        transport.request(method, "https://api.example.test/items", **kwargs)
    finally:
        transport.close()


# --- What the transport repeats ---


@pytest.mark.parametrize("method", ["POST", "PATCH", "post"])
@pytest.mark.parametrize("failure", ["500", "503", "429", "timeout"])
def test_a_method_that_is_not_idempotent_is_sent_once(
    network: _Network, method: str, failure: str
) -> None:
    network.timeout = failure == "timeout"
    network.status = 200 if network.timeout else int(failure)

    with pytest.raises(PublicDataError):
        _request(method, json_body={"n": 1})

    assert network.methods == [method.upper()]


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE", "HEAD"])
def test_an_idempotent_method_is_still_retried(network: _Network, method: str) -> None:
    """Negative: the retry policy for everything the library sends today is unchanged."""
    network.status = 503

    with pytest.raises(PublicDataError):
        _request(method)

    assert network.methods == [method] * 4  # the first attempt and max_retries=3 more


def test_a_post_that_carries_a_key_is_sent_once_and_leaks_nothing(network: _Network) -> None:
    network.status = 500

    with pytest.raises(PublicDataError) as failure:
        _request("POST", params={"serviceKey": _CANARY}, secret_values=(_CANARY,))

    assert network.methods == ["POST"]
    assert _CANARY not in str(failure.value)


def test_a_post_that_succeeds_is_answered(network: _Network) -> None:
    """Negative: sending once is not refusing."""
    _request("POST", json_body={"n": 1})

    assert network.methods == ["POST"]


# --- What a spec may declare, and what the executor sends ---


def test_the_schema_and_the_parser_allow_get_and_post_only() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    allowed = schema["properties"]["endpoint"]["properties"]["method"]["enum"]

    assert sorted(allowed) == ["GET", "POST"]


def test_no_bundled_spec_declares_anything_but_get() -> None:
    """Why refusing POST below changes nothing that ships."""
    assert {spec.endpoint.method for spec in discover_specs()} == {"GET"}


def _adapter(spec: SpecDefinition) -> tuple[SpecDatasetAdapter, HttpTransport]:
    transport = HttpTransport(TransportConfig(max_retries=0))
    config = KPubDataConfig(provider_keys={"datago": _CANARY})
    return SpecDatasetAdapter("datago", [spec], SpecExecutor(transport, config)), transport


def test_a_get_spec_is_sent_as_a_get(network: _Network) -> None:
    spec = _golden_spec("apt_trade")
    adapter, transport = _adapter(spec)
    try:
        with pytest.raises(PublicDataError):
            # The stub's answer is not this dataset's envelope; the request was sent.
            adapter.query_records(_ref(spec), Query(filters={"LAWD_CD": "1", "DEAL_YMD": "202401"}))
    finally:
        transport.close()

    assert network.methods == ["GET"]


def test_a_post_spec_is_refused_before_anything_is_sent(network: _Network) -> None:
    """It used to go out as a GET, whatever the spec said."""
    base = _golden_spec("apt_trade")
    spec = replace(base, endpoint=replace(base.endpoint, method="POST"))
    adapter, transport = _adapter(spec)
    try:
        with pytest.raises(InvalidRequestError, match="POST") as refused:
            adapter.query_records(_ref(spec), Query(filters={"LAWD_CD": "1", "DEAL_YMD": "202401"}))
    finally:
        transport.close()

    assert network.methods == []
    assert spec.id in str(refused.value)
    assert _CANARY not in str(refused.value)


@pytest.mark.parametrize("method", ["DELETE", "PUT", "get", ""])
def test_a_method_outside_the_schema_does_not_parse(method: str) -> None:
    path = _SCHEMA.parent / "datago" / "apt_trade.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["endpoint"]["method"] = method

    if method == "":
        # An empty method is read as the default, GET.
        assert from_mapping(raw).endpoint.method == "GET"
        return
    with pytest.raises(InvalidRequestError, match="method"):
        from_mapping(raw)
