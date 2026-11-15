"""Authentication and allowlist parity for raw spec requests (#972)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.executor import SpecExecutor
from kpubdata.core.spec import AuthSpec, SpecDefinition
from kpubdata.exceptions import InvalidRequestError
from tests.unit.core.test_executor import (
    FakeTransport,
    _golden_spec,
    _make_executor,
    _standard_envelope,
)


class _CountingConfig(KPubDataConfig):
    """Count credential accesses without using any real environment secrets."""

    def __init__(self) -> None:
        super().__init__(provider_keys={"datago": "SENTINEL_KEY_972"}, env_fallback=False)
        self.lookups = 0

    def require_provider_key(self, provider: str) -> str:
        self.lookups += 1
        return super().require_provider_key(provider)


def _path_spec() -> SpecDefinition:
    base = _golden_spec("apt_trade")
    return replace(
        base,
        auth=AuthSpec(type="path_segment", provider_key="datago"),
        endpoint=replace(
            base.endpoint,
            base_url="https://apis.data.go.kr/api",
            path_template="https://apis.data.go.kr/api/{key}/{operation}",
        ),
    )


def test_raw_path_segment_key_is_in_url_not_query_params() -> None:
    spec = _path_spec()
    transport = FakeTransport([_standard_envelope([], total_count=0)])
    executor = _make_executor(transport)

    result = executor.request_raw(spec, {"district": "11000"})

    assert "response" in result
    assert len(transport.calls) == 1
    sent = transport.calls[0]
    assert "test-key-datago" in str(sent["url"])
    assert sent["params"] == {"district": "11000"}
    assert "__path_key__" not in str(sent["params"])


def test_raw_query_param_key_cannot_be_overridden_by_untrusted_filter() -> None:
    spec = _golden_spec("apt_trade")
    transport = FakeTransport([_standard_envelope([], total_count=0)])
    executor = _make_executor(transport)

    executor.request_raw(spec, {"serviceKey": "spoofed-raw-key", "region": "11000"})

    assert transport.calls[0]["params"] == {
        "serviceKey": "test-key-datago",
        "region": "11000",
        "resultType": "json",
    }


@pytest.mark.parametrize("use_path_template", [False, True])
def test_host_validation_precedes_credential_lookup(use_path_template: bool) -> None:
    config = _CountingConfig()
    transport = FakeTransport()
    spec = _golden_spec("apt_trade")
    if use_path_template:
        spec = replace(
            spec,
            endpoint=replace(
                spec.endpoint,
                base_url="https://apis.data.go.kr/api",
                path_template="https://untrusted.example/api/{operation}",
            ),
        )
    else:
        spec = replace(
            spec,
            endpoint=replace(spec.endpoint, base_url="https://untrusted.example/api"),
        )
    executor = SpecExecutor(transport, config)

    with pytest.raises(InvalidRequestError, match="allowlist") as failure:
        executor.request_raw(spec, {"region": "11000"})

    assert "SENTINEL_KEY_972" not in str(failure.value)
    assert config.lookups == 0
    assert transport.calls == []


def test_missing_path_placeholder_fails_without_credential_lookup() -> None:
    config = _CountingConfig()
    transport = FakeTransport()
    base = _path_spec()
    spec = replace(
        base,
        endpoint=replace(base.endpoint, path_template="https://apis.data.go.kr/api/operation"),
    )

    with pytest.raises(InvalidRequestError, match="path_template"):
        SpecExecutor(transport, config).request_raw(spec, {"region": "11000"})

    assert config.lookups == 0
    assert transport.calls == []
