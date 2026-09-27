"""National Institute of Korean Language adapter contract tests (#222)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.providers.korean import KoreanAdapter
from kpubdata.transport.http import HttpTransport
from tests.contract.provider_adapter import ProviderAdapterContract
from tests.unit.providers.datago.conftest import FakeResponse

_FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "korean"


def _load_fixture(name: str) -> bytes:
    return (_FIXTURE_DIR / name).read_bytes()


class _FixtureTransport:
    def __init__(self, fixture_names: list[str]) -> None:
        self._responses = [FakeResponse(_load_fixture(name)) for name in fixture_names]
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._responses.pop(0)


def _build_adapter(fixture_names: list[str]) -> ProviderAdapter:
    transport = _FixtureTransport(fixture_names)
    return KoreanAdapter(
        config=KPubDataConfig(provider_keys={"korean": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )


class TestKoreanDictSearchContract(ProviderAdapterContract):
    """Standard Korean Dictionary search contract (#222)."""

    @pytest.fixture()
    def adapter(self) -> ProviderAdapter:
        return _build_adapter(["dict_search.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "dict_search"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: ProviderAdapter) -> DatasetRef:
        return adapter.get_dataset("dict_search")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(filters={"q": "나무"}, page_size=10)

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return ("search.do", {"q": "나무", "start": 1, "num": 5})
