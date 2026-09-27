"""NEIS (Nice) adapter contract tests (#164)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.providers.neis import NeisAdapter
from kpubdata.transport.http import HttpTransport
from tests.contract.provider_adapter import ProviderAdapterContract
from tests.unit.providers.datago.conftest import FakeResponse

_NEIS_FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "neis"


def _load_fixture(name: str) -> bytes:
    return (_NEIS_FIXTURE_DIR / name).read_bytes()


class _FixtureTransport:
    def __init__(self, fixture_names: list[str]) -> None:
        self._responses = [FakeResponse(_load_fixture(name)) for name in fixture_names]
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._responses.pop(0)


def _build_adapter(fixture_names: list[str]) -> ProviderAdapter:
    transport = _FixtureTransport(fixture_names)
    adapter = NeisAdapter(
        config=KPubDataConfig(provider_keys={"neis": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter


class TestNeisMealDietContract(ProviderAdapterContract):
    """School meal diet information contract (#164)."""

    @pytest.fixture()
    def adapter(self) -> ProviderAdapter:
        return _build_adapter(["meal_diet.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "meal_diet"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: ProviderAdapter) -> DatasetRef:
        return adapter.get_dataset("meal_diet")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(
            filters={"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7021108"},
            page_size=10,
        )

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return (
            "mealServiceDietInfo",
            {"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7021108", "pIndex": 1, "pSize": 5},
        )


class TestNeisSchoolInfoContract(ProviderAdapterContract):
    """School basic information contract (#218)."""

    @pytest.fixture()
    def adapter(self) -> ProviderAdapter:
        return _build_adapter(["school_info.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "school_info"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: ProviderAdapter) -> DatasetRef:
        return adapter.get_dataset("school_info")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(filters={"ATPT_OFCDC_SC_CODE": "B10"}, page_size=10)

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return ("schoolInfo", {"ATPT_OFCDC_SC_CODE": "B10", "pIndex": 1, "pSize": 5})
