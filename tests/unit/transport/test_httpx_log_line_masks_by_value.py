"""The line httpx logs for a request holds no key, wherever the key travels (#821).

httpx logs ``HTTP Request: GET <url> ...`` at INFO for every request. kpubdata's filter on
that logger masked by parameter name only, so a key in a path segment (seoul, fds, bok) or
under a name the list lacks went to the log of any application that shows INFO.

These go through the real ``HttpTransport`` and a real ``httpx.Client``; only the network
is replaced (``httpx.MockTransport``), so the line is the one httpx itself writes.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from kpubdata import Client
from kpubdata.exceptions import PublicDataError
from kpubdata.transport import http as transport_module
from kpubdata.transport._sensitive import SENSITIVE_PARAM_KEYS, _secret_forms
from kpubdata.transport.http import HttpTransport, TransportConfig

#: A stand-in value with the characters a data.go.kr key has, which a URL encodes.
_CANARY = "canary-value+for/masking=test"
_UNLISTED = "accessCode"


class _Network:
    """Answers every request and keeps the URLs it was sent."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.urls.append(str(request.url))
        return httpx.Response(200, json={})


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


@pytest.fixture()
def httpx_lines(caplog: pytest.LogCaptureFixture) -> Iterator[list[str]]:
    """Every record of the ``httpx`` logger, formatted, at DEBUG."""
    lines: list[str] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(record.getMessage())

    handler = _Collect(level=logging.DEBUG)
    logger = logging.getLogger("httpx")
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        with caplog.at_level(logging.DEBUG):
            yield lines
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


def _sent_the_key(urls: list[str]) -> bool:
    """Whether a URL carried the key, plain or percent-encoded."""
    forms = _secret_forms((_CANARY,))
    return any(form in url for url in urls for form in forms)


def _assert_no_key(lines: list[str], caplog: pytest.LogCaptureFixture) -> None:
    logged = "\n".join(lines) + caplog.text
    for form in _secret_forms((_CANARY,)):
        assert form not in logged


@pytest.mark.parametrize(
    ("dataset_id", "filters"),
    [
        ("seoul.bike_station_master", {}),
        ("fds.traceability_item", {}),
        ("bok.base_rate", {"start_date": "202401", "end_date": "202402"}),
    ],
)
def test_a_provider_with_the_key_in_the_path_logs_no_key(
    network: _Network,
    httpx_lines: list[str],
    caplog: pytest.LogCaptureFixture,
    dataset_id: str,
    filters: dict[str, str],
) -> None:
    provider = dataset_id.split(".")[0]
    client = Client(provider_keys={provider: _CANARY}, env_keys=False, max_retries=0)
    try:
        # The empty answer is not a valid payload; the request was still sent.
        with contextlib.suppress(PublicDataError):
            client.dataset(dataset_id).list(**filters)
    finally:
        client.close()

    # The key did travel in the URL, and httpx did log the request — or this shows nothing.
    assert _sent_the_key(network.urls)
    assert any("HTTP Request" in line for line in httpx_lines)
    assert "[REDACTED]" in "\n".join(httpx_lines)
    _assert_no_key(httpx_lines, caplog)


def _request(network: _Network, **kwargs: Any) -> None:
    del network
    transport = HttpTransport(TransportConfig(max_retries=0))
    try:
        transport.request("GET", "https://api.example.test/v1/items", **kwargs)
    finally:
        transport.close()


def test_a_key_under_an_unlisted_parameter_name_is_not_in_the_httpx_line(
    network: _Network, httpx_lines: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    assert _UNLISTED.casefold() not in {name.casefold() for name in SENSITIVE_PARAM_KEYS}

    _request(network, params={_UNLISTED: _CANARY, "page": "1"}, secret_values=(_CANARY,))

    assert _sent_the_key(network.urls)
    (line,) = [line for line in httpx_lines if "HTTP Request" in line]
    assert "page=1" in line
    assert f"{_UNLISTED}=[REDACTED]" in line
    _assert_no_key(httpx_lines, caplog)


def test_without_the_filter_the_same_calls_do_log_the_key(
    network: _Network, httpx_lines: list[str]
) -> None:
    """The checks above look where the key would be: take the filter off and it is there."""
    logger = logging.getLogger("httpx")
    HttpTransport(TransportConfig(max_retries=0)).close()  # makes sure the filter is installed
    filters = [
        f for f in logger.filters if isinstance(f, transport_module._HttpxUrlRedactingFilter)
    ]
    assert filters
    for installed in filters:
        logger.removeFilter(installed)
    try:
        transport = HttpTransport(TransportConfig(max_retries=0))
        # A new transport would put the filter back; keep it off for this call.
        for again in list(logger.filters):
            if isinstance(again, transport_module._HttpxUrlRedactingFilter):
                logger.removeFilter(again)
        try:
            transport.request(
                "GET",
                f"https://api.example.test/{_CANARY.replace('/', '%2F')}/json",
                params={_UNLISTED: _CANARY},
                secret_values=(_CANARY,),
            )
        finally:
            transport.close()
    finally:
        transport_module._install_httpx_redaction()

    assert _sent_the_key(network.urls)
    assert _sent_the_key(httpx_lines)


def test_another_requests_values_are_not_applied_outside_its_call(
    network: _Network, httpx_lines: list[str]
) -> None:
    """Negative: the values are known for one send only. A later request that happens to
    carry the same text as an ordinary value is logged as it is."""
    _request(network, params={_UNLISTED: "plain-value"}, secret_values=("plain-value",))
    _request(network, params={"q": "plain-value"})

    first, second = [line for line in httpx_lines if "HTTP Request" in line]
    assert "plain-value" not in first
    assert "q=plain-value" in second
    assert transport_module._in_flight_secrets.get() == ()
