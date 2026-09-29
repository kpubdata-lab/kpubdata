"""The provenance URL never carries the API key, however it is encoded (#612).

``_build_provenance`` used ``str.replace`` with the plain key. The response URL is
percent-encoded, so a data.go.kr key with ``+``, ``/`` or ``=`` survived as
``abc%2BDEF%2Fghi%3D%3D``; a path-segment key had already been removed from
``params`` and was not masked at all.
"""

from __future__ import annotations

import json
from dataclasses import replace
from urllib.parse import quote, quote_plus

import httpx
import pytest

from kpubdata.core.executor import SpecExecutor
from kpubdata.core.models import Query
from kpubdata.core.spec import AuthSpec, SpecDefinition
from tests.unit.core.test_executor import (
    FakeConfig,
    FakeResponse,
    FakeTransport,
    _golden_spec,
    _ref,
    _standard_envelope,
)

KEY = "abc+DEF/ghi=="


class _Config(FakeConfig):
    def get_provider_key(self, provider: str) -> str | None:
        return KEY

    def require_provider_key(self, provider: str) -> str:
        return KEY


class _UrlTransport(FakeTransport):
    """Gives each response the URL httpx would have requested."""

    def request(self, method: str, url: str, *, params=None, **kwargs) -> FakeResponse:  # type: ignore[override]
        response = super().request(method, url, params=params, **kwargs)
        response.url = str(httpx.URL(url, params=params or {}))  # type: ignore[attr-defined]
        return response


def _key_forms() -> set[str]:
    return {KEY, quote(KEY, safe=""), quote_plus(KEY, safe="")}


def _run(spec: SpecDefinition) -> tuple[dict[str, object], str]:
    transport = _UrlTransport([_standard_envelope([{"x": "1"}], total_count=1)])
    executor = SpecExecutor(transport, _Config())  # type: ignore[arg-type]
    batch = executor.query(spec, _ref(spec), Query())
    provenance = batch.meta["provenance"]
    assert isinstance(provenance, dict)
    return provenance, json.dumps(batch.meta, ensure_ascii=False, default=str)


def _assert_no_key(dumped: str) -> None:
    for form in _key_forms():
        assert form not in dumped, form


def test_an_encoded_query_key_is_masked() -> None:
    provenance, dumped = _run(_golden_spec("apt_trade"))
    assert "url" in provenance
    assert "serviceKey=[REDACTED]" in str(provenance["url"])
    _assert_no_key(dumped)


def test_a_path_segment_key_is_masked() -> None:
    base = _golden_spec("apt_trade")
    spec = replace(
        base,
        auth=AuthSpec(type="path_segment", param_name="apikey", provider_key="datago"),
        endpoint=replace(base.endpoint, path_template="{base_url}/{key}/{operation}"),
    )
    provenance, dumped = _run(spec)
    assert "url" in provenance
    assert "[REDACTED]" in str(provenance["url"])
    _assert_no_key(dumped)


@pytest.mark.parametrize("name", ["KEY", "OC", "myAuth"])
def test_the_spec_auth_parameter_is_masked_by_name(name: str) -> None:
    base = _golden_spec("apt_trade")
    spec = replace(base, auth=replace(base.auth, param_name=name))
    provenance, dumped = _run(spec)
    assert "url" in provenance
    assert provenance["params"][name] == "[REDACTED]"  # type: ignore[index]
    _assert_no_key(dumped)
