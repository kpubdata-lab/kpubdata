"""Unit tests for core/bridge.py — composite merge·routing·registry integration validation.

FakeInnerAdapter mimics the protocol surface of a catalog-based built-in adapter,
while the spec side uses bundled golden spec + FakeTransport executor to validate
actual merge operations.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from kpubdata import Client
from kpubdata.config import KPubDataConfig
from kpubdata.core.bridge import CompositeProviderAdapter
from kpubdata.core.executor import SpecDatasetAdapter, SpecExecutor
from kpubdata.core.models import DatasetRef, Query, RecordBatch
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.core.representation import Representation
from kpubdata.core.spec import SpecDefinition, load_spec_file
from kpubdata.exceptions import DatasetNotFoundError
from kpubdata.registry import ProviderRegistry
from kpubdata.transport.http import HttpTransport

SPECS_DIR = Path(__file__).resolve().parents[3] / "src" / "kpubdata" / "specs"


class FakeResponse:
    """Mimics the minimal interface of httpx.Response."""

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.headers = {"content-type": "application/json"}


class FakeTransport:
    """Records calls and returns standard envelope responses."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        json_body: object = None,
        dataset_id: str | None = None,
        provider: str | None = None,
        secret_values: tuple[str, ...] = (),
    ) -> FakeResponse:
        self.calls.append({"url": url, "params": dict(params or {})})
        payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {
                    "items": {"item": [{"from": "spec"}]},
                    "totalCount": "1",
                },
            }
        }
        return FakeResponse(json.dumps(payload).encode())


class FakeConfig(KPubDataConfig):
    """Config with key lookup replaced by fixed values."""

    def get_provider_key(self, provider: str) -> str | None:
        return f"test-key-{provider}"

    def require_provider_key(self, provider: str) -> str:
        return f"test-key-{provider}"


class FakeInnerAdapter:
    """Catalog adapter mimic — provides 1 spec key (apt_trade) and 2 catalog-only keys."""

    def __init__(self) -> None:
        self.query_calls: list[str] = []
        self.raw_calls: list[str] = []

    @property
    def name(self) -> str:
        return "datago"

    requires_api_key = True

    @staticmethod
    def _ref(key: str, name: str) -> DatasetRef:
        from kpubdata.core.capability import Operation

        return DatasetRef(
            id=f"datago.{key}",
            provider="datago",
            dataset_key=key,
            name=name,
            representation=Representation.API_JSON,
            operations=frozenset({Operation.LIST, Operation.RAW}),
        )

    def list_datasets(self) -> list[DatasetRef]:
        return [self._ref("apt_trade", "카탈로그 아파트"), self._ref("air_quality", "대기오염")]

    def search_datasets(self, text: str) -> list[DatasetRef]:
        return [ref for ref in self.list_datasets() if text in ref.name]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        for ref in self.list_datasets():
            if ref.dataset_key == dataset_key:
                return ref
        raise DatasetNotFoundError(f"unknown: {dataset_key}", provider="datago")

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        self.query_calls.append(dataset.dataset_key)
        return RecordBatch(items=[{"from": "inner"}], dataset=dataset)

    def get_schema(self, dataset: DatasetRef) -> None:
        return None

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        self.raw_calls.append(dataset.dataset_key)
        return {"from": "inner"}


def _golden(key: str) -> SpecDefinition:
    return load_spec_file(SPECS_DIR / "datago" / f"{key}.yaml")


@pytest.fixture()
def transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture()
def spec_adapter(transport: FakeTransport) -> SpecDatasetAdapter:
    executor = SpecExecutor(transport, FakeConfig())
    return SpecDatasetAdapter("datago", [_golden("apt_trade"), _golden("village_fcst")], executor)


@pytest.fixture()
def inner() -> FakeInnerAdapter:
    return FakeInnerAdapter()


@pytest.fixture()
def composite(
    inner: FakeInnerAdapter, spec_adapter: SpecDatasetAdapter
) -> CompositeProviderAdapter:
    return CompositeProviderAdapter(inner, spec_adapter)


# ----------------------------------------------------------------------
# Merge rules
# ----------------------------------------------------------------------


def test_list_datasets_spec_wins_and_appends(
    composite: CompositeProviderAdapter, inner: FakeInnerAdapter
) -> None:
    """Overlapping keys are replaced by spec references; spec-only keys are appended at end."""
    refs = composite.list_datasets()
    by_key = {ref.dataset_key: ref for ref in refs}

    assert set(by_key) == {"apt_trade", "air_quality", "village_fcst"}
    # apt_trade exists in catalog but spec wins (distinguished by title).
    assert by_key["apt_trade"].name == _golden("apt_trade").title
    # Catalog-only keys remain unchanged (same content).
    assert by_key["air_quality"].name == "대기오염"


def test_search_datasets_merges_without_duplicates(composite: CompositeProviderAdapter) -> None:
    """Search result merge has no key duplicates (spec takes precedence)."""
    hits = composite.search_datasets("아파트")
    keys = [ref.dataset_key for ref in hits]
    assert keys.count("apt_trade") == 1
    # Both spec title and catalog match, but only 1 result (spec takes precedence).
    assert "apt_trade" in keys


def test_provider_name_mismatch_rejected(
    inner: FakeInnerAdapter, spec_adapter: SpecDatasetAdapter
) -> None:
    """Merging different Providers is rejected."""
    other = SpecDatasetAdapter("seoul", [], SpecExecutor(FakeTransport(), FakeConfig()))
    with pytest.raises(ValueError, match="같은 Provider"):
        CompositeProviderAdapter(inner, other)


# ----------------------------------------------------------------------
# Routing
# ----------------------------------------------------------------------


def test_get_dataset_routes_spec_first(composite: CompositeProviderAdapter) -> None:
    """Spec-owned keys return spec references."""
    ref = composite.get_dataset("apt_trade")
    assert ref.name == _golden("apt_trade").title
    catalogue_only = composite.get_dataset("air_quality")
    assert catalogue_only.name == "대기오염"
    with pytest.raises(DatasetNotFoundError):
        composite.get_dataset("nope")


def test_query_records_routes_by_owner(
    composite: CompositeProviderAdapter,
    inner: FakeInnerAdapter,
    transport: FakeTransport,
) -> None:
    """Spec-owned queries go to executor; catalog-owned queries go to inner adapter."""
    spec_ref = composite.get_dataset("apt_trade")
    batch = composite.query_records(spec_ref, Query())
    assert batch.items == [{"from": "spec"}]
    assert inner.query_calls == []

    inner_ref = composite.get_dataset("air_quality")
    inner_batch = composite.query_records(inner_ref, Query())
    assert inner_batch.items == [{"from": "inner"}]
    assert inner.query_calls == ["air_quality"]


def test_call_raw_routes_by_owner(
    composite: CompositeProviderAdapter, inner: FakeInnerAdapter
) -> None:
    """Raw escape hatch also follows ownership rules."""
    spec_ref = composite.get_dataset("village_fcst")
    raw = composite.call_raw(spec_ref, "raw", {})
    assert isinstance(raw, dict) and "response" in raw
    assert inner.raw_calls == []

    inner_raw = composite.call_raw(composite.get_dataset("air_quality"), "raw", {})
    assert inner_raw == {"from": "inner"}


def test_requires_api_key_or_semantics(inner: FakeInnerAdapter) -> None:
    """requires_api_key is logical OR."""
    no_key_spec = SpecDatasetAdapter("datago", [], SpecExecutor(FakeTransport(), FakeConfig()))
    inner.requires_api_key = False
    composite = CompositeProviderAdapter(inner, no_key_spec)
    assert composite.requires_api_key is False
    inner.requires_api_key = True
    assert CompositeProviderAdapter(inner, no_key_spec).requires_api_key is True


# ----------------------------------------------------------------------
# Registry integration
# ----------------------------------------------------------------------


def test_registry_accepts_composite(composite: CompositeProviderAdapter) -> None:
    """Composite passes protocol and capability validation at registration."""
    registry = ProviderRegistry()
    registry.register(composite)
    assert "datago" in registry
    adapter = registry.get("datago")
    assert isinstance(adapter, CompositeProviderAdapter)
    assert isinstance(adapter, ProviderAdapter)  # runtime_checkable protocol


def test_client_resolves_spec_dataset_end_to_end() -> None:
    """Client → composite → spec executor path works in real client."""
    payload = {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "OK"},
            "body": {"items": {"item": {"category": "T1H"}}, "totalCount": "1"},
        }
    }
    mock_response = httpx.Response(
        status_code=200,
        content=json.dumps(payload).encode(),
        request=httpx.Request("GET", "http://example.com"),
    )
    with patch.object(HttpTransport, "request", return_value=mock_response) as mock_request:
        client = Client(provider_keys={"datago": "test-key"}, cache=False)
        dataset = client.dataset("datago.village_fcst")
        batch = dataset.list()
        assert isinstance(batch, RecordBatch)
        assert batch.items == [{"category": "T1H"}]
        assert mock_request.call_count == 1
        # Proof of spec path: format_param value is spec's uppercase "JSON" (adapter uses lowercase "json").
        kwargs = mock_request.call_args.kwargs
        assert kwargs["params"]["dataType"] == "JSON"


def test_client_catalogue_dataset_unaffected() -> None:
    """Catalog datasets not in spec use existing adapter path unchanged."""
    payload = {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "OK"},
            "body": {"items": {"item": {"a": 1}}, "totalCount": "1"},
        }
    }
    mock_response = httpx.Response(
        status_code=200,
        content=json.dumps(payload).encode(),
        request=httpx.Request("GET", "http://example.com"),
    )
    with patch.object(HttpTransport, "request", return_value=mock_response) as mock_request:
        client = Client(provider_keys={"datago": "test-key"}, cache=False)
        dataset = client.dataset("datago.air_quality")
        batch = dataset.list()
        assert len(batch.items) == 1
        kwargs = mock_request.call_args.kwargs
        params = kwargs["params"]
        # Proof of adapter path: format parameter value is lowercase "json" (spec executor uses uppercase).
        format_values = {
            value for value in params.values() if value in {"json", "JSON", "xml", "XML"}
        }
        assert format_values == {"json"}
