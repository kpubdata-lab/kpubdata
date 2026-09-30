"""Public probe API and the explicit-keys-only mode (#694).

kpubdata-builder probes with a user's key and may only import the public
surface. Two things are pinned here: the probe is reachable from ``Client`` and
``kpubdata.__all__``, and a client built with ``env_keys=False`` never fills a
missing key from the environment -- otherwise a user's probe would silently run
on the operator's key and report a verdict that is not the user's.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest

import kpubdata
from kpubdata import PROBE_STATUSES, Client, KPubDataConfig, ProbeResult, _probe
from kpubdata.core.status import ProbeStatus
from kpubdata.transport.http import HttpTransport

_REAL_FACTORY = _probe.new_probe_transport
SENTINEL = "sentinel-key"
ENV_KEY = "env-operator-key"
DATASET = "datago.apt_trade"

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KPUBDATA_MODE", raising=False)
    monkeypatch.delenv("KPUBDATA_DATAGO_API_KEY", raising=False)
    monkeypatch.delenv("DATAGO_API_KEY", raising=False)


class _Recorder:
    """Stands in for the probe transport and records every outgoing request."""

    def __init__(self, handler: Handler) -> None:
        self.requests: list[httpx.Request] = []
        self.transports: list[HttpTransport] = []
        self._handler = handler

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._handler(request)

    def factory(self) -> HttpTransport:
        transport = _REAL_FACTORY()
        transport._client = httpx.Client(transport=httpx.MockTransport(self._handle))
        self.transports.append(transport)
        return transport


@pytest.fixture
def install(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[Handler], _Recorder]]:
    def _install(handler: Handler) -> _Recorder:
        recorder = _Recorder(handler)
        monkeypatch.setattr(_probe, "new_probe_transport", recorder.factory)
        return recorder

    yield _install


def _unreachable(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"the probe must not call: {request.url.host}")


def _ok_body() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "response": {
                "header": {"resultCode": "000", "resultMsg": "OK"},
                "body": {"items": {"item": []}, "totalCount": 0, "numOfRows": 10, "pageNo": 1},
            }
        },
    )


class TestPublicSurface:
    def test_probe_names_are_exported(self) -> None:
        assert "ProbeResult" in kpubdata.__all__
        assert "PROBE_STATUSES" in kpubdata.__all__

    def test_the_vocabulary_is_adr_0005(self) -> None:
        assert tuple(s.value for s in ProbeStatus) == PROBE_STATUSES

    def test_an_unknown_dataset_is_none(self) -> None:
        assert Client(env_keys=False).probe("datago.no_such_dataset") is None


class TestExplicitKeysOnly:
    def test_the_environment_is_not_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KPUBDATA_DATAGO_API_KEY", ENV_KEY)
        monkeypatch.setenv("DATAGO_API_KEY", ENV_KEY)
        assert KPubDataConfig(env_fallback=False).get_provider_key("datago") is None

    def test_the_default_still_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Backward compatibility: the default client keeps reading the environment."""
        monkeypatch.setenv("KPUBDATA_DATAGO_API_KEY", ENV_KEY)
        assert Client()._config.get_provider_key("datago") == ENV_KEY

    def test_no_key_means_no_call_and_auth_unknown(
        self, monkeypatch: pytest.MonkeyPatch, install: Callable[[Handler], _Recorder]
    ) -> None:
        monkeypatch.setenv("KPUBDATA_DATAGO_API_KEY", ENV_KEY)
        monkeypatch.setenv("DATAGO_API_KEY", ENV_KEY)
        recorder = install(_unreachable)

        result = Client(env_keys=False).probe(DATASET)

        assert result is not None
        assert result.status == "auth_unknown"
        assert recorder.requests == []
        assert ENV_KEY not in result.detail

    def test_probe_all_uses_no_env_key_either(
        self, monkeypatch: pytest.MonkeyPatch, install: Callable[[Handler], _Recorder]
    ) -> None:
        monkeypatch.setenv("KPUBDATA_DATAGO_API_KEY", ENV_KEY)
        recorder = install(_unreachable)

        results = Client(env_keys=False).probe_all(provider="datago")

        assert results
        assert {r.status for r in results} <= {"auth_unknown", "available"}
        assert recorder.requests == []

    def test_only_the_passed_key_is_sent(
        self, monkeypatch: pytest.MonkeyPatch, install: Callable[[Handler], _Recorder]
    ) -> None:
        monkeypatch.setenv("KPUBDATA_DATAGO_API_KEY", ENV_KEY)
        recorder = install(lambda _request: _ok_body())

        result = Client(provider_keys={"datago": SENTINEL}, env_keys=False).probe(DATASET)

        assert result is not None
        assert len(recorder.requests) == 1
        sent = str(recorder.requests[0].url)
        assert SENTINEL in sent
        assert ENV_KEY not in sent


class TestProbeTransport:
    def test_it_is_fast_fail_and_uncached(self) -> None:
        transport = _probe.new_probe_transport()
        assert transport._config.timeout == _probe.PROBE_TIMEOUT_SECONDS
        assert transport._config.max_retries == _probe.PROBE_RETRIES
        assert transport.cache is None

    def test_probe_all_shares_one_transport_and_closes_it(
        self, install: Callable[[Handler], _Recorder]
    ) -> None:
        recorder = install(lambda _request: _ok_body())

        Client(provider_keys={"datago": SENTINEL}, env_keys=False).probe_all(provider="datago")

        assert len(recorder.transports) == 1
        assert recorder.transports[0]._client is None


def _echo_key_500(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, text=f"upstream failed for {request.url}")


def _echo_key_403(request: httpx.Request) -> httpx.Response:
    return httpx.Response(403, text=f"key {SENTINEL} is not registered")


def _connect_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError(f"cannot connect to {request.url}", request=request)


class TestKeyNeverLeaks:
    @pytest.mark.parametrize("handler", [_echo_key_500, _echo_key_403, _connect_error])
    def test_detail_and_logs_carry_no_key(
        self,
        handler: Handler,
        install: Callable[[Handler], _Recorder],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        recorder = install(handler)
        caplog.set_level(logging.DEBUG)

        client = Client(provider_keys={"datago": SENTINEL}, env_keys=False)
        result = client.probe(DATASET)

        assert result is not None
        assert recorder.requests, "the probe should have called"
        assert result.status in PROBE_STATUSES
        assert result.status != "available"
        assert SENTINEL not in result.detail
        assert SENTINEL not in repr(result)
        assert SENTINEL not in repr(client._config)
        for record in caplog.records:
            assert SENTINEL not in record.getMessage()
            assert SENTINEL not in str(record.__dict__)

    def test_classify_redacts_before_truncating(self) -> None:
        """A key cut at the truncation boundary must not survive as a prefix."""
        padding = "x" * (120 - len(SENTINEL) // 2)
        unredacted = _probe.classify(RuntimeError(padding + SENTINEL))[1]
        assert SENTINEL[:4] in unredacted  # the case this test is about
        redacted = _probe.classify(RuntimeError(padding + SENTINEL), secrets=(SENTINEL,))[1]
        assert SENTINEL[:4] not in redacted


class TestCli:
    def test_probe_goes_through_the_client(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from kpubdata import cli

        calls: list[tuple[str, object]] = []

        def fake_probe_all(self: Client, *, provider: str | None = None) -> list[ProbeResult]:
            calls.append(("probe_all", provider))
            return [ProbeResult(DATASET, "svc", "available", "2026-09-30T00:00:00+00:00")]

        def fake_probe(self: Client, dataset_id: str) -> ProbeResult | None:
            calls.append(("probe", dataset_id))
            return ProbeResult(dataset_id, "svc", "available", "2026-09-30T00:00:00+00:00")

        monkeypatch.setattr(Client, "probe_all", fake_probe_all)
        monkeypatch.setattr(Client, "probe", fake_probe)

        output = str(tmp_path / "key-scope.json")
        assert cli.main(["probe", "--provider", "datago", "--output", output]) == 0
        assert cli.main(["probe", "--dataset", DATASET, "--output", output]) == 0
        assert calls == [("probe_all", "datago"), ("probe", DATASET)]


def test_the_httpx_request_log_line_is_masked(caplog: pytest.LogCaptureFixture) -> None:
    """httpx logs the full URL at INFO; the credential parameter must be masked."""
    caplog.set_level(logging.INFO, logger="httpx")
    url = httpx.URL(f"https://apis.data.go.kr/x?serviceKey={SENTINEL}&pageNo=1")
    logging.getLogger("httpx").info("HTTP Request: %s %s", "GET", url)
    message = caplog.records[-1].getMessage()
    assert SENTINEL not in message
    assert "pageNo=1" in message


def test_the_sgis_secret_is_not_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SGIS consumer secret is a credential too; explicit-keys-only skips its env var."""
    from kpubdata.exceptions import ConfigError
    from kpubdata.providers.sgis.auth import SgisAuthClient

    monkeypatch.setenv("KPUBDATA_SGIS_CONSUMER_SECRET", ENV_KEY)
    config = KPubDataConfig(provider_keys={"sgis": SENTINEL}, env_fallback=False)
    auth = SgisAuthClient(config=config, transport=HttpTransport())
    with pytest.raises(ConfigError) as excinfo:
        auth._resolve_credentials()
    assert SENTINEL not in str(excinfo.value)

    default = SgisAuthClient(
        config=KPubDataConfig(provider_keys={"sgis": SENTINEL}), transport=HttpTransport()
    )
    assert default._resolve_credentials() == (SENTINEL, ENV_KEY)
