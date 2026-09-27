"""KIPRIS (Korean Intellectual Property Rights Information Service) adapter contract tests (#223)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.providers.kipris import KiprisAdapter
from kpubdata.transport.http import HttpTransport
from tests.contract.provider_adapter import ProviderAdapterContract
from tests.unit.providers.datago.conftest import FakeResponse

_FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "kipris"


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
    return KiprisAdapter(
        config=KPubDataConfig(provider_keys={"kipris": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )


class TestKiprisPatentFamilyContract(ProviderAdapterContract):
    """Patent family information search contract (#223)."""

    @pytest.fixture()
    def adapter(self) -> ProviderAdapter:
        return _build_adapter(["patent_family.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "patent_family"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: ProviderAdapter) -> DatasetRef:
        return adapter.get_dataset("patent_family")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(filters={"applicationNumber": "1020050082226"}, page_size=10)

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return ("getAppNoPatFamInfoSearch", {"applicationNumber": "1020050082226"})
